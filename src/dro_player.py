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

import threading
import pyaudio
import pyopl
import dro_data
from dro_util import DROTrimmerException


class OPLStream(object):
    """ Based on demo.py that comes with the PyOPL library.
    """
    def __init__(self, frequency, buffer_size, bit_depth, audio_stream):
        """
        @type frequency: int
        @type buffer_size: int
        @type bit_depth: int
        @type audio_stream: PyAudio
        """
        global SAMPLE_SIZE
        self.frequency = frequency
        self.buffer_size = buffer_size
        self.bit_depth = bit_depth
        self.audio_stream = audio_stream # probably shouldn't be a local property...
        self.opl = pyopl.opl(frequency, sampleSize=(self.bit_depth / 8))
        self.buffer = bytearray(buffer_size * (self.bit_depth / 8))
        self.stop_requested = False # required so we don't keep rendering obsolete data after stopping playback.

    def write(self, register, value):
        self.opl.writeReg(register, value)

    def render(self, length_ms):
        samples_to_render = length_ms * self.frequency / 1000
        leftover_size = samples_to_render % self.buffer_size
        if leftover_size:
            leftover = bytearray(leftover_size * (self.bit_depth / 8))
        else:
            leftover = None
        tmp_buffer = self.buffer
        while samples_to_render > 0 and not self.stop_requested:
            if samples_to_render < self.buffer_size:
                tmp_buffer = leftover
            self.opl.getSamples(tmp_buffer)
            pyaudio_buffer = buffer(tmp_buffer)
            self.audio_stream.write(pyaudio_buffer)
            samples_to_render -= self.buffer_size

    def set_high_bank(self):
        # TODO
        pass

    def set_low_bank(self):
        # TODO
        pass


class DROPlayer(object):
    def __init__(self):
        self.frequency = 48000
        self.buffer_size = 512
        self.bit_depth = 16
        self.channels = 1
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
        self.update_thread = None

    def load_song(self, new_song):
        """
        @type new_song: DROSongV2
        """
        self.is_playing = False
        if self.current_song is not None:
            self.reset()
        self.current_song = new_song

    def reset(self):
        self.is_playing = False
        self.pos = 0
        if self.update_thread is not None:
            self.update_thread.stop_request.set()
        self.update_thread = None # This thread gets created only when playing actually begins.
        self.opl_stream = OPLStream(self.frequency, self.buffer_size, self.bit_depth, self.audio_stream)
        self.opl_stream.write(1, 32) # hack. Apparently always sets it to OPL-3 mode. Sounds better in my testing.

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

    def seek(self, pos_fraction):
        seeker = DROSeekerFactory(self.current_song)
        seeker.seek(self, pos_fraction)

    def seek_to_pos(self, seek_pos):
        seeker = DROSeekerFactory(self.current_song)
        seeker.seek_to_pos(self, seek_pos)


class DROSeekerFactory(object):
    def __new__(cls, dro_song):
        if dro_song.file_version == dro_data.DRO_FILE_V1:
            return DROSeekerV1()
        elif dro_song.file_version == dro_data.DRO_FILE_V2:
            return DROSeekerV2()
        else:
            raise DROTrimmerException("DROSeekerFactory doesn't recognise the file format of the DRO song."
                                        "Expected one of (%s, %s), found %s instead." % (dro_data.DRO_FILE_V1,
                                                                                         dro_data.DRO_FILE_V2,
                                                                                         dro_song.file_version))


class DROSeeker(object):
    """ Helper class to seek in DRO songs. Externalised from the player so the player class remains DRO-version neutral.
    """
    # Could potentially merge with the updater thread, and have a flag to skip "rendering" of any sound.
    def seek(self, dro_player, pos_fraction):
        """Seeks by time to the given fraction of the total song length.
         e.g. for a song that is 4:00 minutes long, pass in 0.5 to skip to approx. 2:00.
        """
        raise NotImplementedError()

    def seek_to_pos(self, dro_player, seek_pos):
        """Seeks to a particular instruction position.
        This method is useful for playing a song from an instruction highlighted in the table editor.
        Note tha position has no real bearing on the length of the song in ms - for a song with 200 instructions,
        40 of them might be initializing registers/operators.
        """
        raise NotImplementedError()


class DROSeekerV1(DROSeeker):
    #def seek(self, dro_player, pos_fraction):
    #    pass

    def seek_to_pos(self, dro_player, seek_pos):
        seek_pos = min(seek_pos, len(dro_player.current_song.data)) # make sure seek_pos is within bounds
        dro_player.pos = 0
        while dro_player.pos < seek_pos:
            datum = dro_player.current_song.data[dro_player.pos]
            cmd = datum[0]
            if cmd in (0x00, 0x01): # delay
                pass # ignore delays
            elif cmd == 0x02:
                dro_player.opl_stream.set_low_bank()
            elif cmd == 0x03:
                dro_player.opl_stream.set_high_bank()
            elif cmd == 0x04:
                reg, val = datum[1], datum[2]
                dro_player.opl_stream.write(reg, val)
            else:
                reg, val = datum[0], datum[1]
                dro_player.opl_stream.write(reg, val)
            dro_player.pos += 1


class DROSeekerV2(DROSeeker):
    def seek(self, dro_player, pos_fraction):
        seek_pos = int(pos_fraction * dro_player.current_song.getLengthMS())
        dro_player.pos = 0
        time_pos = 0
        while time_pos < seek_pos and dro_player.pos < len(dro_player.current_song.data):
            reg, val = dro_player.current_song.data[dro_player.pos]
            if reg in (dro_player.current_song.short_delay_code, dro_player.current_song.long_delay_code):
                time_pos += val
                # If we go past the intended seek time, don't increment the position counter. This way we end up
                #  before the seek time, rather than after it.
                if time_pos < seek_pos:
                    break
            else:
                if reg & 0x80:
                    dro_player.opl_stream.set_high_bank()
                    reg &= 0x7F
                else:
                    dro_player.opl_stream.set_low_bank()
                dro_player.opl_stream.write(dro_player.current_song.codemap[reg], val)
            dro_player.pos += 1

    def seek_to_pos(self, dro_player, seek_pos):
        seek_pos = min(seek_pos, len(dro_player.current_song.data)) # make sure seek_pos is within bounds
        dro_player.pos = 0
        while dro_player.pos < seek_pos:
            reg, val = dro_player.current_song.data[dro_player.pos]
            if reg not in (dro_player.current_song.short_delay_code, dro_player.current_song.long_delay_code):
                if reg & 0x80:
                    dro_player.opl_stream.set_high_bank()
                    reg &= 0x7F
                else:
                    dro_player.opl_stream.set_low_bank()
                dro_player.opl_stream.write(dro_player.current_song.codemap[reg], val)
            dro_player.pos += 1


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

class DROPlayerUpdateThreadV2(DROPlayerUpdateThread):
    def run(self):
        while (self.dro_player.pos < len(self.current_song.data)
               and self.dro_player.is_playing
               and not self.stop_request.isSet()):
            reg, val = self.current_song.data[self.dro_player.pos]
            if reg in (self.current_song.short_delay_code, self.current_song.long_delay_code):
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


def main():
    """ As a bonus, this module can be used as a standalone program to play a DRO song! (TODO)
    """
    import dro_io
    import time
    #import dro_data
    test_song = "pm2_001_out.dro"
    file_reader = dro_io.DroFileIO()
    dro_song = file_reader.read(test_song)[0]
    dro_player = DROPlayer()
    dro_player.load_song(dro_song)
    dro_player.seek(0.9)
    dro_player.play()
    while dro_player.is_playing:
        print "Oh, still playing? Zzzz..."
        time.sleep(1)


if __name__ == "__main__": main()
