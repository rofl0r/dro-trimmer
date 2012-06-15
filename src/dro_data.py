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

import difflib
import dro_undo
import regdata

DRO_FILE_V1 = 1
DRO_FILE_V2 = 2

class DROSong(object):
    """ NOTE: this actually implements methods for the V1 file format.
    """
    OPL_TYPE_MAP = [
        "OPL-2",
        "OPL-3",
        "Dual OPL-2"
    ]

    def __init__(self, file_version, name, data, ms_length, opl_type):
        self.file_version = file_version
        self.name = name
        self.data = data
        self.ms_length = ms_length
        self.opl_type = opl_type
        self.short_delay_code = 0x00
        self.long_delay_code = 0x01

    def getLengthMS(self):
        return self.ms_length

    def getLengthData(self):
        return len(self.data)

    def find_next_instruction(self, start, inst, look_backwards=False):
        """ Takes a starting index and register number (as a hex string) or
        a special value of "DLYS", "DLYL" or "BANK", and finds the next
        occurrence of that register after the given index. Returns the index."""

        # This is nuts. Change the comparison test depending on what we're
        #  looking for.
        i = start
        if inst == "DLYS":
            ct = lambda d, inst: d[0] == self.short_delay_code
        elif inst == "DLYL":
            ct = lambda d, inst: d[0] == self.long_delay_code
        elif inst == "DALL":
            ct = lambda d, inst: d[0] in (self.short_delay_code, self.long_delay_code)
        elif inst == "BANK":
            ct = lambda d, inst: d[0] == 0x02 or d[0] == 0x03
        elif int(inst, 16) <= 0x04: # registers requiring override
            ct = lambda d, inst: d[0] == 0x04 and d[1] == inst
            inst = int(inst, 16)
        else:
            ct = lambda d, inst: d[0] == inst
            inst = int(inst, 16)

        if look_backwards:
            i -= 2 # so we don't get stuck on the currently selected instruction
            while i >= 0:
                if ct(self.data[i], inst):
                    return i
                i -= 1
        else:
            while i < len(self.data):
                if ct(self.data[i], inst):
                    return i
                i += 1

        return -1

    def __insert_instructions(self, index_and_value_list):
        """ Currently just an internal method, used for undoing deletions.

        Note to self: if this gets exposed to outside calls, make it
        "undoable" too.
        """
        for i, reg_and_val in index_and_value_list:
            self.data.insert(i, reg_and_val) # inefficient but I'm mega-lazy.
            if reg_and_val[0] in (self.short_delay_code, self.long_delay_code):
                self.ms_length += reg_and_val[1]

    @dro_undo.undoable("Delete Instruction(s)", dro_undo.g_undo_controller, __insert_instructions)
    def delete_instructions(self, index_list):
        """ Deletes instructions at the given indexes.

        Returns a list of tuples, containing the index deleted and the value
        that was stored at that index."""
        deleted_data = []
        new_data = []
        for i, reg_and_val in enumerate(self.data):
            if i in index_list:
                deleted_data.append((i, reg_and_val))
                if reg_and_val[0] in (self.short_delay_code, self.long_delay_code):
                    self.ms_length -= reg_and_val[1]
            else:
                new_data.append(reg_and_val)
        self.data = new_data
        return deleted_data

    def get_register_display(self, item):
        instr = self.data[item]
        cmd = instr[0]
        if cmd == 0x00: # delay, 1-byte
            return "D-08"
        elif cmd == 0x01: # delay, 2-bytes?
            return "D-16"
        elif cmd == 0x02 or cmd == 0x03: # switch cmd/val pair
            return "BANK"
        elif cmd == 0x04: # reg <- val pair, override
            return '0x%02X' % (instr[1])
        else:
            return '0x%02X' % (instr[0])

    def get_value_display(self, item):
        instr = self.data[item]
        cmd = instr[0]
        if cmd == 0x00 or cmd == 0x01: # delays
            return str(instr[1]) + " ms"
        elif cmd == 0x02: # low cmd/val pair
            return "low"
        elif cmd == 0x03: # high cmd/val pair
            return "high"
        elif cmd == 0x04: # reg <- val pair, override
            return '0x%02X (%s)' % (instr[2], instr[2])
        else:
            return '0x%02X (%s)' % (instr[1], instr[1])

    def get_instruction_description(self, item):
        instr = self.data[item]
        cmd = instr[0]
        if cmd == 0x00:
            return "Delay (8-bit)"
        elif cmd == 0x01:
            return "Delay (16-bit)"
        elif cmd == 0x02:
            return "Switch to low registers (Dual OPL-2 / OPL-3)"
        elif cmd == 0x03:
            return "Switch to high registers (Dual OPL-2 / OPL-3)"
        elif cmd == 0x04:
            try:
                reg_desc = regdata.registers[instr[1]]
            except KeyError:
                reg_desc = "(unknown)"
            return reg_desc + " (data override)"
        else:
            try:
                reg_desc = regdata.registers[cmd]
            except KeyError:
                reg_desc = "(unknown)"
            return reg_desc

    def __str__(self):
        return "DRO[name = '%s', ver = '%s', opl_type = '%s' (%s), ms_length = '%s']" % (
            self.name, self.file_version, self.opl_type, self.OPL_TYPE_MAP[self.opl_type], self.ms_length
        )


class DROSongV2(DROSong):
    OPL_TYPE_MAP = [
        "OPL-2",
        "Dual OPL-2",
        "OPL-3"
    ]

    def __init__(self, file_version, name, data, ms_length, opl_type, codemap, short_delay_code, long_delay_code):
        super(DROSongV2, self).__init__(file_version, name, data, ms_length, opl_type)
        self.codemap = codemap
        self.short_delay_code = short_delay_code
        self.long_delay_code = long_delay_code

    def find_next_instruction(self, start, s_inst, look_backwards=False):
        """ Takes a starting index and register number (as a hex string) or
        a special value of "DLYS" or "DLYL", and finds the next
        occurrence of that register after the given index. Returns the index."""

        i = start
        if s_inst == "DLYS":
            ct = lambda d, inst: d[0] == self.short_delay_code
        elif s_inst == "DLYL":
            ct = lambda d, inst: d[0] == self.long_delay_code
        elif s_inst == "DALL":
            ct = lambda d, inst: d[0] in (self.short_delay_code, self.long_delay_code)
        else:
            def search_func(d, inst):
                reg, val = d
                if reg in (self.short_delay_code, self.long_delay_code):
                    return False
                reg = self.codemap[d[0] & 0x7F]
                return reg == inst
            ct = search_func
            s_inst = int(s_inst, 16)

        if look_backwards:
            i -= 2 # so we don't get stuck on the currently selected instruction
            while i >= 0:
                if ct(self.data[i], s_inst):
                    return i
                i -= 1
        else:
            while i < len(self.data):
                if ct(self.data[i], s_inst):
                    return i
                i += 1

        return -1

    def get_register_display(self, item):
        reg, val = self.data[item]
        if reg == self.short_delay_code:
            return "DLYS"
        elif reg == self.long_delay_code:
            return "DLYL"
        else:
            return '0x%03X' % ((reg & 0x80) << 1 | self.codemap[reg & 0x7F])

    def get_value_display(self, item):
        reg, val = self.data[item]
        if reg in (self.short_delay_code, self.long_delay_code):
            # Assume long delays have already been left-shifted.
            return str(val) + " ms"
        else:
            return '0x%02X (%s)' % (val, val)

    def get_instruction_description(self, item):
        reg, val = self.data[item]
        if reg == self.short_delay_code:
            return "Delay (short)"
        elif reg == self.long_delay_code:
            return "Delay (long)"
        else:
            bank = "high" if reg & 0x80 else "low"
            reg_lookup = reg & 0x7F
            try:
                reg_desc = regdata.registers[self.codemap[reg_lookup]]
            except KeyError:
                # OPL-3 has some special registers that are only in the high bank
                if reg & 0x80:
                    try:
                        reg_desc = regdata.registers[0x100 | self.codemap[reg_lookup]]
                    except KeyError:
                        reg_desc = "(unknown)"
                else:
                    reg_desc = "(unknown)"
            return "%s (%s bank)" % (reg_desc, bank)


class DROTotalDelayCalculator(object):
    def sum_delay(self, dro_song):
        # Bleh
        calc_delay = 0
        for datum in dro_song.data:
            reg = datum[0]
            if reg in (dro_song.short_delay_code, dro_song.long_delay_code):
                calc_delay += datum[1]
        return calc_delay


class DROFirstDelayAnalyzer(object):
    def __init__(self):
        self.result = False

    def analyze_dro(self, dro_song):
        """
        @type dro_song: DROSong
        """
        if not len(dro_song.data):
            return
        reg_and_val = dro_song.data[0]
        if reg_and_val[0] in (dro_song.short_delay_code, dro_song.long_delay_code):
            self.result = True


class DROTotalDelayMismatchAnalyzer(object):
    def __init__(self):
        self.result = False

    def analyze_dro(self, dro_song):
        calc_delay = DROTotalDelayCalculator().sum_delay(dro_song)
        self.result = calc_delay != dro_song.ms_length

class DROLoopAnalyzer(object):
    def analyze_dro(self, dro_song):
        dro_data = dro_song.data
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
        print("Result of analysis: longest block = " + str(result[2]) +\
              ", start first half = " + str(result[0]) +\
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
            print("Note: The first instruction in the matched block was a key on/off. There may be " +\
                  "a more appropriate block earlier in the song.")

        first_delay = 0
        # Now search for the first delay
        for i, inst in enumerate(dro_data):
            if inst[0] == 0 or inst[0] == 1:
                first_delay = i
                print("Result of analysis: first delay at pos = " + str(i))
                break

        return (result[0],
                result[1] + tmp_len,
                first_delay)
