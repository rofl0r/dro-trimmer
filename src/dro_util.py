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

class StructFromKeywords(object):
    def __init__(self, **kwds):
        for key in kwds:
            setattr(self, key, kwds[key])

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

def condense_slices(index_list):
    """ Assumes index_list is sorted, in either ascending or descending order.
    Based on http://stackoverflow.com/a/10987875"""
    start = index_list[0]
    i = 1
    c_list = []
    while i < len(index_list):
        # Diff != 1? Slice ended, or non-slice value.
        if abs(index_list[i] - index_list[i - 1]) != 1:
            end = index_list[i - 1]
            if start == end:
                c_list.append(start)
            else:
                c_list.append(slice(min(start, end), max(start, end)))
            start = index_list[i]
        i += 1
    if index_list[-1] == start:
        c_list.append(start)
    else:
        c_list.append(slice(min(start, index_list[-1]), max(start, index_list[-1])))
    return c_list

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

def ms_to_timestr(ms_val):
    # Stolen from StackOverflow, post by Sven Marnach
    minutes, milliseconds = divmod(ms_val, 60000)
    seconds = float(milliseconds) / 1000
    return "%02i:%02i" % (minutes, seconds)

## {{{ http://code.activestate.com/recipes/134892/ (r2)
class _Getch:
    """
    Gets a single character from standard input.  Does not echo to
    the screen.
    """
    def __init__(self):
        try:
            self.impl = _GetchWindows()
        except ImportError:
            try:
                self.impl = _GetchMacCarbon()
            except(AttributeError, ImportError):
                self.impl = _GetchUnix()

    def __call__(self): return self.impl()

class _GetchUnix:
    def __init__(self):
        import tty, sys

    def __call__(self):
        import sys, tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

class _GetchMacCarbon:
    """
    A function which returns the current ASCII key that is down;
    if no ASCII key is down, the null string is returned.  The
    page http://www.mactech.com/macintosh-c/chap02-1.html was
    very helpful in figuring out how to do this.
    """
    def __init__(self):
        import Carbon
        Carbon.Evt #see if it has this (in Unix, it doesn't)

    def __call__(self):
        import Carbon
        if Carbon.Evt.EventAvail(0x0008)[0]==0: # 0x0008 is the keyDownMask
            return ''
        else:
            #
            # The event contains the following info:
            # (what,msg,when,where,mod)=Carbon.Evt.GetNextEvent(0x0008)[1]
            #
            # The message (msg) contains the ASCII char which is
            # extracted with the 0x000000FF charCodeMask; this
            # number is converted to an ASCII character with chr() and
            # returned
            #
            (what,msg,when,where,mod)=Carbon.Evt.GetNextEvent(0x0008)[1]
            return chr(msg & 0x000000FF)

class _GetchWindows:
    def __init__(self):
        import msvcrt

    def __call__(self):
        import msvcrt
        return msvcrt.getch()

getch = _Getch()
## end of http://code.activestate.com/recipes/134892/ }}}
