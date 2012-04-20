#!/usr/bin/python
#
#    This file is part of DRO Trimmer.
#
#    DRO Trimmer is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    DRO Trimmer is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with DRO Trimmer.  If not, see <http://www.gnu.org/licenses/>.
#
# DRO Trimmer
# Laurence Dougal Myers
# 0.1.0 Started October 2006, released 12 June 2007 (public domain)
# 0.2.0 Started 23 August 2008, released 26 December 2008 (LGPL)
# 
# Notes:
#  - the multicolumntable is inefficient, should use wxPython rather than PythonCard for that
#  - analysis is kind of dumb and useless (especially "least used registers")
#  - the GUI doesn't resize properly

import struct
import difflib
from regdata import registers

# This var is just for backwards compatability - it seems old versions of DRO
#  files wrote the OPL type as a char, whereas newer versions write it as a 4-byte
#  int. This program supports either, but it's hard coded.
WRITE_CHAR_OPL = False

DROF_HEADER = "DBRAWOPL"
DROF_VERSION = 0x10000
TEST_FILE_NAME = "merc_001.dro"

#dro_stats = {}


class DROTrimmerException(Exception):
    pass

class DROFileException(DROTrimmerException):
    pass


class DROSong(object):
    def __init__(self, name, data, ms_length, opl_type):
        self.name = name
        self.data = data
        self.ms_length = ms_length
        self.opl_type = opl_type

    def getName(self):
        return self.name

    def setName(self, newname):
        """ Sets the filename of the DRO song. Must be a full path."""
        self.name = newname
        
    def getData(self):
        return self.data
    
    def getOPLType(self):
        return self.opl_type
    
    def getLengthMS(self):
        return self.ms_length

    def getLengthInstr(self):
        return len(self.data)
    
    def getInstr(self, i):
        return self.data[i]
    
    def findNextInstr(self, start, inst):
        """ Takes a starting index and register number (as a hex string) or
        a special value of "D-08", "D-18" or "BANK", and finds the next
        occurance of that register after the given index. Returns the index."""
        
        # This is nuts. Change the comparison test depending on what we're
        #  looking for.
        i = start
        if inst == "D-08":
            ct = lambda d, inst: d[0] == 0x00
        elif inst == "D-16":
            ct = lambda d, inst: d[0] == 0x01
        elif inst == "DALL":
            ct = lambda d, inst: d[0] == 0x00 or d[0] == 0x01
        elif inst == "BANK":
            ct = lambda d, inst: d[0] == 0x02 or d[0] == 0x03
        elif (int(inst, 16) <= 0x04): # registers requiring override
            ct = lambda d, inst: d[0] == 0x04 and d[1] == inst
            inst = int(inst, 16)
        else:
            ct = lambda d, inst: d[0] == inst
            inst = int(inst, 16)
        
        # Below could (and probably should) be changed to one of the following.
        # It will require remembering the last value we looked for, as well as
        #  the iterator.
        #matching_tuples = (mylist[i] for i in range(current_index, len(mylist)) if mylist[i][0] == 0x70)
        # or
        #index_to_search_from = 2
        #sliced = itertools.islice(iter(mylist), index_to_search_from, None)
        #matching_tuples = (a for a in sliced if a[0] == 0x70)
        #matching_tuples.next()
        
        while i < len(self.data):
            if ct(self.data[i], inst):
                return i
            i += 1
        
        return -1
        
    
    def deleteInstruction(self, i):
        """ Deletes instruction at given index."""
        inst = self.data[i]
        # Update total delay count if removing a delay
        if inst[0] == 0x00 or inst[0] == 0x01:
            self.ms_length -= inst[1]
        self.data = self.data[:i] + self.data[i + 1:]
        


def warning(text):
    """ Accepts a string, prints string prefixed with "WARNING! - " """
    # maybe TODO: GUI message queue?
    print "WARNING! - " + text

def load_dro(file_name):
    """ Accepts a file name (string). Returns a DROSong object and whether it was auto-trimmed (boolean).
    
    Raises DROFileException on invalid file data/version."""
    # Code interpreted from the adplug source code.
    dro_byte_length = 0
    dro_ms_length = 0
    dro_opl_type = 0
    
    drof = file(file_name, 'rb')
    
    # File validation
    header = drof.read(8)
    if header != DROF_HEADER:
        drof.close()
        raise DROFileException("Does not appear to be a DRO file (invalid header).")
    
    version = read_int(drof)
    if version != DROF_VERSION:
        drof.close()
        raise DROFileException("Unsupported version of the DRO file format.")

    #print("Successfully opened DRO file.")
    
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
    dro_stats = {}
    line_num = 0
    
    # Read in and interpret the data stream
    while drof.tell() - header_end_pos < dro_byte_length:
        line = "" # human readable line
        cmd = read_char(drof) # 
        inst = [cmd] # instruction
        if cmd == 0x00: # delay, 1-byte
            # I think it's the val + 1 ms for a delay? so a delay of 0 = 1ms?
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
            if registers.has_key(tmp_val):
                hr = registers[tmp_val]
            else:
                hr = "unknown"
        #elif cmd == 0x10: # delay, 2-bytes? DOSBox source code seems confused
            #pass
        else:
            tmp_val = read_char(drof)
            inst.append(tmp_val)
        
        # Log some statistics (occurances of register changes)
        # Lower number of changes will be 
        # Only worry about reg <-- val commands for now (ignore overrides)
        if inst[0] > 0x04:
            # Note to self: could use a defaultdict here
            if not dro_stats.has_key(inst[1]):
                dro_stats[inst[1]] = 1
            else:
                dro_stats[inst[1]] += 1
            
        # Log the data
        dro_data.append(tuple(inst))
    
    # If we haven't reached the EOF we must have an error somewhere in the code.
    m = drof.read(1)
    
    drof.close() # need to close the file anyway, so do it here
    
    if m != "":
        raise DROFileException("Tried to read the specified number of bytes in the data stream, but there were some bytes left over!")
    else:
        #print "Successfully loaded DRO data!\n ms_length: ", dro_ms_length, " (reported)\n", \
        #      " dro_calc_delay: ", dro_calc_delay, " (calculated)\n", \
        #      " dro_byte_length: ", dro_byte_length, "\n", \
        #      " dro_opl_type: ", dro_opl_type, "\n", \
        #      " len(dro_data): ", len(dro_data)
        
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
            #print dro_data[0]
            auto_trimmed = True
            #print("Removed bogus initial delay, new dro_calc_delay is " + str(dro_calc_delay))
        length_mismatch = False
        if dro_calc_delay != dro_ms_length:
            length_mismatch = True
            #warning("Calculated song length does not match the file's stored song length.\n This is usually caused by a delay instruction near the start, but removing it might corrupt the song.")
            
        return (DROSong(file_name, dro_data, dro_ms_length, dro_opl_type), auto_trimmed, length_mismatch)
    
def save_dro(file_name, dro_song):
    """ Accepts a file name (string), and a DROSong object. Saves the DROSong
    data to a file."""
    drof = file(file_name, 'wb')
    
    write_header(drof, 0, 0, 0) # write a dummy header
    
    total_size = 0 # keep track of the size of the data (in bytes)
    total_delay = 0 # keep track of the length of the song (in ms)
    # Each delay is stored - 1, so need to account for that when writing
    #  the song length.
    delay_offset = 0
    
    for inst in dro_song.getData():
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
    drof.seek(0)
    write_header(drof, total_delay, total_size, dro_song.getOPLType())
    
    drof.close()

    print("DRO file saved. total_delay: " + str(total_delay) + " total_size: " + str(total_size))

def analyze_dro():
    global dro_data
    
    # Split the data in half and see what the largest matching block is.
    # This will give us an indication on whether or not the song loops, and if so,
    #  where the loop points are.
    sm = difflib.SequenceMatcher()
    tmp_len = len(dro_data) / 2
    tmp_a = dro_data[:tmp_len]
    tmp_b = dro_data[tmp_len:]
    sm.set_seqs(tmp_a, tmp_b)
    
    # We have to do "len(dro_data) - tmp_len" because of rounding when 
    #  dividing by two earlier.
    result = sm.find_longest_match(0, tmp_len, 0, len(dro_data) - tmp_len)
    print("Result of analysis: longest block = " + str(result[2]) + \
          ", start first half = " + str(result[0]) + \
          ", start second half = " + str(result[1] + tmp_len))
       
    # TODO: Find the first instance of the data block dro_data[result[0]:result[1] + tmp_len]?
    # No. This is not the problem. The problem is that the longest block could be because
    #  it starts with a note-off, whereas the first block will not have that note off. Every
    #  loop iteration, however, will have that note off, and so it will have a longer matching
    #  block.
    # Taking this into consideration, notify the user that if the first instruction
    #  in the matched block is a note off, there may be an earlier block that is more
    #  suitable for trimming.
    
    # If first instruction is note off, alert user
    if dro_data[result[0]][0] in range(0xB0, 0xB9):
        print("Note: The first instruction in the matched block was a key on/off. There may be " + \
              "a more appropriate block earlier in the song.")
    
    first_delay = 0
    # Now search for the first delay
    for i, inst in enumerate(dro_data):
        if inst[0] == 0 or inst[0] == 1:
            first_delay = i
            print("Result of analysis: first delay at pos = " + str(i))
            break
    
    return (result[0], result[1] + tmp_len, first_delay)
    


def write_header(in_f, length, size, opl_type):
    in_f.write(DROF_HEADER)
    write_int(in_f, DROF_VERSION)
    write_int(in_f, length)
    write_int(in_f, size)
    if WRITE_CHAR_OPL: # I guess for backwards compatability?
        write_char(in_f, opl_type)
    else:
        write_int(in_f, opl_type)


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


def test():
    global dro_ms_total
    global dro_total_delay
    global dro_data
    droData = load_dro(TEST_FILE_NAME)[0]
    print("Finished loading DRO, will now try saving.")
    save_dro("drotrim_out.dro", droData)
    print("Done")
    #print "DRO reported length: ", dro_ms_total, "\nCalculated length: ", dro_total_delay
    #print " difference: ", dro_total_delay - dro_ms_total
    ##print dro_data[0]
    #
    ## Try deleting something
    #for i, d in enumerate(dro_data):
    #    if d[0] == 0x00 or d[0] == 0x01:
    #        old_delay = dro_total_delay
    #        print "Removing delay of " + str(d[1]) + "ms"
    #        delete_instruction(i)
    #        print "New total delay: " + str(dro_total_delay)
    #        print "Calculated difference of total delays: " + str(dro_total_delay - old_delay)
    #        break
        
    
    
if __name__ == '__main__':
    test()
    
