#!/usr/bin/python
#
#    Use, distribution, and modification of the DRO Trimmer binaries, source code,
#    or documentation, is subject to the terms of the MIT license, as below.
#
#    Copyright (c) 2008 - 2014 Laurence Dougal Myers
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

from collections import defaultdict
import difflib
import itertools
import threading

import dro_data
from dro_util import DROTrimmerException, read_config
import regdata

# Duplicated from dro_data to avoid circular import. TODO: move to common location.
DRO_FILE_V1 = 1
DRO_FILE_V2 = 2


class DROTotalDelayCalculator(object):
    def sum_delay(self, dro_song):
        """
        @type dro_song: DROSong
        """
        # Bleh
        calc_delay = 0
        for inst in dro_song.data:
            if inst.inst_type == dro_data.DROInstruction.T_DELAY:
                calc_delay += inst.value
        return calc_delay


class DROTotalDelayWithWriteDelayCalculator(object):
    def __init__(self):
        try:
            config = read_config()
            self.chip_write_delay = config.getfloat("audio", "chip_write_delay")
        except Exception, e:
            print "Could not read audio settings from drotrim.ini, using default value for chip write delay. (Error: %s)" % e
            self.chip_write_delay = 0

    def sum_delay(self, dro_song):
        """
        @type dro_song: DROSong
        """
        calc_delay = 0 # milliseconds
        total_write_delay = 0 # microseconds
        for inst in dro_song.data:
            if inst.inst_type == dro_data.DROInstruction.T_DELAY:
                calc_delay += inst.value
            elif inst.inst_type == dro_data.DROInstruction.T_REGISTER:
                total_write_delay += self.chip_write_delay
        calc_delay += total_write_delay // 1000
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
        inst = dro_song.data[0]
        if inst.inst_type == dro_data.DROInstruction.T_DELAY:
            self.result = True


class DROTotalDelayMismatchAnalyzer(object):
    def __init__(self):
        self.result = False

    def analyze_dro(self, dro_song):
        """
        @type dro_song: DROSong
        """
        calc_delay = DROTotalDelayCalculator().sum_delay(dro_song)
        self.result = calc_delay != dro_song.ms_length


class DROLoopAnalyzer(object):
    class Match(object):
        def __init__(self, start=None, end=None, length=0):
            self.start = start
            self.end = end
            self.length = length

        def __repr__(self):
            return "Match(start=%s, end=%s, length=%s)" % (self.start, self.end, self.length)

    class AnalysisResult(object):
        def __init__(self, description, result):
            self.description = description
            self.result = result

        def __str__(self):
            return "%s\n\n%s" % (self.description, self.result)

    def __init__(self):
        self.analysis_methods = [
            self.analyze_earliest_end_match,
            self.analyze_earliest_end_delay_and_note_match,
            self.analyze_latest_start_match,
            self.analyze_longest_instruction_blocks,
            self.analyze_seqeunce_matcher
        ]

    def num_analyses(self):
        return len(self.analysis_methods)

    def analyze_dro(self, dro_song):
        """
        @type dro_song: DROSong
        """
        results = []
        for analysis_method in self.analysis_methods:
            results.append(analysis_method(dro_song))
        return results

    def __do_backward_search_analysis(self, dro_data, original_indexes):
        """From the index second from the end, compare to the last value at the end.
        If the current value matches the end value, compare all
        values preceding the current value against all values
        preceding the end value.
        (This is a fairly naive approach.)
        Example:
          [0, 1, 2, 3, 1, 2]
                       ^  ^
          [0, 1, 2, 3, 1, 2]
                       ^  ^
          [0, 1, 2, 3, 1, 2]
                    ^     ^
          [0, 1, 2, 3, 1, 2]
                 ^        ^
          [0, 1, 2, 3, 1, 2]
              ^--/     ^--/
           result:
           section 1: start = 1, end = 2, length = 2
           section 2: start = 4, end = 5, length = 2
        """
        result = ""
        curr_match = None
        end_match = self.Match()
        longest_match = self.Match()
        end_index = len(dro_data) - 1
        later_index = end_index
        match_ended = False
        # Iterate in reverse, also getting the index.
        for i, curr_value in itertools.izip(xrange(end_index, -1, -1), (reversed(dro_data))):
            # Ignore the end value
            if i == end_index:
                continue
            later_value = dro_data[later_index]
            if curr_value == later_value:
                # Check if we're starting a new match
                if later_index == end_index:
                    curr_match = self.Match(start=i, end=i, length=0)
                curr_match.length += 1
                curr_match.start = i
                if i == 0:
                    match_ended = True
            elif curr_match is not None:
                match_ended = True

            # Sequence has ended, and it's longer than the longest match so far,
            #  or it's the same length as the longest match but has an earlier
            #  starting point.
            if match_ended:
                if (curr_match.length > longest_match.length or
                    (curr_match.length == longest_match.length and
                     curr_match.start < longest_match.start)):
                    longest_match = curr_match
                    end_match = self.Match(
                        start=later_index + 1,
                        end=end_index,
                        length=curr_match.length
                    )
                curr_match = None
                later_index = end_index
                match_ended = False

            # If we're matching, decrement the end index.
            if curr_match is not None:
                later_index -= 1

        result += "My conclusions:\n"
        if longest_match.start is None or longest_match.end is None or longest_match.length == 0:
            result += "No match found. I'm sorry.\n"
        else:
            # Convert matching indexes to original indexes
            longest_match = self.Match(
                start=original_indexes[longest_match.start],
                end=original_indexes[longest_match.end],
                length=original_indexes[longest_match.end] - original_indexes[longest_match.start] + 1
            )
            end_match = self.Match(
                start=original_indexes[end_match.start],
                end=original_indexes[end_match.end],
                length=original_indexes[end_match.end] - original_indexes[end_match.start] + 1
            )
            result += ("Loop section 1: start=%s, end=%s, length=%s.\n" %
                       (longest_match.start, longest_match.end, longest_match.length))
            result += ("Loop section 2: start=%s, end=%s, length=%s.\n" %
                       (end_match.start, end_match.end, end_match.length))

        return result

    def analyze_earliest_end_match(self, dro_song):
        """
        Goes through the data backwards. Finds the "earliest" sequence of instructions that
        matches the sequence of instructions at the end of the song.
        """
        dro_data = dro_song.data
        original_indexes = range(len(dro_song.data))
        result = self.__do_backward_search_analysis(dro_data, original_indexes)
        return self.AnalysisResult("Earliest match to end", result)

    def analyze_earliest_end_delay_and_note_match(self, dro_song):
        """
        Goes through the data backwards. Finds the "earliest" sequence of instructions that
        matches the sequence of instructions at the end of the song. Only looks at
        delay and note on/off instructions.
        """

        # First, go through the data and only keep note on/off instructions and delays.
        # This is because sometimes the looped information has slightly different
        # data.
        original_indexes = []
        dro_data_copy = dro_song.data.shallow_copy()

        MIN_DELAY_TO_INCLUDE = 2 # skip delays of 1 ms
        for i, inst in enumerate(dro_song.data):
            should_include = False
            if inst.inst_type == dro_data.DROInstruction.T_DELAY:
                if inst.value >= MIN_DELAY_TO_INCLUDE:
                    should_include = True
            elif inst.inst_type == dro_data.DROInstruction.T_REGISTER:
                if inst.command in range(0xB0, 0xB9):
                    should_include = True
            if should_include:
                dro_data_copy.append_raw(dro_song.data.get_raw(i))
                original_indexes.append(i)

        result = self.__do_backward_search_analysis(dro_data_copy, original_indexes)
        return self.AnalysisResult("Earliest match to end (delays and note on/off only)", result)

    def analyze_latest_start_match(self, dro_song):
        """
        Goes through the data forwards. Finds the "latest" sequence of instructions that
        matches the sequence of instructions towards the start of the song, after the
        first note on and the first delay instructions.
        """
        result = ""
        # First, find our starting point.
        note_on_found = False
        start_pos = 0
        for i, inst in enumerate(dro_song.data):
            if inst.inst_type == dro_data.DROInstruction.T_DELAY:
                if note_on_found:
                    # This is where we want to start, the first delay after the first "note on" instruction
                    start_pos = i
                    break
                else:
                    continue
            elif (inst.inst_type == dro_data.DROInstruction.T_REGISTER and
                    inst.value in range(0xB0, 0xB9)):
                note_on_found = True

        if start_pos == 0:
            return self.AnalysisResult("Latest match to start", "Forward search couldn't find a place to start.\n")

        # Next, do the search for reals.
        # (This is very similar to method on & two, but goes forwards instead)
        early_index = start_pos
        curr_match = None
        longest_match = self.Match()
        start_match = self.Match()
        match_ended = False
        for i in xrange(start_pos + 1, len(dro_song.data)):
            early_value = dro_song.data[early_index]
            later_value = dro_song.data[i]

            if early_value == later_value:
                # Check if we're starting a new match
                if early_index == start_pos:
                    curr_match = self.Match(start=i, end=i, length=0)
                curr_match.length += 1
                curr_match.end = i
                if i == len(dro_song.data) - 1:
                    match_ended = True
            elif curr_match is not None:
                match_ended = True

            # Sequence has ended, and it's longer than the longest match so far,
            #  or it's the same length as the longest match but has a later
            #  starting point.
            if match_ended:
                if (curr_match.length > longest_match.length or
                    (curr_match.length == longest_match.length and
                     curr_match.start > longest_match.start)):
                    longest_match = curr_match
                    start_match = self.Match(
                        start=start_pos,
                        end=early_index - 1,
                        length=curr_match.length
                    )
                curr_match = None
                early_index = start_pos
                match_ended = False

            # If we're matching, increment the start index.
            if curr_match is not None:
                early_index += 1

        result += "My conclusions:\n"
        if longest_match.start is None or longest_match.end is None or longest_match.length == 0:
            result += "No match found. I'm sorry.\n"
        else:
            result += ("Loop section 1: start=%s, end=%s, length=%s.\n" %
                       (start_match.start, start_match.end, start_match.length))
            result += ("Loop section 2: start=%s, end=%s, length=%s.\n" %
                       (longest_match.start, longest_match.end, longest_match.length))

        return self.AnalysisResult("Latest match to start", result)

    def analyze_longest_instruction_blocks(self, dro_song):
        """
        Finds the the 15 longest blocks of instructions, separated by delay instructions.
        Excludes the first block at the beginning of the song (which is usually just
        register initialization, in DRO 2).
        """
        # This is the shortest length that we want to keep track of.
        notable_threshold = 10

        # Try and find sections with large chunks of instructions before a delay.
        sections = []
        curr_section = self.Match()
        for i, inst in enumerate(dro_song.data):
            if inst.inst_type != dro_data.DROInstruction.T_DELAY:
                if curr_section.start is None:
                    curr_section.start = i
                curr_section.length += 1
            else:
                curr_section.end = i - 1
                if curr_section.length >= notable_threshold:
                    sections.append(curr_section)
                curr_section = self.Match()

        # If we've got a hanging section left over, finish it off.
        if curr_section.start is not None and curr_section.end is None:
            curr_section.end = len(dro_song.data) - 1
            if curr_section.length >= notable_threshold:
                sections.append(curr_section)

        sections.sort(key=lambda m: m.length, reverse=True)
        num_to_display = min(len(sections), 15)
        if len(sections) > 1 and sections[0].start == 0:
            interesting_sections = sections[1:num_to_display + 1] # skip the first one since it's the start of the song
        else:
            interesting_sections = sections[0:num_to_display]
        sections_string = "\n".join(str(sec) for sec in interesting_sections)
        result = "Interesting sections (by size):\n%s" % (sections_string,)
        result += "\n\n"
        interesting_sections.sort(key=lambda m: m.start, reverse=True)
        sections_string = "\n".join(str(sec) for sec in interesting_sections)
        result += "Interesting sections (by position):\n%s" % (sections_string,)
        return self.AnalysisResult("Longest instruction blocks", result)

    def analyze_seqeunce_matcher(self, dro_song):
        """
        Splits the data in half, and uses Python's difflib.SequenceMatcher to
        find the longest matching blocks in each half.
        """
        result_str = ""
        # Split the data in half and see what the largest matching block is.
        # This will give us an indication on whether or not the song loops, and if so,
        #  where the loop points are.
        sm = difflib.SequenceMatcher()
        tmp_len = len(dro_song.data) / 2
        tmp_a = dro_song.data[:tmp_len]
        tmp_b = dro_song.data[tmp_len:]
        sm.set_seqs(tmp_a, tmp_b)
        #result1 = sm.get_matching_blocks()
        #print result1

        # We have to do "len(dro_song.data) - tmp_len" because of rounding when
        #  dividing by two earlier.
        result = sm.find_longest_match(0, tmp_len, 0, len(dro_song.data) - tmp_len)
        result_str += ("Result of analysis:\n longest block = " + str(result[2]) +
                       ",\n start first half = " + str(result[0]) +
                       ",\n start second half = " + str(result[1] + tmp_len) + "\n")

        # TODO: Find the first instance of the data block dro_data[result[0]:result[1] + tmp_len]?
        # No. This is not the problem. The problem is that the longest block could be because
        #  it starts with a note-off, whereas the first block will not have that note off. Every
        #  loop iteration, however, will have that note off, and so it will have a longer matching
        #  block.
        # Taking this into consideration, notify the user that if the first instruction
        #  in the matched block is a note off, there may be an earlier block that is more
        #  suitable for trimming.

        # If first instruction is note off, alert user
        inst = dro_song.data[result[0]]
        if (inst.inst_type == dro_data.DROInstruction.T_REGISTER and
            inst.value in range(0xB0, 0xB9)):
            result_str += ("Note: The first instruction in the matched block was a key on/off. There may be " +
                           "a more appropriate block earlier in the song.\n")

        # Now search for the first delay
        for i, inst in enumerate(dro_song.data):
            if inst.inst_type == dro_data.DROInstruction.T_DELAY:
                result_str += ("First delay at pos = " + str(i) + "\n")
                break

        return self.AnalysisResult("Halved sequence match", result_str)


class DRODetailedRegisterAnalyzer(object):
    # TODO: output channels and banks in the table.
    OPL_TYPE_OPL2, OPL_TYPE_DUAL_OPL2, OPL_TYPE_OPL3 = range(3)

    def __init__(self):
        self.state_descriptions = []
        self.current_bank = 0
        self.current_state = None
        self.OPL_TYPE_DRO1_MAP = [
            self.OPL_TYPE_OPL2,
            self.OPL_TYPE_OPL3,
            self.OPL_TYPE_DUAL_OPL2
        ]
        self.OPL_TYPE_DRO2_MAP = [
            self.OPL_TYPE_OPL2,
            self.OPL_TYPE_DUAL_OPL2,
            self.OPL_TYPE_OPL3
        ] # a bit pointless, but added for consistency.
        self._stop = threading.Event()

    def cancel(self):
        self._stop.set()

    def analyze_dro(self, dro_song):
        self.state_descriptions = []
        self.current_state = [None] * 0x1FF
        if dro_song.file_version == DRO_FILE_V1:
            opl_type = self.OPL_TYPE_DRO1_MAP[dro_song.opl_type]
        elif dro_song.file_version == DRO_FILE_V2:
            opl_type = self.OPL_TYPE_DRO2_MAP[dro_song.opl_type]
        else:
            raise (DROTrimmerException("Unrecognised DRO version: %s. Cannot perform state analysis." %
                                       (dro_song.file_version,)))
        # Wait for the data lock to become available.
        with dro_song.data_lock:
            for inst in dro_song.data:
                if self._stop.isSet():
                    return
                if inst.inst_type == dro_data.DROInstruction.T_DELAY:
                    self.state_descriptions.append(
                        (self.current_bank, "Delay: %s ms" % (inst.value,)))
                elif inst.inst_type == dro_data.DROInstruction.T_BANK_SWITCH:
                    self.current_bank = inst.value
                    self.state_descriptions.append(
                        (self.current_bank, "Bank switch: %s" % (("low", "high")[self.current_bank],))
                    )
                else:
                    if inst.bank is not None:
                        self.current_bank = inst.bank
                    desc = self.__analyze_and_update_register(self.current_bank,
                                                              inst.command,
                                                              inst.value,
                                                              opl_type)
                    self.state_descriptions.append(
                        (self.current_bank, desc))
        return self.state_descriptions

    def __analyze_and_update_register(self, bank, reg, val, opl_type):
        try:
            if bank and regdata.registers.has_key(0x100 | reg):
                register_description = regdata.registers[0x100 | reg]
            else:
                register_description = regdata.registers[reg]
        except Exception:
            return "Unknown register: %s" % (reg,)

        reg_and_bank = (bank << 8) | reg
        old_val = self.current_state[reg_and_bank]

        changed_desc = []
        bitmasks = regdata.register_bitmask_lookup[register_description]
        for bm in bitmasks:
            # Output the description for this bitmask, if the old value is None (start of the song), or the
            #  value has changed.
            if old_val is None or (bm.mask & old_val) ^ (bm.mask & val):
                changed_desc.append(bm.description)

        self.current_state[reg_and_bank] = val

        return ' / '.join(changed_desc) if len(changed_desc) else '(no changes)'


class DRORegisterUsageAnalyzer(object):
    PERC_CHANNEL = 0xBD

    def __init__(self, detailed_percussion_analysis=False):
        self.detailed_percussion_analysis = detailed_percussion_analysis
        self.perc_usage = defaultdict(bool)
        self.usage = defaultdict(int)

    def analyze_dro(self, dro_song):
        """Returns two dicts. First dict is register usage, second dictt is perc inst usage.
        Keys are registers, with the bank set in bit 0x100. e.g.
         register 0xDB on the high bank will return a key of 0x1DB.
        Values are the number of times that register is used in the DRO file.

        Perc usage dict:
        Keys are bitmasks (powers of 2), values are "True" if that bit was set during
        the analysis."""
        self.usage = defaultdict(int)
        self.perc_usage = defaultdict(bool)
        perc_bitmasks = regdata.register_bitmask_lookup[regdata.registers[self.PERC_CHANNEL]]
        with dro_song.data_lock:
            bank = 0
            for inst in dro_song.data:
                if inst.bank is not None:
                    bank = inst.bank
                if inst.inst_type == dro_data.DROInstruction.T_BANK_SWITCH:
                    bank = inst.value
                if inst.inst_type == dro_data.DROInstruction.T_REGISTER:
                    self.usage[(bank << 8) | inst.command] += 1
                    if inst.command == self.PERC_CHANNEL and self.detailed_percussion_analysis:
                        # Go through all bitmasks, mark any usages.
                        for i, pb in enumerate(perc_bitmasks):
                            if inst.value & pb.mask:
                                self.perc_usage[(bank << 8) | pb.mask] = True
        return self.usage, self.perc_usage


class DRODebugAnalyzer(object):
    def __init__(self):
        pass

    def analyze_dro(self, dro_song):
        """Prints out the DRO song info, then prints each instruction."""
        with dro_song.data_lock:
            print dro_song
            for inst in dro_song.data:
                print inst


class DROSimpleNoteAnalyser(object):
    PITCH_REGISTERS = frozenset(range(0xA0, 0xA8 + 1))
    KEY_ON_REGISTERS = frozenset(range(0xB0, 0xB8 + 1))
    CHANNELS_PER_BANK = 9

    class NoteStatus(object):
        PITCH_MAP = {
            0x015B : ' C',
            0x016B : 'C#',
            0x0181 : ' D',
            0x0198 : 'D#',
            0x01B0 : ' E',
            0x01CA : ' F',
            0x01E5 : 'F#',
            0x0202 : ' G',
            0x0220 : 'G#',
            0x0241 : ' A',
            0x0263 : 'A#',
            0x0287 : ' B',
            0x02AE : ' C'
        }

        def __init__(self, channel=None, note_status_to_clone=None):
            if note_status_to_clone is not None:
                self.channel = note_status_to_clone.channel
                self.pitch = note_status_to_clone.pitch
                self.octave = note_status_to_clone.octave
                self.on = note_status_to_clone.on
            else:
                self.channel = channel
                self.pitch = 0
                self.octave = 0
                self.on = False

        def __str__(self):
            # 0x241 = 440.0 hz
            # 0x241 = 577
            # 24.7 hz between notes
            # approx 1.31 per hz
            closest_value = min(self.PITCH_MAP.keys(), key=lambda x: abs(x - self.pitch))
            note_name = "%s-%s" % (self.PITCH_MAP[closest_value], self.octave)
            return "(ch: %s, pitch: %x, oct: %s, note: %s)" % (self.channel, self.pitch, self.octave, note_name)

    def analyze_dro(self, dro_song):
        """
        Returns a list of of "Note on" pitch values (as NoteStatus objects), containing one list per channel.
        Ignores pitch bends and other pitch changes while a note is on.

        @type dro_song: DROSong
        """
        channel_notes = [DROSimpleNoteAnalyser.NoteStatus(channel=i + 1) for i in xrange(DROSimpleNoteAnalyser.CHANNELS_PER_BANK * 2)]
        output = [[] for i in xrange(DROSimpleNoteAnalyser.CHANNELS_PER_BANK * 2)]
        with dro_song.data_lock:
            for inst in dro_song.data:
                # Ignore non-register stuff.
                if inst.inst_type != dro_data.DROInstruction.T_REGISTER:
                    continue
                # If it's A0 - A8, update the pitch
                elif inst.command in DROSimpleNoteAnalyser.PITCH_REGISTERS:
                    note_status = self.get_channel_status(channel_notes, inst)
                    note_status.pitch = (note_status.pitch & 0xFF00) | inst.value
                # If it's B0 - B8, update the pitch and note on/off
                elif inst.command in DROSimpleNoteAnalyser.KEY_ON_REGISTERS:
                    note_status = self.get_channel_status(channel_notes, inst)
                    note_status.pitch = (note_status.pitch & 0x00FF) | ((inst.value & 0x03) << 8)
                    note_status.octave = (inst.value & 0x1C) >> 2
                    orig_on_value = note_status.on
                    note_status.on = (inst.value & 0x20) > 0
                    # If note on status changes, make a new entry in the output list
                    if note_status.on ^ orig_on_value and note_status.on:
                        output[note_status.channel - 1].append(DROSimpleNoteAnalyser.NoteStatus(note_status_to_clone=note_status))
        return output

    def get_channel_status(self, channel_notes, inst):
        channel_index = (inst.command & 0x0F) + (inst.bank * DROSimpleNoteAnalyser.CHANNELS_PER_BANK)
        return channel_notes[channel_index]
