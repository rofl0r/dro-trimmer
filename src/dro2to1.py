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

from __future__ import with_statement
import os
import struct
import sys

class DRO2to1Exception(Exception):
    pass

def convertDRO2to1(dro2_file, dro1_file):
    hardware_type_map = [0, 2, 1] # V2 goes OPL-2, Dual 2, 3. V1 goes OPL-2, 3, Dual 2.
    DRO_VERSION_V1_NEW = (0, 1)
    DRO_VERSION_V2 = (2, 0)
    DRO_HEADER = "DBRAWOPL"

    header_name = dro2_file.read(8)
    if header_name != DRO_HEADER:
        raise DRO2to1Exception("Does not appear to be a DRO file (invalid header. Expected %s, found %s)." %
                               (DRO_HEADER, header_name))

    header_version = struct.unpack('<2H', dro2_file.read(4))
    if header_version != DRO_VERSION_V2:
        raise DRO2to1Exception("Unsupported version of the DRO file format. Supported: v1 or v2. Found: %s" %
                               (header_version,))

    (iLengthPairs, iLengthMS, iHardwareType, iFormat, iCompression, iShortDelayCode, iLongDelayCode,
     iCodemapLength) = struct.unpack('<2L6B', dro2_file.read(14))
    codemap = struct.unpack(str(iCodemapLength) + 'B', dro2_file.read(iCodemapLength))
    if iFormat != 0:
        raise DRO2to1Exception("Unsupported DRO v2 format. Only 0 is supported, found format ID %s" % iFormat)
    if iCompression != 0:
        raise DRO2to1Exception("Unsupported DRO v2 compression. Only 0 is supported, found compression ID %s" % iFormat)
    if len(codemap) > 128:
        raise DRO2to1Exception("DRO v2 file has too many entries in the codemap. Maximum 128, found %s. Is the file corrupt?" %
                               len(codemap))

    # Write the header.
    dro1_file.write(DRO_HEADER)
    dro1_file.write(struct.pack('<2H', *DRO_VERSION_V1_NEW))
    dro1_file.write(struct.pack('<L', iLengthMS))
    # Need to come back and write this
    size_offset = dro1_file.tell()
    dro1_file.write(struct.pack('<L', 0)) # write a dummy value for now
    dro1_file.write(struct.pack('<L', hardware_type_map[iHardwareType]))

    data_start_offset = dro1_file.tell()
    total_size = 0
    last_bank = 0
    for i in xrange(iLengthPairs):
        reg, val = struct.unpack('2B', dro2_file.read(2))
        if reg == iShortDelayCode:
            out_val = struct.pack('2B', 0x00, val)
            total_size += 2
        elif reg == iLongDelayCode:
            val = ((val + 1) << 8) - 1
            out_val = struct.pack('<BH', 0x01, val)
            total_size += 3
        else:
            bank = (reg & 0x80) >> 7
            if bank is not last_bank:
                # NOTE: bank switching is currently inefficient.
                # In DRO V2, registers are normally altered in pairs, e.g. 0x80 and 0x180 (low and high bank).
                # This means converted files will have low/high bank switching before every
                #  instruction, which is inefficient. A better conversion would group together
                #  the low and high bank instructions.
                out_val = struct.pack('B', 0x02 + bank)
                dro1_file.write(out_val)
                total_size += 1
                last_bank = bank
            reg &= 0x7F
            reg = codemap[reg]
            if reg < 0x05:
                out_val = struct.pack('3B', 0x04, reg, val)
                total_size += 3
            else:
                out_val = struct.pack('2B', reg, val)
                total_size += 2
        dro1_file.write(out_val)

    dro1_file.flush()
    dro1_file.seek(size_offset)
    dro1_file.write(struct.pack('<L', total_size))

def main():
    args = sys.argv
    if len(args) < 2 or len(args) > 3:
        print "Please pass the name of the file you want to convert, and optionally the output file name."
        return 1
    input_file_name = args[1]
    if not os.path.isfile(input_file_name):
        print "File not found, or is not a file: %s" % input_file_name
        return 2
    if len(args) == 3:
        output_file_name = args[2]
    else:
        base, ext = os.path.splitext(input_file_name)
        output_file_name = base + "_1" + ext
    if os.path.isfile(output_file_name):
        print ("Output file already exists, please delete it or rename it, or specify a different output file name: %s"
            % output_file_name)
        return 3

    try:
        print "Converting V2 file %s to V1 file %s..." % (input_file_name, output_file_name)
        with file(input_file_name, 'rb') as input_file:
            with file(output_file_name, 'wb') as output_file:
                convertDRO2to1(input_file, output_file)

        print "Done!"
        return 0
    except Exception, e:
        print e
        return 4

if __name__ == "__main__": sys.exit(main())