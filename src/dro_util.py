import struct

class DROTrimmerException(Exception):
    pass

class DROFileException(DROTrimmerException):
    pass


def warning(text):
    """ Accepts a string, prints string prefixed with "WARNING! - " """
    # maybe TODO: GUI message queue?
    print "WARNING! - " + text


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

