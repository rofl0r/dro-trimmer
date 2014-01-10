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

import array
import dro_io
import dro_data


def generate_registers_to_init():
    registers_to_init = [0x01, 0x04, 0x05, 0x08, 0xBD]
    operator_bases = (0x20, 0x40, 0x60, 0x80, 0xE0)
    for i in xrange(24):
        if (i & 7) < 6:
            for operator_base in operator_bases:
                registers_to_init.append(operator_base + i)
    channel_bases = (0xA0, 0xB0, 0xC0)
    for i in xrange(9):
        for channel_base in channel_bases:
            registers_to_init.append(channel_base + i)
    return registers_to_init


class DroCapture(object):
    REGISTERS_TO_INIT = generate_registers_to_init()

    def __init__(self):
        self.short_delay_code = len(DroCapture.REGISTERS_TO_INIT)
        self.long_delay_code = len(DroCapture.REGISTERS_TO_INIT) + 1
        self.code_map = {}
        for i, register in enumerate(DroCapture.REGISTERS_TO_INIT):
            self.code_map[register] = i
        self.length_ms = 0
        self._bank = 0
        self.data = array.array('B')
        self.opl_type = None
        self.file_name = None

    def open(self, dro_song):
        self.opl_type = dro_song.opl_type
        if self.file_name is None:
            self.file_name = "{}.out.dro".format(dro_song.name)
        if dro_song.file_version == dro_data.DRO_FILE_V1:
            self.initialise_registers()
        self.bank = 0

    def set_output_fname(self, output_fname):
        self.file_name = "{}.out.dro".format(output_fname)

    @property
    def bank(self):
        return self._bank

    @bank.setter
    def bank(self, value):
        self._bank = value

    def write(self, register, value):
        code = self.code_map[register] | (self.bank << 7)
        self.data.append(code)
        self.data.append(value)

    def render(self, ms_to_render):
        if not ms_to_render:
            return
        self.length_ms += ms_to_render
        long_delays, short_delays = divmod(ms_to_render, 256)
        while long_delays > 0:
            delays_to_write = min(long_delays, 255)
            self.data.append(self.long_delay_code)
            self.data.append(delays_to_write - 1)
            long_delays -= delays_to_write
        if short_delays:
            self.data.append(self.short_delay_code)
            self.data.append(short_delays - 1)

    def render_chip_delay(self):
        pass # do nothing

    def clear_chip_delay_drift(self):
        pass # do nothing

    def stop(self):
        codelist = sorted(self.code_map.keys(), key=lambda key: self.code_map[key])

        data_wrapper = dro_data.DRODataV2()
        data_wrapper.data = self.data
        data_wrapper.codemap = codelist
        data_wrapper.short_delay_code = self.short_delay_code
        data_wrapper.long_delay_code = self.long_delay_code
        data_wrapper.delay_codes = (self.short_delay_code, self.long_delay_code)

        song_wrapper = dro_data.DROSongV2(
            dro_io.DRO_FILE_V2,
            self.file_name,
            data_wrapper,
            self.length_ms,
            self.opl_type,
            codelist,
            self.short_delay_code,
            self.long_delay_code
        )

        dro_io.DroFileIO().write(self.file_name, song_wrapper)

    def initialise_registers(self):
        self.bank = 0
        for register in DroCapture.REGISTERS_TO_INIT:
            if register == 5:
                continue # reg 5 only exists in the high bank
            self.write(register, 0)
        if self.opl_type > 0:
            self.bank = 1
            for register in DroCapture.REGISTERS_TO_INIT:
                self.write(register, 0)
            self.bank = 0
