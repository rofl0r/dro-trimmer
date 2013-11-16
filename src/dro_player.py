#!/usr/bin/python
#
#    Use, distribution, and modification of the DRO Trimmer binaries, source code,
#    or documentation, is subject to the terms of the MIT license, as below.
#
#    Copyright (c) 2008 - 2013 Laurence Dougal Myers
#
#    Permission is hereby granted, free of charge, to any person obtaining a copy
#    of this software and associated documentation files (the "Software"), to deal
#    in the Software without restriction, including without limitation the rights
#    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#    copies of the Software, and to permit persons to whom the Software is
#    furnished to do so, subject to the following conditions:
#
#    The above copyright notice and this permission notice shall be included in
#    all copies or substantial portions of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#    THE SOFTWARE.

import optparse
import os
import sys
import threading
import time
import wave
import pyaudio
import pyopl
import dro_analysis
import dro_capture
import dro_data
import dro_globals
import dro_util
import dro_io


def stopPlayerOnException(func):
    def inner_func(self, *args, **kwds):
        try:
            func(self, *args, **kwds)
        except:
            self.dro_player.is_playing = False
            raise
    return inner_func


class WavRenderer(object):
    def __init__(self, frequency, bit_depth, channels):
        self.frequency = frequency
        self.bit_depth = bit_depth
        self.channels = channels
        self.wav = None
        self.wav_fname = None
        self.wav_lock = threading.RLock()

    def open(self, dro_song):
        if self.wav_fname is None:
            self.wav_fname = "{}.wav".format(dro_song.name)
        self.wav = wave.open(self.wav_fname, 'wb')
        self.wav.setnchannels(self.channels)
        self.wav.setsampwidth(self.bit_depth / 8)
        self.wav.setframerate(self.frequency)

    def close(self):
        with self.wav_lock:
            if self.wav is not None:
                self.wav.close()
                self.wav = None # Hm, maybe should leave it hanging around?
                self.wav_fname = None

    def write(self, data):
        with self.wav_lock:
            if self.wav is not None:
                self.wav.writeframes(data)

    def set_output_fname(self, output_fname):
        self.wav_fname = "{}.wav".format(output_fname)


class ProcessingStreamsList(list):
    def __init__(self):
        super(ProcessingStreamsList, self).__init__()
        self._bank = 0

    @property
    def bank(self):
        return self._bank

    @bank.setter
    def bank(self, value):
        self._bank = value
        for stream in self:
            stream.bank = value

    def open(self, dro_song):
        for stream in self:
            stream.open(dro_song)

    def set_output_fname(self, output_fname):
        for stream in self:
            stream.set_output_fname(output_fname)

    def write(self, register, value):
        for stream in self:
            stream.write(register, value)

    def render(self, ms_to_render):
        for stream in self:
            stream.render(ms_to_render)

    def render_chip_delay(self):
        for stream in self:
            stream.render_chip_delay()

    def clear_chip_delay_drift(self):
        for stream in self:
            stream.clear_chip_delay_drift()

    def stop(self):
        for stream in self:
            stream.stop()


class OPLStream(object):
    """ Based on demo.py that comes with the PyOPL library.

    Also accounts for chip-write delays:
     "The AdLib manual gives the wait times in microseconds: three point three
     (3.3) microseconds for the address, and twenty-three (23) microseconds
     for the data."

    The OPL3 (YMF262) spec suggests that an address write and data write both need a wait of 32 master clock cycles.
    The master clock runs at 14.32 MHz. 64 cycles is 4.469273743016759776536312849162 microseconds... approximately ;)

    This page:
    http://www.ugcs.caltech.edu/~john/computer/opledit/tech/opl3.txt
    Says:
     "Unlike Adlib (OPL2), OPL3 doesn't need delay between register writes.
     With OPL2 you had to wait 3.3 [microseconds] after index register write and another
     23 [microseconds] after data register write. On the contrary OPL3 doesn't need
     (almost) any delay after index register write and only 0.28 [microseconds] after data
     register write. This means you can neglect the delays and slightly speed up
     your music driver. But using reasonable delays will certainly do no harm."

    A post on VOGONS mentions it could be 3.3us... sigh.

    Anyway, basically we need to make it configurable.

    """

    def __init__(self, frequency, buffer_size, bit_depth, channels, chip_write_delay, output_streams):
        """
        @type frequency: int
        @type buffer_size: int
        @type bit_depth: int
        @type channels: int
        @type chip_write_delay: float
        @type output_streams: list, containing PyAudio or WavRenderer objects.
        """
        self.frequency = frequency # Changing this to be different to the audio rate produces a tempo-shifting effect
        self.buffer_size = buffer_size
        self.bit_depth = bit_depth
        self.channels = channels
        self.chip_write_delay = chip_write_delay
        self.output_streams = output_streams
        self.opl = pyopl.opl(frequency, sampleSize=(self.bit_depth / 8), channels=self.channels)
        self.buffer = self.__create_bytearray(buffer_size)
        self.pyaudio_buffer = buffer(self.buffer)
        self.stop_requested = False # required so we don't keep rendering obsolete data after stopping playback.
        self._bank = 0
        self.chip_delay_drift = 0 # OPL2/OPL3 need microsecond delays writing to registers, we need to account for it.
        self.sample_overflow = 0 # float, fraction of samples that still need to be rendered.
        self.reset()

    @property
    def bank(self):
        return self._bank

    @bank.setter
    def bank(self, value):
        self._bank = value

    def reset(self):
        """
        The OPL emulator will retain it state, we need to make sure that we can clear its state
        (e.g. when creating a new OPL stream).
        """
        orig_bank = self.bank
        for bank in xrange(2):
            self.bank = bank
            for reg in xrange(0x100):
                self.write(reg, 0x00)
        self.bank = orig_bank

    def open(self, dro_song):
        for ostream in self.output_streams:
            if isinstance(ostream, WavRenderer): # blech
                ostream.open(dro_song)

    def set_output_fname(self, output_fname):
        for ostream in self.output_streams:
            if isinstance(ostream, WavRenderer): # blech
                ostream.set_output_fname(output_fname)

    def stop(self):
        self.stop_requested = True
        for ostream in self.output_streams:
            if isinstance(ostream, WavRenderer): # blech
                ostream.close()

    def __create_bytearray(self, size):
        return bytearray(size * (self.bit_depth / 8) * self.channels)

    def write(self, register, value):
        if self.bank:
            register |= 0x100
            # Could be re-written as "register |= self.bank << 2"
        self.opl.writeReg(register, value)
        self.chip_delay_drift += self.chip_write_delay

    def render(self, length_ms):
        # Taken from PyOPL 1.0 and 1.2. Accurate rendering, though a bit inefficient.
        samples_to_render = length_ms * self.frequency / 1000.0
        samples_to_render += self.sample_overflow
        self.sample_overflow = samples_to_render % 1
        if samples_to_render < 2:
            # Limitation of PyOPL: needs a minimum of two samples.
            return
        samples_to_render = int(samples_to_render // 1)
        while samples_to_render > 0 and not self.stop_requested:
            if samples_to_render < self.buffer_size:
                tmp_buffer = self.__create_bytearray((samples_to_render % self.buffer_size))
                tmp_audio_buffer = buffer(tmp_buffer)
                samples_to_render = 0
            else:
                tmp_buffer = self.buffer
                tmp_audio_buffer = self.pyaudio_buffer
                samples_to_render -= self.buffer_size
            self.opl.getSamples(tmp_buffer)
            for ostream in self.output_streams:
                ostream.write(buffer(tmp_audio_buffer))

    def render_chip_delay(self):
        if self.chip_delay_drift > 0:
            self.render(self.chip_delay_drift / 1000.0)
            self.chip_delay_drift = 0

    def clear_chip_delay_drift(self):
        self.chip_delay_drift = 0


class DROPlayer(object):
    CHANNEL_REGISTERS = frozenset(range(0xB0, 0xB8 + 1)  +
                                  range(0x1B0, 0x1B8 + 1))
    PERCUSSION_REGISTER = 0xBD
    #PERCUSSION_VALUES = frozenset(map(lambda i: 2 ** i, range(5)))

    def __init__(self, channels=2):
        # TODO: move config reading somewhere else
        # TODO: separate frequency etc for opl rendering
        #  (similar to DOSBox's mixer vs opl settings)
        try:
            config = dro_util.read_config()
            self.frequency = config.getint("audio", "frequency")
            self.buffer_size = config.getint("audio", "buffer_size")
            self.bit_depth = config.getint("audio", "bit_depth")
            self.chip_write_delay = config.getfloat("audio", "chip_write_delay")
        except Exception, e:
            print "Could not read audio settings from drotrim.ini, using default values. (Error: %s)" % e
            self.frequency = 48000
            self.buffer_size = 512
            self.bit_depth = 16
            self.chip_write_delay = 0
        self.channels = channels # crap
        audio = pyaudio.PyAudio()
        self.audio_stream = audio.open(
            format = audio.get_format_from_width(self.bit_depth / 8),
            channels = self.channels,
            rate = self.frequency,
            output = True)
        # Set up the WAV Renderer
        self.wav_renderer = WavRenderer(
            self.frequency,
            self.bit_depth,
            self.channels
        )
        # Set up other stuff
        self.processing_streams = ProcessingStreamsList()
        self.current_song = None
        self.is_playing = False
        self.pos = 0
        self.time_elapsed = 0
        self.update_thread = None
        self.sound_on = True
        self.recording_on = False
        self.capture_dro = False
        self.active_channels = set(self.CHANNEL_REGISTERS)
        self.active_percussion = [0xFF, 0xFF]
        self.writes_elapsed = 0

    def load_song(self, new_song):
        """
        @type new_song: DROSongV2
        """
        self.is_playing = False
        self.current_song = new_song
        self.reset()

    def reset(self):
        self.is_playing = False
        self.pos = 0
        self.time_elapsed = 0
        self.writes_elapsed = 0
        if self.update_thread is not None:
            self.update_thread.stop_request.set()
        self.update_thread = None # This thread gets created only when playing actually begins.
        output_streams = []
        if self.sound_on:
            output_streams.append(self.audio_stream)
        if self.recording_on:
            output_streams.append(self.wav_renderer)
        opl_stream = OPLStream(self.frequency, self.buffer_size, self.bit_depth, self.channels,
                                    self.chip_write_delay, output_streams)
        if self.current_song is not None:
            if self.current_song.file_version == dro_data.DRO_FILE_V1:
                # Hack. DRO V1 files don't seem to set the "Waveform select" register
                # correctly, so OPL-2 songs sound very wrong. Doesn't affect V2 files.
                opl_stream.write(1, 32)
        self.processing_streams = ProcessingStreamsList()
        self.processing_streams.append(opl_stream)
        if self.capture_dro:
            dro_out_stream = dro_capture.DroCapture()
            self.processing_streams.append(dro_out_stream)
        self.active_percussion = set(self.CHANNEL_REGISTERS)
        self.active_percussion = [0xFF, 0xFF]

    def set_output_fname(self, output_fname):
        self.processing_streams.set_output_fname(output_fname)

    def play(self):
        self.is_playing = True
        self.processing_streams.open(self.current_song)
        self.update_thread = DROPlayerUpdateThread(self, self.current_song)
        self.update_thread.start()

    def stop(self):
        self.is_playing = False
        if self.update_thread is not None:
            self.update_thread.stop_request.set()
        self.processing_streams.stop()

    def seek_to_time(self, seek_time):
        seeker = DROSeeker(self)
        seeker.seek_to_time(seek_time)

    def seek_to_pos(self, seek_pos):
        seeker = DROSeeker(self)
        seeker.seek_to_pos(seek_pos)

    @property
    def write_delay_elapsed(self):
        return self.writes_elapsed * self.chip_write_delay // 1000

    @property
    def time_with_write_delay_elapsed(self):
        return self.time_elapsed + self.write_delay_elapsed


class DROSeeker(object):
    """ Helper class to seek in DRO songs. Externalised from the player so the player class remains DRO-version neutral.
    """

    def __init__(self, dro_player):
        self.dro_player = dro_player # circular reference, yuck
    
    # Could potentially merge with the updater thread, and have a flag to skip "rendering" of any sound.
    @stopPlayerOnException
    def seek_to_time(self, seek_time_ms):
        """Seeks to the specified time.
        Seek time is clamped between 0 and the song's recorded ms_length."""
        seek_time_ms = min(max(seek_time_ms, 0), self.dro_player.current_song.ms_length)

        self.dro_player.pos = 0
        while (self.dro_player.time_elapsed < seek_time_ms
               and self.dro_player.pos < len(self.dro_player.current_song.data)):
            inst = self.dro_player.current_song.data[self.dro_player.pos]
            if inst.inst_type == dro_data.DROInstruction.T_DELAY:
                delay = inst.value
                # If we go past the intended seek time, don't increment the position counter. This way we end up
                #  before the seek time, rather than after it.
                if self.dro_player.time_elapsed + delay > seek_time_ms:
                    break
                self.dro_player.time_elapsed += delay
            elif inst.inst_type == dro_data.DROInstruction.T_BANK_SWITCH:
                self.dro_player.processing_streams.bank = inst.value # DRO v1
            #elif inst.inst_type == dro_data.DROInstruction.T_REGISTER:
            else:
                if inst.bank is not None: # DRO v2
                    self.dro_player.processing_streams.bank = inst.bank
                self.dro_player.processing_streams.write(inst.command, inst.value)
                self.dro_player.writes_elapsed += 1
            self.dro_player.pos += 1
        self.dro_player.processing_streams.clear_chip_delay_drift()

    @stopPlayerOnException
    def seek_to_pos(self, seek_pos):
        """Seeks to a particular instruction position.
        This method is useful for playing a song from an instruction highlighted in the table editor.
        Note the position has no real bearing on the length of the song in ms - for a song with 200 instructions,
        40 of them might be initializing registers/operators.
        """
        seek_pos = min(seek_pos, len(self.dro_player.current_song.data)) # make sure seek_pos is within bounds
        self.dro_player.pos = 0
        while self.dro_player.pos < seek_pos:
            inst = self.dro_player.current_song.data[self.dro_player.pos]
            if inst.inst_type == dro_data.DROInstruction.T_DELAY:
                self.dro_player.time_elapsed += inst.value
            elif inst.inst_type == dro_data.DROInstruction.T_BANK_SWITCH:
                self.dro_player.processing_streams.bank = inst.value # DRO v1
            #elif inst.inst_type == dro_data.DROInstruction.T_REGISTER:
            else:
                if inst.bank is not None: # DRO v2
                    self.dro_player.processing_streams.bank = inst.bank
                self.dro_player.processing_streams.write(inst.command, inst.value)
                self.dro_player.writes_elapsed += 1
            self.dro_player.pos += 1
        self.dro_player.processing_streams.clear_chip_delay_drift()


class DROPlayerUpdateThread(threading.Thread):
    PERCUSSION_REGISTER = 0xBD

    def __init__(self, dro_player, current_song):
        super(DROPlayerUpdateThread, self).__init__()
        self.dro_player = dro_player # circular reference, yuck
        self.current_song = current_song
        self.stop_request = threading.Event()
        self.active_channels = set(self.dro_player.active_channels)
        self.active_percussion = set(self.dro_player.active_percussion)

    @stopPlayerOnException
    def run(self):
        while (self.dro_player.pos < len(self.current_song.data)
               and self.dro_player.is_playing
               and not self.stop_request.isSet()):
            # First, check if we need to mute a channel register.
            new_muted_channels = self.active_channels - self.dro_player.active_channels
            orig_bank = self.dro_player.processing_streams.bank
            for channel in new_muted_channels:
                self.dro_player.processing_streams.bank = (channel & 0x100) >> 8
                self.dro_player.processing_streams.write(channel & 0xFF, 0x00)
            del orig_bank
            # Check if we need to unmute a channel register (also remove muted channels).
            if self.dro_player.active_channels ^ self.active_channels:
                self.active_channels = set(self.dro_player.active_channels)

            # Process the instruction.
            inst = self.dro_player.current_song.data[self.dro_player.pos]
            if inst.inst_type == dro_data.DROInstruction.T_DELAY:
                self.dro_player.processing_streams.render(inst.value)
                self.dro_player.time_elapsed += inst.value
            elif inst.inst_type == dro_data.DROInstruction.T_BANK_SWITCH:
                self.dro_player.processing_streams.bank = inst.value # DRO v1
            #elif inst.inst_type == dro_data.DROInstruction.T_REGISTER:
            else:
                if inst.bank is not None: # DRO v2
                    self.dro_player.processing_streams.bank = inst.bank
                # Check if this is a channel register, and if so, if it should be muted.
                # Percussion channel is handled separately
                if inst.command == self.PERCUSSION_REGISTER:
                    # Need to pass through the 3 high bits of the percussion channel.
                    # We rely on the bitmask to handle this.
                    mask = self.dro_player.active_percussion[self.dro_player.processing_streams.bank]
                    val = inst.value & mask
                    self.dro_player.processing_streams.write(inst.command, val)
                # Non-channel registers get a pass.
                elif not inst.command in self.dro_player.CHANNEL_REGISTERS:
                    self.dro_player.processing_streams.write(inst.command, inst.value)
                # Only write to channel registers if they are active.
                elif (self.dro_player.processing_streams.bank << 8) | inst.command in self.active_channels:
                    self.dro_player.processing_streams.write(inst.command, inst.value)
                self.dro_player.writes_elapsed += 1
                self.dro_player.processing_streams.render_chip_delay()
            # Update position and stop if no more instructions.
            self.dro_player.pos += 1
            if self.dro_player.pos >= len(self.current_song.data):
                self.dro_player.is_playing = False
        self.dro_player.stop()


class _TimerUpdateThread(threading.Thread):
    def __init__(self, calc_ms_length):
        super(_TimerUpdateThread, self).__init__()
        self.time_elapsed = 0
        self.calc_ms_length = calc_ms_length
        self.stop_request = threading.Event()

    def run(self):
        calc_ms_length_string = dro_util.ms_to_timestr(self.calc_ms_length)
        while not self.stop_request.isSet():
            # Pretty rough way of keeping time.
            sys.stdout.write("\r{} / {}".format(
                 dro_util.ms_to_timestr(self.time_elapsed),
                 calc_ms_length_string
                )
            )
            sys.stdout.flush()
            time.sleep(0.01)
            self.time_elapsed += 10


def __parse_arguments():
    usage = ("Usage: %prog [options] dro_file\n\n" +
             "Plays a DRO song. Can also be used to render a song to a single WAV file.\n\n" +
             "Keyboard shorcuts:\n" +
             " 0-9: solo channel\n" +
             " ~: unmute all channels\n" +
             " -: switch to the low bank\n" +
             " +: switch to the high bank (OPL-3)"
             " CTRL-C: cancel playback"
        )
    version = dro_globals.g_app_version
    oparser = optparse.OptionParser(usage, version=version)
    oparser.add_option("-r", "--render", action="store_true", dest="render", default=False,
                      help="Render the song to a WAV file. Sound output is disabled.")
    options, args = oparser.parse_args()
    return oparser, options, args


def main():
    """ As a bonus, this module can be used as a standalone program to play a DRO song!
    """
    oparser, options, args = __parse_arguments()
    if len(args) < 1:
        print "Please pass the name of the song to play as the first argument."
        oparser.print_help()
        return 1
    song_to_play = args[0]
    if not os.path.isfile(song_to_play):
        print "Song does not appear to exist, or is not a file: %s" % song_to_play
        return 3

    file_reader = dro_io.DroFileIO()
    dro_song = file_reader.read(song_to_play)
    dro_player = DROPlayer()
    dro_player.sound_on = not options.render
    dro_player.recording_on = options.render
    dro_player.load_song(dro_song)
    print dro_song.pretty_string()

    timer_thread = None
    try:
        calc_ms_length = dro_analysis.DROTotalDelayWithWriteDelayCalculator().sum_delay(dro_song)
        calc_ms_length_string = dro_util.ms_to_timestr(calc_ms_length)
        if options.render:
            dro_player.play()
            while dro_player.is_playing:
                sys.stdout.write("\r{} / {}".format(
                    dro_util.ms_to_timestr(dro_player.time_with_write_delay_elapsed),
                    calc_ms_length_string))
                sys.stdout.flush()
                time.sleep(0.05)
            # Print the end time too (but cheat)
            sys.stdout.write("\r{} / {}".format(
                calc_ms_length_string,
                calc_ms_length_string)
            )
        else:
            dro_player.play()
            timer_thread = _TimerUpdateThread(calc_ms_length)
            timer_thread.start()
            bank = 0
            while dro_player.is_playing:
                # Check for user input.
                chin = dro_util.getch()
                if chin:
                    if 48 <= ord(chin) <= 57: # solo channels
                        if int(chin) == 0:
                            channel = 0xBD
                        else:
                            channel = 0xB0 + int(chin) - 1
                        channel |= (bank << 8)
                        dro_player.active_channels = set([channel])
                    elif chin == "`" or chin == "~": # reset
                        dro_player.active_channels = set(dro_player.CHANNEL_REGISTERS)
                    elif chin == "-" or chin == "_": # switch to bank 0
                        bank = 0
                    elif chin == "=" or chin == "+": # switch to bank 1
                        bank = 1
                time.sleep(0.01)
            # Print the end time too (but cheat)
            sys.stdout.write("\r{} / {}".format(
                calc_ms_length_string,
                calc_ms_length_string)
            )
    except KeyboardInterrupt, ke:
        pass
    except Exception, e:
        print e
        return 2
    finally:
        if dro_player.is_playing:
            dro_player.stop()
        if timer_thread is not None:
            timer_thread.stop_request.set()
            if timer_thread.isAlive(): # not quite right, but meh.
                timer_thread.join()
    return 0


if __name__ == "__main__":
    sys.exit(main())
