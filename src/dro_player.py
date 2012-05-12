#!/usr/bin/python
#
#    Use, distribution, and modification of the DRO Trimmer binaries, source code,
#    or documentation, is subject to the terms of the MIT license, as below.
#
#    Copyright (c) 2008 - 2012 Laurence Dougal Myers
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

import ConfigParser
import threading
import pyaudio
import pyopl
import dro_data
from dro_util import DROTrimmerException

def stopPlayerOnException(func):
    def inner_func(self, *args, **kwds):
        try:
            func(self, *args, **kwds)
        except:
            self.dro_player.is_playing = False
            raise
    return inner_func


class OPLStream(object):
    """ Based on demo.py that comes with the PyOPL library.
    """
    def __init__(self, frequency, buffer_size, bit_depth, channels, audio_stream):
        """
        @type frequency: int
        @type buffer_size: int
        @type bit_depth: int
        @type audio_stream: PyAudio
        """
        self.frequency = frequency # Changing this to be different to the audio rate produces a tempo-shifting effect
        self.buffer_size = buffer_size
        self.bit_depth = bit_depth
        self.channels = channels
        self.audio_stream = audio_stream # probably shouldn't be a local property...
        self.opl = pyopl.opl(frequency, sampleSize=(self.bit_depth / 8), channels=self.channels)
        self.buffer = bytearray(buffer_size * (self.bit_depth / 8) * self.channels)
        self.pyaudio_buffer = buffer(self.buffer)
        self.stop_requested = False # required so we don't keep rendering obsolete data after stopping playback.
        self.samples_to_render = 0 # only used for PyOPL 1.1 rendering method
        self.bank = 0

    def write(self, register, value):
        if self.bank:
            register |= 0x100
            # Could be re-written as "register |= self.bank << 2"
        self.opl.writeReg(register, value)

    def render_new(self, length_ms):
        # Taken from PyOPL 1.0 and 1.2. Accurate rendering, though a bit inefficient.
        samples_to_render = length_ms * self.frequency / 1000
        while samples_to_render > 0 and not self.stop_requested:
            if samples_to_render < self.buffer_size:
                tmp_buffer = bytearray((samples_to_render % self.buffer_size) * (self.bit_depth / 8) * self.channels)
                tmp_audio_buffer = buffer(tmp_buffer)
                samples_to_render = 0
            else:
                tmp_buffer = self.buffer
                tmp_audio_buffer = self.pyaudio_buffer
                samples_to_render -= self.buffer_size
            self.opl.getSamples(tmp_buffer)
            self.audio_stream.write(buffer(tmp_audio_buffer))

    def render_old(self, length_ms):
        # Taken from the PyOPL 1.1 demo.py. Slightly inaccurate as
        #  long as you render around 44/48khz. Lower resolutions
        #  will have more obvious problems, try 8000 for example.
        self.samples_to_render += length_ms * self.frequency / 1000
        while self.samples_to_render > self.buffer_size:
            self.opl.getSamples(self.buffer)
            self.audio_stream.write(self.pyaudio_buffer)
            self.samples_to_render -= self.buffer_size

    render = render_new

    def set_high_bank(self):
        self.bank = 1

    def set_low_bank(self):
        self.bank = 0


class DROPlayer(object):
    def __init__(self):
        # TODO: move config reading somewhere else
        # TODO: separate frequency etc for opl rendering
        #  (similar to DOSBox's mixer vs opl settings)
        try:
            config = ConfigParser.SafeConfigParser()
            config_files_parsed = config.read(['drotrim.ini'])
            if not len(config_files_parsed):
                raise DROTrimmerException("Could not read drotrim.ini, using default audio options.")
            self.frequency = config.getint("audio", "frequency")
            #self.buffer_size = config.getint("audio", "buffer_size")
            self.bit_depth = config.getint("audio", "bit_depth")
        except Exception, e:
            print "Could not read audio settings from drotrim.ini, using default values. (Error: %s)" % e
            self.frequency = 48000
            #self.buffer_size = 512
            self.bit_depth = 16
        self.buffer_size = 512
        self.channels = 2
        audio = pyaudio.PyAudio()
        self.audio_stream = audio.open(
            format = audio.get_format_from_width(self.bit_depth / 8),
            channels = self.channels,
            rate = self.frequency,
            output = True)
        self.opl_stream = None
        self.current_song = None
        self.is_playing = False
        self.pos = 0
        self.time_elapsed = 0
        self.update_thread = None

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
        if self.update_thread is not None:
            self.update_thread.stop_request.set()
        self.update_thread = None # This thread gets created only when playing actually begins.
        self.opl_stream = OPLStream(self.frequency, self.buffer_size, self.bit_depth, self.channels, self.audio_stream)
        if (self.current_song is not None
            and self.current_song.file_version == dro_data.DRO_FILE_V1):
            # Hack. DRO V1 files don't seem to set the "Waveform select" register
            # correctly, so OPL-2 songs sound very wrong. Doesn't affect V2 files.
            self.opl_stream.write(1, 32)

    def play(self):
        self.is_playing = True
        self.update_thread = DROPlayerUpdateThreadFactory(self, self.current_song)
        self.update_thread.start()

    def start(self):
        """ Alias of play()."""
        self.play()

    def stop(self):
        self.is_playing = False
        if self.update_thread is not None:
            self.update_thread.stop_request.set()
        if self.opl_stream is not None:
            self.opl_stream.stop_requested = True

    def seek_to_time(self, seek_time):
        seeker = DROSeekerFactory(self)
        seeker.seek_to_time(seek_time)

    def seek_to_pos(self, seek_pos):
        seeker = DROSeekerFactory(self)
        seeker.seek_to_pos(seek_pos)


class DROSeekerFactory(object):
    def __new__(cls, dro_player):
        if dro_player.current_song.file_version == dro_data.DRO_FILE_V1:
            return DROSeekerV1(dro_player)
        elif dro_player.current_song.file_version == dro_data.DRO_FILE_V2:
            return DROSeekerV2(dro_player)
        else:
            raise DROTrimmerException("DROSeekerFactory doesn't recognise the file format of the DRO song."
                                        "Expected one of (%s, %s), found %s instead." % (dro_data.DRO_FILE_V1,
                                                                                         dro_data.DRO_FILE_V2,
                                                                                         dro_player.current_song.file_version))


class DROSeeker(object):
    """ Helper class to seek in DRO songs. Externalised from the player so the player class remains DRO-version neutral.
    """
    
    def __init__(self, dro_player):
        self.dro_player = dro_player
    
    # Could potentially merge with the updater thread, and have a flag to skip "rendering" of any sound.
    def seek_to_time(self, seek_time_ms):
        """Seeks to the specified time
        """
        raise NotImplementedError()

    def seek_to_pos(self, seek_pos):
        """Seeks to a particular instruction position.
        This method is useful for playing a song from an instruction highlighted in the table editor.
        Note tha position has no real bearing on the length of the song in ms - for a song with 200 instructions,
        40 of them might be initializing registers/operators.
        """
        raise NotImplementedError()


class DROSeekerV1(DROSeeker):
    @stopPlayerOnException
    def seek_to_time(self, seek_time_ms):
        """ Seek time is clamped between 0 and the song's recorded ms_length."""
        seek_time_ms = min(max(seek_time_ms, 0), self.dro_player.current_song.ms_length)

        self.dro_player.pos = 0
        while (self.dro_player.time_elapsed < seek_time_ms
            and self.dro_player.pos < len(self.dro_player.current_song.data)):
            datum = self.dro_player.current_song.data[self.dro_player.pos]
            cmd = datum[0]
            if cmd in (0x00, 0x01): # delay
                delay = datum[1]
                # If we go past the intended seek time, don't increment the position counter. This way we end up
                #  before the seek time, rather than after it.
                if self.dro_player.time_elapsed + delay > seek_time_ms:
                    break
                self.dro_player.time_elapsed += delay
            elif cmd == 0x02:
                self.dro_player.opl_stream.set_low_bank()
            elif cmd == 0x03:
                self.dro_player.opl_stream.set_high_bank()
            elif cmd == 0x04:
                reg, val = datum[1], datum[2]
                self.dro_player.opl_stream.write(reg, val)
            else:
                reg, val = datum[0], datum[1]
                self.dro_player.opl_stream.write(reg, val)
            self.dro_player.pos += 1

    @stopPlayerOnException
    def seek_to_pos(self, seek_pos):
        seek_pos = min(seek_pos, len(self.dro_player.current_song.data)) # make sure seek_pos is within bounds
        self.dro_player.pos = 0
        while self.dro_player.pos < seek_pos:
            datum = self.dro_player.current_song.data[self.dro_player.pos]
            cmd = datum[0]
            if cmd in (0x00, 0x01): # delay
                delay = datum[1]
                self.dro_player.time_elapsed += delay
            elif cmd == 0x02:
                self.dro_player.opl_stream.set_low_bank()
            elif cmd == 0x03:
                self.dro_player.opl_stream.set_high_bank()
            elif cmd == 0x04:
                reg, val = datum[1], datum[2]
                self.dro_player.opl_stream.write(reg, val)
            else:
                reg, val = datum[0], datum[1]
                self.dro_player.opl_stream.write(reg, val)
            self.dro_player.pos += 1


class DROSeekerV2(DROSeeker):
    @stopPlayerOnException
    def seek_to_time(self, seek_time_ms):
        """ Seek time is clamped between 0 and the song's recorded ms_length."""
        seek_time_ms = min(max(seek_time_ms, 0), self.dro_player.current_song.ms_length)
        self.dro_player.pos = 0
        self.dro_player.time_elapsed = 0
        while (self.dro_player.time_elapsed < seek_time_ms
               and self.dro_player.pos < len(self.dro_player.current_song.data)):
            reg, val = self.dro_player.current_song.data[self.dro_player.pos]
            if reg in (self.dro_player.current_song.short_delay_code, self.dro_player.current_song.long_delay_code):
                # If we go past the intended seek time, don't increment the position counter. This way we end up
                #  before the seek time, rather than after it.
                if self.dro_player.time_elapsed + val > seek_time_ms:
                    break
                self.dro_player.time_elapsed += val
            else:
                if reg & 0x80:
                    self.dro_player.opl_stream.set_high_bank()
                    reg &= 0x7F
                else:
                    self.dro_player.opl_stream.set_low_bank()
                self.dro_player.opl_stream.write(self.dro_player.current_song.codemap[reg], val)
            self.dro_player.pos += 1

    @stopPlayerOnException
    def seek_to_pos(self, seek_pos):
        seek_pos = min(seek_pos, len(self.dro_player.current_song.data)) # make sure seek_pos is within bounds
        self.dro_player.pos = 0
        while self.dro_player.pos < seek_pos:
            reg, val = self.dro_player.current_song.data[self.dro_player.pos]
            if reg not in (self.dro_player.current_song.short_delay_code, self.dro_player.current_song.long_delay_code):
                if reg & 0x80:
                    self.dro_player.opl_stream.set_high_bank()
                    reg &= 0x7F
                else:
                    self.dro_player.opl_stream.set_low_bank()
                self.dro_player.opl_stream.write(self.dro_player.current_song.codemap[reg], val)
            self.dro_player.pos += 1


class DROPlayerUpdateThreadFactory(object):
    def __new__(cls, dro_player, current_song):
        if current_song.file_version == dro_data.DRO_FILE_V1:
            return DROPlayerUpdateThreadV1(dro_player, current_song)
        elif current_song.file_version == dro_data.DRO_FILE_V2:
            return DROPlayerUpdateThreadV2(dro_player, current_song)
        else:
            raise DROTrimmerException("DROPlayerUpdateThreadFactory doesn't recognise the file format of the DRO song."
                                      "Expected one of (%s, %s), found %s instead." % (dro_data.DRO_FILE_V1,
                                                                                       dro_data.DRO_FILE_V2,
                                                                                       current_song.file_version))


class DROPlayerUpdateThread(threading.Thread):
    def __init__(self, dro_player, current_song):
        super(DROPlayerUpdateThread, self).__init__()
        self.dro_player = dro_player
        self.current_song = current_song
        self.stop_request = threading.Event()

    def run(self):
        raise NotImplementedError()


class DROPlayerUpdateThreadV1(DROPlayerUpdateThread):
    def run(self):
        try:
            while (self.dro_player.pos < len(self.current_song.data)
                   and self.dro_player.is_playing
                   and not self.stop_request.isSet()):
                datum = self.dro_player.current_song.data[self.dro_player.pos]
                cmd = datum[0]
                if cmd in (0x00, 0x01): # delay
                    delay = datum[1]
                    self.dro_player.opl_stream.render(delay)
                elif cmd == 0x02:
                    self.dro_player.opl_stream.set_low_bank()
                elif cmd == 0x03:
                    self.dro_player.opl_stream.set_high_bank()
                elif cmd == 0x04:
                    reg, val = datum[1], datum[2]
                    self.dro_player.opl_stream.write(reg, val)
                else:
                    reg, val = datum[0], datum[1]
                    self.dro_player.opl_stream.write(reg, val)
                self.dro_player.pos += 1
                if self.dro_player.pos >= len(self.current_song.data):
                    self.dro_player.is_playing = False
        except Exception, e:
            self.dro_player.is_playing = False
            raise e


class DROPlayerUpdateThreadV2(DROPlayerUpdateThread):
    def run(self):
        try:
            while (self.dro_player.pos < len(self.current_song.data)
                   and self.dro_player.is_playing
                   and not self.stop_request.isSet()):
                reg, val = self.current_song.data[self.dro_player.pos]
                if reg in (self.current_song.short_delay_code, self.current_song.long_delay_code):
                    self.dro_player.time_elapsed += val
                    self.dro_player.opl_stream.render(val)
                else:
                    if reg & 0x80:
                        self.dro_player.opl_stream.set_high_bank()
                        reg &= 0x7F
                    else:
                        self.dro_player.opl_stream.set_low_bank()
                    self.dro_player.opl_stream.write(self.current_song.codemap[reg], val)
                self.dro_player.pos += 1
                if self.dro_player.pos >= len(self.current_song.data):
                    self.dro_player.is_playing = False
        except Exception, e:
            self.dro_player.is_playing = False
            raise e

def main():
    """ As a bonus, this module can be used as a standalone program to play a DRO song!
    """
    import dro_io
    import os
    import sys
    import time

    if len(sys.argv) < 2:
        print "Pass the name of the song to play as the first argument. e.g. 'dro_player cdshock_000.dro'"
        return 1

    song_to_play = sys.argv[1]
    if not os.path.isfile(song_to_play):
        print "Song does not appear to exist, or is not a file: %s" % song_to_play
        return 3
    file_reader = dro_io.DroFileIO()
    dro_song = file_reader.read(song_to_play)
    dro_player = DROPlayer()
    dro_player.load_song(dro_song)
    print str(dro_song)

    def ms_to_timestr(ms_val):
        # Stolen from StackOverflow, post by Sven Marnach
        minutes, milliseconds = divmod(ms_val, 60000)
        seconds = float(milliseconds) / 1000
        return "%02i:%02i" % (minutes, seconds)

    time_elapsed = 0
    dro_player.play()
    try:
        while dro_player.is_playing:
            # Pretty rough way of keeping time.
            sys.stdout.write("\r" + ms_to_timestr(time_elapsed) + " / " + ms_to_timestr(dro_song.ms_length))
            sys.stdout.flush()
            time.sleep(1)
            time_elapsed += 1000
        # Print the end time too (but cheat)
        sys.stdout.write("\r" + ms_to_timestr(dro_song.ms_length) + " / " + ms_to_timestr(dro_song.ms_length))
    except KeyboardInterrupt, ke:
        pass
    except Exception, e:
        print e
        return 2
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
