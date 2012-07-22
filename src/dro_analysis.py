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
import itertools
import threading

from dro_data import DRO_FILE_V1, DRO_FILE_V2
import dro_globals
from dro_util import DROTrimmerException
import regdata

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
            #print dro_data[longest_match.start:longest_match.end + 1]
            #print dro_data[end_match.start:end_match.end + 1]
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
        dro_data = []
        MIN_DELAY_TO_INCLUDE = 2 # skip delays of 1 ms
        for i, datum in enumerate(dro_song.data):
            reg = datum[0]
            should_include = False
            if reg in (dro_song.short_delay_code,
                       dro_song.long_delay_code):
                if datum[1] >= MIN_DELAY_TO_INCLUDE:
                    should_include = True
            else:
                if dro_song.file_version == DRO_FILE_V2: # sigh
                    reg = dro_song.codemap[reg & 0x7F]
                if reg in range(0xB0, 0xB9):
                    should_include = True
            if should_include:
                dro_data.append(datum)
                original_indexes.append(i)

        result = self.__do_backward_search_analysis(dro_data, original_indexes)
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
        dro_data = dro_song.data
        for i, reg_and_val in enumerate(dro_data):
            reg = reg_and_val[0]
            if reg in (dro_song.short_delay_code,
                       dro_song.long_delay_code):
                if note_on_found:
                    # This is where we want to start, the first delay after the first "note on" instruction
                    start_pos = i
                    break
                else:
                    continue
            if dro_song.file_version == DRO_FILE_V1:
                if reg < 0x05: # skip non-register commands
                    continue
            elif dro_song.file_version == DRO_FILE_V2:
                reg = dro_song.codemap[reg & 0x7F]
            if reg in range(0xB0, 0xB9):
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
        for i in xrange(start_pos + 1, len(dro_data)):
            early_value = dro_data[early_index]
            later_value = dro_data[i]

            if early_value == later_value:
                # Check if we're starting a new match
                if early_index == start_pos:
                    curr_match = self.Match(start=i, end=i, length=0)
                curr_match.length += 1
                curr_match.end = i
                if i == len(dro_data) - 1:
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
        dro_data = dro_song.data
        sections = []
        curr_section = self.Match()
        for i, datum in enumerate(dro_data):
            reg = datum[0]
            if reg not in (dro_song.short_delay_code,
                           dro_song.long_delay_code):
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
            curr_section.end = len(dro_data) - 1
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
        dro_data = dro_song.data
        # Split the data in half and see what the largest matching block is.
        # This will give us an indication on whether or not the song loops, and if so,
        #  where the loop points are.
        sm = difflib.SequenceMatcher()
        tmp_len = len(dro_data) / 2
        tmp_a = dro_data[:tmp_len]
        tmp_b = dro_data[tmp_len:]
        sm.set_seqs(tmp_a, tmp_b)
        #result1 = sm.get_matching_blocks()
        #print result1

        # We have to do "len(dro_data) - tmp_len" because of rounding when
        #  dividing by two earlier.
        result = sm.find_longest_match(0, tmp_len, 0, len(dro_data) - tmp_len)
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
        cmd = dro_data[result[0]][0]
        if dro_song.file_version == DRO_FILE_V2 and cmd not in (dro_song.short_delay_code, dro_song.long_delay_code):
            cmd = dro_song.codemap[cmd & 0x7F]
        if cmd in range(0xB0, 0xB9):
            result_str += ("Note: The first instruction in the matched block was a key on/off. There may be " +
                           "a more appropriate block earlier in the song.\n")

        # Now search for the first delay
        for i, inst in enumerate(dro_data):
            if inst[0] in (dro_song.short_delay_code, dro_song.long_delay_code):
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
            self.__analyze_dro1(dro_song)
        elif dro_song.file_version == DRO_FILE_V2:
            self.__analyze_dro2(dro_song)
        else:
            raise (DROTrimmerException("Unrecognised DRO version: %s. Cannot perform state analysis." %
                                       (dro_song.file_version,)))
        return self.state_descriptions

    def __analyze_dro1(self, dro_song):
        opl_type = self.OPL_TYPE_DRO1_MAP[dro_song.opl_type]
        for cmd_and_val in dro_song.data:
            if self._stop.isSet():
                return
            cmd = cmd_and_val[0]
            if cmd in (dro_song.short_delay_code, dro_song.long_delay_code):
                val = cmd_and_val[1]
                self.state_descriptions.append((self.current_bank, "Delay: %s ms" % (val,)))
                continue
            elif cmd in (0x02, 0x03):
                self.current_bank = cmd - 0x02
                self.state_descriptions.append((self.current_bank, "Bank switch: %s" % (self.current_bank,)))
                continue
            elif cmd == 0x04:
                reg = cmd_and_val[1]
                val = cmd_and_val[2]
            else:
                reg = cmd_and_val[0]
                val = cmd_and_val[1]

            self.state_descriptions.append((self.current_bank,
                                            self.__analyze_and_update_register(self.current_bank, reg, val, opl_type)))

    def __analyze_dro2(self, dro_song):
        opl_type = self.OPL_TYPE_DRO2_MAP[dro_song.opl_type]
        for cmd, val in dro_song.data:
            if self._stop.isSet():
                return
            if cmd in (dro_song.short_delay_code, dro_song.long_delay_code):
                self.state_descriptions.append((self.current_bank, "Delay: %s ms" % val))
                continue
            else:
                self.current_bank = (cmd & 0x80) >> 7
                reg = dro_song.codemap[cmd & 0x7F]
            self.state_descriptions.append((self.current_bank,
                                            self.__analyze_and_update_register(self.current_bank, reg, val, opl_type)))

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
