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

from __future__ import with_statement
from dro_data import DRO_FILE_V1, DRO_FILE_V2, DROSong, DROSongV2
from dro_util import *

DRO_HEADER = "DBRAWOPL"
DRO_VERSION_V1_OLD = (1, 0)
DRO_VERSION_V1_NEW = (0, 1) # the DOSBox devs really screwed the versioning up, didn't they?
DRO_VERSION_V2 = (2, 0)

# This var is just for backwards compatability - it seems old versions of DRO
#  files wrote the OPL type as a char, whereas newer versions write it as a 4-byte
#  int. This program supports either, but it's hard coded.
WRITE_CHAR_OPL = False

class DroFileIO(object):
    def read(self, file_name):
        """ Accepts a file name (string). Returns a DROSong object and whether it was auto-trimmed (boolean).

        Raises DROFileException on invalid file data/version."""
        with file(file_name, 'rb') as drof:
            header_name = drof.read(8)
            if header_name != DRO_HEADER:
                raise DROFileException("Does not appear to be a DRO file (invalid header. Expected %s, found %s)." %
                                       (DRO_HEADER, header_name))

            header_version = struct.unpack('<2H', drof.read(4))
            if header_version in (DRO_VERSION_V1_OLD, DRO_VERSION_V1_NEW):
                reader = DroFileIOv1()
            elif header_version == DRO_VERSION_V2:
                reader = DroFileIOv2()
            else:
                raise DROFileException("Unsupported version of the DRO file format. Supported: v1 or v2. Found: %s" %
                                       (header_version,))

            dro_song = reader.read_data(file_name, drof)
            return dro_song

    def write(self, file_name, dro_song):
        with file(file_name, 'wb') as drof:
            drof.write(DRO_HEADER)
            if dro_song.file_version == DRO_FILE_V1:
                writer = DroFileIOv1()
                drof.write(struct.pack('<2H', *DRO_VERSION_V1_NEW)) # hmm, maybe shouldn't be here
            elif dro_song.file_version == DRO_FILE_V2:
                writer = DroFileIOv2()
                drof.write(struct.pack('<2H', *DRO_VERSION_V2)) # hmm, maybe shouldn't be here
            else:
                # Should never get here.
                raise DROFileException("Tried to save an unsupported version of the DRO file format. Support v1 or v2, found: %s" %
                                       (dro_song.file_version,))
            writer.write_data(drof, dro_song)

class DroFileIOv1(object):
    def read_data(self, file_name, drof):
        """ Accepts an open DRO file. Returns a DROSong object and whether it was auto-trimmed (boolean).

        Raises DROFileException on invalid file data/version."""
        # Code interpreted from the adplug source code.
        dro_byte_length = 0
        dro_ms_length = 0
        dro_opl_type = 0

        # Actually load some data
        dro_ms_length = read_int(drof) # Total milliseconds in file (not used)
        dro_byte_length = read_int(drof) # Total data bytes in file (not used)

        # Looking at the samurai.dro file in the adplug testing dir, it uses a char for
        #  the OPL type, but my rips use words.
        #  Looks like there's two different file formats, with the same version number.
        dro_opl_type = read_int(drof) # Type of opl data this can contain

        # To avoid the char/word problem, we'll just assume if the word we read in is
        #  too large (say, more than 0xFF), we probably meant to read a char, so go back
        #  and try again. Obviously this will cause problems if for some reason the DOSBox
        #  guys want to use an opl_type of e.g. 1893647, but I think that's unlikely.
        if dro_opl_type > 0xFF:
            drof.seek(-4, 1)
            dro_opl_type = read_char(drof)

        header_end_pos = drof.tell()

        dro_data = [] # DRO data stored as a list of tuples (instruction + parameter)
        dro_calc_delay = 0 # should match dro_ms_total by the end

        # Read in and interpret the data stream
        while drof.tell() - header_end_pos < dro_byte_length:
            cmd = read_char(drof) #
            inst = [cmd] # instruction
            if cmd == 0x00: # delay, 1-byte
                # I think it's the val + 1 ms for a delay, so a delay of 0 = 1ms
                tmp_val = read_char(drof) + 1
                inst.append(tmp_val)
                dro_calc_delay += tmp_val
            elif cmd == 0x01: # delay, 2-bytes?
                tmp_val = read_short(drof) + 1
                inst.append(tmp_val)
                dro_calc_delay += tmp_val
            elif cmd == 0x02: # low cmd/val pair
                pass
            elif cmd == 0x03: # high cmd/val pair
                pass
            elif cmd == 0x04: # reg <- val pair
                tmp_val = read_char(drof)
                tmp_val_2 = read_char(drof)
                inst.append(tmp_val)
                inst.append(tmp_val_2)
            else:
                tmp_val = read_char(drof)
                inst.append(tmp_val)

            # Log the data
            dro_data.append(tuple(inst))

        # If we haven't reached the EOF we must have an error somewhere in the code.
        m = drof.read(1)
        if m != "":
            raise DROFileException("Tried to read the specified number of bytes in the data stream, but there were some bytes left over!")

        auto_trimmed = False
        # Perform preliminary trimming.
        # DOSBox seems to incorrectly write a long delay as the first instruction,
        #  which is not counted towards the song length written in the DRO file;
        #  it also causes instruments to get messed up (at least in AdPlug, which
        #  considers the initial state dump to be everything before the first delay).
        #  As such, we get rid of this bogus instruction.
        if dro_data[0][0] == 0x00 or dro_data[0][0] == 0x01:
            dro_calc_delay -= dro_data[0][1]
            dro_data = dro_data[1:]
            auto_trimmed = True
            #print("Removed bogus initial delay, new dro_calc_delay is " + str(dro_calc_delay))
        length_mismatch = False
        if dro_calc_delay != dro_ms_length:
            length_mismatch = True
            #warning("Calculated song length does not match the file's stored song length.\n This is usually caused by a delay instruction near the start, but removing it might corrupt the song.")

        return (DROSong(DRO_FILE_V1, file_name, dro_data, dro_ms_length, dro_opl_type),
                auto_trimmed,
                length_mismatch)

    def write_data(self, drof, dro_song):
        """ Accepts a file name (string), and a DROSong object. Saves the DROSong
        data to a file."""

        header_start = drof.tell()

        self.write_header(drof, 0, 0, 0) # write a dummy header

        total_size = 0 # keep track of the size of the data (in bytes)
        total_delay = 0 # keep track of the length of the song (in ms)

        # Each delay is stored - 1, so need to account for that when writing
        #  the song length.

        for inst in dro_song.data:
            cmd = inst[0]
            write_char(drof, cmd)
            if cmd == 0x00: # (delay 8-bit)
                # Delays are stored as "delay - 1", but the song length in ms is
                #  calculated from the original delay. Hence, make a note of the
                #  original delay, then store the adjusted figure.
                tmp_val = inst[1]
                total_delay += tmp_val
                tmp_val -= 1
                write_char(drof, tmp_val)
                total_size += 2
            elif cmd == 0x01: # delay 16-bit
                tmp_val = inst[1]
                total_delay += tmp_val
                tmp_val -= 1
                write_short(drof, tmp_val)
                total_size += 3
            elif cmd == 0x02 or cmd == 0x03: # switch high/low register pairs
                total_size += 1
            elif cmd == 0x04: # command override
                write_char(drof, inst[1])
                write_char(drof, inst[2])
                total_size += 3
            else: # reg <- vals
                write_char(drof, inst[1])
                total_size += 2

        # rewind and rewrite the header
        drof.seek(header_start)
        self.write_header(drof, total_delay, total_size, dro_song.opl_type)

        print("DRO file saved. total_delay: " + str(total_delay) + " total_size: " + str(total_size))

    def write_header(self, in_f, length, size, opl_type):
        write_int(in_f, length)
        write_int(in_f, size)
        if WRITE_CHAR_OPL: # I guess for backwards compatibility?
            write_char(in_f, opl_type)
        else:
            write_int(in_f, opl_type)


class DroFileIOv2(object):
    def read_data(self, file_name, drof):
        (iLengthPairs, iLengthMS, iHardwareType, iFormat, iCompression, iShortDelayCode, iLongDelayCode,
         iCodemapLength) = struct.unpack('<2L6B', drof.read(14))
        codemap = struct.unpack(str(iCodemapLength) + 'B', drof.read(iCodemapLength))
        if iFormat != 0:
            raise DROFileException("Unsupported DRO v2 format. Only 0 is supported, found format ID %s" % iFormat)
        if iCompression != 0:
            raise DROFileException("Unsupported DRO v2 compression. Only 0 is supported, found compression ID %s" % iFormat)

        dro_calc_delay = 0
        dro_data = []
        for _ in xrange(iLengthPairs):
            reg, val = struct.unpack('2B', drof.read(2))
            if reg == iShortDelayCode:
                val += 1
                dro_calc_delay += val
            elif reg == iLongDelayCode:
                val = (val + 1) << 8
                dro_calc_delay += val
            # could also use this opportunity to verify the reg value is < 128.
            dro_data.append((reg, val))

        # TODO: auto-trim leading delay
        length_mismatch = dro_calc_delay != iLengthMS
        auto_trimmed = False

        # NOTE: iHardwareType value is different compared to V1. Really should cater for it.
        return (DROSongV2(DRO_FILE_V2, file_name, dro_data, iLengthMS, iHardwareType, codemap, iShortDelayCode, iLongDelayCode),
                auto_trimmed,
                length_mismatch) # ignore auto-trim and length mismatch for now

    def write_data(self, drof, dro_song):
        """
        @type drof: File
        @type drof: DROSongV2
        """
        # Write the header
        drof.write(
            struct.pack(
                '<2L6B',
                len(dro_song.data), # length in reg/val pairs
                dro_song.ms_length, # length in MS
                dro_song.opl_type, # hardware type
                0, # format
                0, # compression
                dro_song.short_delay_code,
                dro_song.long_delay_code,
                len(dro_song.codemap) # length of codemap
            )
        )
        # Write the codemap
        drof.write(
            struct.pack(
                str(len(dro_song.codemap)) + 'B',
                *dro_song.codemap
            )
        )
        # Write the data
        for reg, val in dro_song.data:
            if reg == dro_song.short_delay_code:
                val -= 1
            elif reg == dro_song.long_delay_code:
                val = (val >> 8) - 1
            drof.write(struct.pack('2B', reg, val))




