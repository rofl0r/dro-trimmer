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

import array
import dro_analysis
import dro_globals
import dro_undo
import dro_util
import regdata

DRO_FILE_V1 = 1
DRO_FILE_V2 = 2


class DROInstruction(object):
    __slots__ = ["inst_type", "command", "value", "bank"]
    T_REGISTER, T_DELAY, T_BANK_SWITCH = range(3)
    BS_LOW, BS_HIGH = (0x02, 0x03)

    def __init__(self, inst_type, command, value, bank=None):
        self.inst_type = inst_type
        self.command = command
        self.value = value
        self.bank = bank

    def __repr__(self):
        return ("DROInstruction(%s, %s, %s, %s)" %
            (self.inst_type,
                self.command,
                self.value,
                self.bank))


class DRODataFactory(object):
    def __new__(cls, file_version, *args, **kwds):
        if file_version == DRO_FILE_V1:
            return DRODataV1(*args, **kwds)
        elif file_version == DRO_FILE_V2:
            return DRODataV1(*args, **kwds)
        else:
            return dro_util.DROTrimmerException("Unknown DRO version for data factory: %s" % file_version)


class DROData(object):
    """ Wraps around the DRO data, providing access to each instruction,
    while efficiently storing the item in memory.
    """
    def __init__(self, *args, **kwds):
        self.data = array.array('B')

    def translate_index(self, key):
        raise NotImplementedError()

    def interpret_data(self, real_index):
        raise NotImplementedError()

    def __len__(self):
        raise NotImplementedError()

    def iter_indexes(self):
        raise NotImplementedError()

    def __delitem__(self, key):
        first_index = self.translate_index(key)
        try:
            second_index = self.translate_index(key + 1)
        except IndexError:
            second_index = None
        if second_index is None:
            del self.data[first_index:] # possibly dangerous
        else:
            del self.data[first_index:second_index]

    def __getitem__(self, key):
        real_index = self.translate_index(key)
        return self.interpret_data(real_index)

    def __iter__(self):
        for i in self.iter_indexes():
            yield self[i]

    def fromfile(self, file_handle, num_entries):
        self.data.fromfile(file_handle, num_entries)

    def tofile(self, file_handle):
        self.data.tofile(file_handle)

    def raw_len(self):
        return len(self.data)

    def raw_iter(self):
        return iter(self.data)


class DRODataV1(DROData):
    def __init__(self, *args, **kwds):
        super(DRODataV1, self).__init__(*args, **kwds)
        self.index_map = [] # keys are indexes.

    def translate_index(self, index):
        return self.index_map[index]

    def interpret_data(self, real_index):
        cmd = self.data[real_index]
        if cmd == 0x00:
            inst_type = DROInstruction.T_DELAY
            val = self.data[real_index + 1] + 1
        elif cmd == 0x01:
            inst_type = DROInstruction.T_DELAY
            val = (self.data[real_index + 1] | (self.data[real_index + 2] << 8)) + 1
        elif cmd == 0x02:
            inst_type = DROInstruction.T_BANK_SWITCH
            val = 0x00
        elif cmd == 0x03:
            inst_type = DROInstruction.T_BANK_SWITCH
            val = 0x01
        elif cmd == 0x04:
            inst_type = DROInstruction.T_REGISTER
            cmd = self.data[real_index + 1]
            val = self.data[real_index + 2]
        else:
            inst_type = DROInstruction.T_REGISTER
            val = self.data[real_index + 1]

        return DROInstruction(inst_type, cmd, val)

    def __len__(self):
        return len(self.index_map)

    def iter_indexes(self):
        return iter(self.index_map)

    def generate_index_map(self):
        self.index_map = []
        i = 0
        while i < len(self.data):
            # Map the logical index to the real index
            self.index_map.append(i)
            # Skip to the next instruction
            cmd = self.data[i]
            if cmd == 0x00:
                i += 2
            elif cmd == 0x01:
                i += 3
            elif cmd in (0x02, 0x03):
                i += 1
            elif cmd == 0x04:
                i += 3
            else:
                i+= 2


class DRODataV2(DROData):
    def __init__(self, *args, **kwds):
        super(DRODataV2, self).__init__(self, *args, **kwds)
        self.codemap = None
        self.short_delay_code = None
        self.long_delay_code = None

    def translate_index(self, key):
        return key * 2

    def interpret_data(self, real_index):
        cmd = self.data[real_index]
        bank = None
        if cmd == self.short_delay_code:
            inst_type = DROInstruction.T_DELAY
            val = self.data[real_index + 1] + 1
        elif cmd == self.long_delay_code:
            inst_type = DROInstruction.T_DELAY
            val = (self.data[real_index + 1] + 1) << 8
        else:
            inst_type = DROInstruction.T_REGISTER
            bank = (cmd & 0x80) >> 7
            cmd = self.codemap[cmd & 0x7F]
            val = self.data[real_index + 1]

        return DROInstruction(inst_type, cmd, val, bank)

    def __len__(self):
        return len(self.data) / 2

    def iter_indexes(self):
        return xrange(len(self.data) / 2)


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
        self.detailed_register_descriptions = None

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
        # Also need to update our register descriptions, since the data has changed.
        self.generate_detailed_register_descriptions()

    @dro_undo.undoable("Delete Instruction(s)", dro_globals.get_undo_controller, __insert_instructions)
    def delete_instructions(self, index_list):
        """ Deletes instructions at the given indexes.

        Returns a list of tuples, containing the index deleted and the value
        that was stored at that index."""
        deleted_data = []
        new_data = []
        index_set = set(index_list)
        for i, reg_and_val in enumerate(self.data):
            if i in index_set:
                deleted_data.append((i, reg_and_val))
                if reg_and_val[0] in (self.short_delay_code, self.long_delay_code):
                    self.ms_length -= reg_and_val[1]
            else:
                new_data.append(reg_and_val)
        self.data = new_data
        # Also need to update our register descriptions, since the data has changed.
        self.generate_detailed_register_descriptions()
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

    def get_detailed_register_description(self, item):
        if (self.detailed_register_descriptions is None or
            item >= len(self.detailed_register_descriptions)):
            return "(not available)"
        else:
            return self.detailed_register_descriptions[item][1]

    def get_bank_description(self, item):
        if (self.detailed_register_descriptions is None or
            item >= len(self.detailed_register_descriptions)):
            return "(N/A)"
        else:
            return self.detailed_register_descriptions[item][0]

    def generate_detailed_register_descriptions(self):
        dro_globals.task_master().cancel_task("REG_ANALYSIS")
        self.detailed_register_descriptions = None
        detailed_register_analyzer = dro_analysis.DRODetailedRegisterAnalyzer()
        # Delay running analysis for a fraction of a second, this gives a better user experience. For example,
        # when selecting an instruction and holding down the "delete" key to delete lots of instructions.
        dro_globals.task_master().start_task(
            "REG_ANALYSIS",
            0.1,
            detailed_register_analyzer.analyze_dro,
            detailed_register_analyzer.cancel,
            [self]
        )



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
            return '0x%02X' % (self.codemap[reg & 0x7F])

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

