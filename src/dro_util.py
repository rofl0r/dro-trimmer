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
import os.path
import sys
import struct

__config = None

class DROTrimmerException(Exception):
    pass

class DROFileException(DROTrimmerException):
    pass

def read_config():
    global __config
    if __config is None:
        __config = ConfigParser.SafeConfigParser()
        # Mitigate issue #4 by always searching for a config file in the same
        #  path as the executable.
        exe_path = get_exe_path()
        config_files_parsed = __config.read(['drotrim.ini', os.path.join(exe_path, 'drotrim.ini')])
        if not len(config_files_parsed):
            raise DROTrimmerException("Could not read drotrim.ini.")
    return __config

def warning(text):
    """ Accepts a string, prints string prefixed with "WARNING! - " """
    # maybe TODO: GUI message queue?
    print "WARNING! - " + text

def get_exe_path():
    return os.path.dirname(sys.argv[0])

# These are only used for DRO 1 files...
def write_char(in_f, val):
    in_f.write(struct.pack("<B", val))

def read_char(in_f): # 1 byte
    return struct.unpack("<B", in_f.read(1))[0]

def write_short(in_f, val):
    in_f.write(struct.pack("<H", val))

def read_short(in_f): # 2 bytes
    return struct.unpack("<H", in_f.read(2))[0]

def write_int(in_f, val):
    in_f.write(struct.pack("<L", val))

def read_int(in_f): # 4 bytes, really a word
    return struct.unpack("<L", in_f.read(4))[0]

