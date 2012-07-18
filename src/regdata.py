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
#
# Register translation
# Data taken from:
#  http://www.shipbrook.com/jeff/sb.html
#  http://www.gamedev.net/reference/articles/article447.asp
#  http://www.nendai.nagoya-u.ac.jp/global/sys/HTML/S/dev%20sound%20isa%20opl.c.html
#  http://www.shikadi.net/moddingwiki/OPL_chip

registers = {
    0x01: "Test LSI Register / Waveform Select Enable",
    0x02: "Timer 1 Count",
    0x03: "Timer 2 Count",
    0x04: "1: Timer Control Flags (IRQ Reset / Mask / Start)   2: Four-Operator Enable", #  004 (port: base+1):
    0x104: "Four-Operator Enable", # (port: base+3) - I don't think 0x104 or 0x105 will ever be used due to OPL mode implicit in DRO format...?
    #0x05: "2: OPL3 Mode Enable", # (port: base+3)
    0x105: "OPL3 Mode Enable", # (port: base+3)
    0x08: "Speech synthesis mode / Keyboard split note select (CSW / NOTE-SEL)",
    0x20: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
    0x21: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
    0x22: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
    0x23: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
    0x24: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
    0x25: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
    0x26: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
    0x27: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
    0x28: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
    0x29: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
    0x2A: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
    0x2B: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
    0x2C: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
    0x2D: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
    0x2E: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
    0x2F: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
    0x30: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
    0x31: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
    0x32: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
    0x33: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
    0x34: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
    0x35: "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor",
     #0x3F: "", # OPL-3 only?
    0x40: "Key Scale Level / Output Level",
    0x41: "Key Scale Level / Output Level",
    0x42: "Key Scale Level / Output Level",
    0x43: "Key Scale Level / Output Level",
    0x44: "Key Scale Level / Output Level",
    0x45: "Key Scale Level / Output Level",
    0x46: "Key Scale Level / Output Level",
    0x47: "Key Scale Level / Output Level",
    0x48: "Key Scale Level / Output Level",
    0x49: "Key Scale Level / Output Level",
    0x4A: "Key Scale Level / Output Level",
    0x4B: "Key Scale Level / Output Level",
    0x4C: "Key Scale Level / Output Level",
    0x4D: "Key Scale Level / Output Level",
    0x4E: "Key Scale Level / Output Level",
    0x4F: "Key Scale Level / Output Level",
    0x50: "Key Scale Level / Output Level",
    0x51: "Key Scale Level / Output Level",
    0x52: "Key Scale Level / Output Level",
    0x53: "Key Scale Level / Output Level",
    0x54: "Key Scale Level / Output Level",
    0x55: "Key Scale Level / Output Level",
    0x60: "Attack Rate / Decay Rate",
    0x61: "Attack Rate / Decay Rate",
    0x62: "Attack Rate / Decay Rate",
    0x63: "Attack Rate / Decay Rate",
    0x64: "Attack Rate / Decay Rate",
    0x65: "Attack Rate / Decay Rate",
    0x66: "Attack Rate / Decay Rate",
    0x67: "Attack Rate / Decay Rate",
    0x68: "Attack Rate / Decay Rate",
    0x69: "Attack Rate / Decay Rate",
    0x6A: "Attack Rate / Decay Rate",
    0x6B: "Attack Rate / Decay Rate",
    0x6C: "Attack Rate / Decay Rate",
    0x6D: "Attack Rate / Decay Rate",
    0x6E: "Attack Rate / Decay Rate",
    0x6F: "Attack Rate / Decay Rate",
    0x70: "Attack Rate / Decay Rate",
    0x71: "Attack Rate / Decay Rate",
    0x72: "Attack Rate / Decay Rate",
    0x73: "Attack Rate / Decay Rate",
    0x74: "Attack Rate / Decay Rate",
    0x75: "Attack Rate / Decay Rate",
    0x80: "Sustain Level / Release Rate",
    0x81: "Sustain Level / Release Rate",
    0x82: "Sustain Level / Release Rate",
    0x83: "Sustain Level / Release Rate",
    0x84: "Sustain Level / Release Rate",
    0x85: "Sustain Level / Release Rate",
    0x86: "Sustain Level / Release Rate",
    0x87: "Sustain Level / Release Rate",
    0x88: "Sustain Level / Release Rate",
    0x89: "Sustain Level / Release Rate",
    0x8A: "Sustain Level / Release Rate",
    0x8B: "Sustain Level / Release Rate",
    0x8C: "Sustain Level / Release Rate",
    0x8D: "Sustain Level / Release Rate",
    0x8E: "Sustain Level / Release Rate",
    0x8F: "Sustain Level / Release Rate",
    0x90: "Sustain Level / Release Rate",
    0x91: "Sustain Level / Release Rate",
    0x92: "Sustain Level / Release Rate",
    0x93: "Sustain Level / Release Rate",
    0x94: "Sustain Level / Release Rate",
    0x95: "Sustain Level / Release Rate",
    0xA0: "Frequency Number (low 8 bits)",
    0xA1: "Frequency Number (low 8 bits)",
    0xA2: "Frequency Number (low 8 bits)",
    0xA3: "Frequency Number (low 8 bits)",
    0xA4: "Frequency Number (low 8 bits)",
    0xA5: "Frequency Number (low 8 bits)",
    0xA6: "Frequency Number (low 8 bits)",
    0xA7: "Frequency Number (low 8 bits)",
    0xA8: "Frequency Number (low 8 bits)",
    0xB0: "Key On / Octave / Frequency (high 2 bits)",
    0xB1: "Key On / Octave / Frequency (high 2 bits)",
    0xB2: "Key On / Octave / Frequency (high 2 bits)",
    0xB3: "Key On / Octave / Frequency (high 2 bits)",
    0xB4: "Key On / Octave / Frequency (high 2 bits)",
    0xB5: "Key On / Octave / Frequency (high 2 bits)",
    0xB6: "Key On / Octave / Frequency (high 2 bits)",
    0xB7: "Key On / Octave / Frequency (high 2 bits)",
    0xB8: "Key On / Octave / Frequency (high 2 bits)",
    0xBD: "AM depth / Vibrato depth / Percussion control",
    0xC0: "Feedback strength / Panning / Synthesis type",
    0xC1: "Feedback strength / Panning / Synthesis type",
    0xC2: "Feedback strength / Panning / Synthesis type",
    0xC3: "Feedback strength / Panning / Synthesis type",
    0xC4: "Feedback strength / Panning / Synthesis type",
    0xC5: "Feedback strength / Panning / Synthesis type",
    0xC6: "Feedback strength / Panning / Synthesis type",
    0xC7: "Feedback strength / Panning / Synthesis type",
    0xC8: "Feedback strength / Panning / Synthesis type",
    0xE0: "Waveform Select",
    0xE1: "Waveform Select",
    0xE2: "Waveform Select",
    0xE3: "Waveform Select",
    0xE4: "Waveform Select",
    0xE5: "Waveform Select",
    0xE6: "Waveform Select",
    0xE7: "Waveform Select",
    0xE8: "Waveform Select",
    0xE9: "Waveform Select",
    0xEA: "Waveform Select",
    0xEB: "Waveform Select",
    0xEC: "Waveform Select",
    0xED: "Waveform Select",
    0xEE: "Waveform Select",
    0xEF: "Waveform Select",
    0xF0: "Waveform Select",
    0xF1: "Waveform Select",
    0xF2: "Waveform Select",
    0xF3: "Waveform Select",
    0xF4: "Waveform Select",
    0xF5: "Waveform Select"
}

class RegisterBitmask(object):
    def __init__(self, description, mask):
        self.description = description
        self.mask = mask

# What follows is a bit lazy.
# (Sorry for the ugly bitmasks, Python 2.5 has no binary literals)
register_bitmask_lookup = {
    "Test LSI Register / Waveform Select Enable" : (
        RegisterBitmask("Waveform Select Enable", int('00100000', 2)),
        RegisterBitmask("Test LSI Register", int('00011111', 2)),
    ),
    "Timer 1 Count" : (
        RegisterBitmask("Timer 1 Count", int('11111111', 2)),
    ),
    "Timer 2 Count" : (
        RegisterBitmask("Timer 2 Count", int('11111111', 2)),
    ),
    "1: Timer Control Flags (IRQ Reset / Mask / Start)   2: Four-Operator Enable" : ( # TODO: revise registers 004 and 104 - doesn't work yet.
        RegisterBitmask("IRQ Reset", int('10000000', 2)),
        RegisterBitmask("Timer 1 Mask", int('01000000', 2)),
        RegisterBitmask("Timer 2 Mask", int('00100000', 2)),
        RegisterBitmask("Timer 1 Start", int('00000010', 2)),
        RegisterBitmask("Timer 2 Start", int('00000001', 2)),
    ),
    "Four-Operator Enable" : ( # TODO: revise registers 004 and 104 - doesn't work yet.
        RegisterBitmask("4-Operator enable for ch. 11 & 14", int('00100000', 2)),
        RegisterBitmask("4-Operator enable for ch. 10 & 13", int('00010000', 2)),
        RegisterBitmask("4-Operator enable for ch. 9 & 12", int('00001000', 2)),
        RegisterBitmask("4-Operator enable for ch. 2 & 5", int('00000100', 2)),
        RegisterBitmask("4-Operator enable for ch. 1 & 4", int('00000010', 2)),
        RegisterBitmask("4-Operator enable for ch. 0 & 3", int('00000001', 2)),
    ),
    "OPL3 Mode Enable" : (
        RegisterBitmask("OPL3 Mode Enable", int('00000001', 2)),
    ),
    "Speech synthesis mode / Keyboard split note select (CSW / NOTE-SEL)" : (
        RegisterBitmask("CSW (Speech synthesis mode)", int('10000000', 2)),
        RegisterBitmask("Keyboard split", int('01000000', 2)),
        # NOTE: documentation refers to an F-Number, what is it?
        # I think it could be the "Frequency Multiplication Factor"?
    ),
    "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor" : (
        RegisterBitmask("Tremolo", int('10000000', 2)),
        RegisterBitmask("Vibrato", int('01000000', 2)),
        RegisterBitmask("Sustain", int('00100000', 2)),
        RegisterBitmask("KSR (envelope scaling)", int('00010000', 2)),
        RegisterBitmask("Frequency Multiplication Factor", int('00001111', 2)),
    ),
    "Key Scale Level / Output Level" : (
        RegisterBitmask("Key Scale Level", int('11000000', 2)),
        RegisterBitmask("Output Level", int('00111111', 2)),
    ),
    "Attack Rate / Decay Rate" : (
        RegisterBitmask("Attack Rate", int('11110000', 2)),
        RegisterBitmask("Decay Rate", int('00001111', 2)),
    ),
    "Sustain Level / Release Rate" : (
        RegisterBitmask("Sustain Level", int('11110000', 2)),
        RegisterBitmask("Release Rate", int('00001111', 2)),
    ),
    "Frequency Number (low 8 bits)" : (
        RegisterBitmask("Frequency Number (low 8 bits)", int('11111111', 2)),
    ),
    "Key On / Octave / Frequency (high 2 bits)" : (
        RegisterBitmask("Key On", int('00100000', 2)),
        RegisterBitmask("Octave", int('00011100', 2)),
        RegisterBitmask("Frequency (high 2 bits)", int('00000011', 2)),
    ),
    "AM depth / Vibrato depth / Percussion control" : (
        RegisterBitmask("Tremolo depth", int('10000000', 2)),
        RegisterBitmask("Vibrato depth", int('01000000', 2)),
        RegisterBitmask("Percussion mode", int('00100000', 2)),
        RegisterBitmask("BD", int('00010000', 2)),
        RegisterBitmask("SD", int('00001000', 2)),
        RegisterBitmask("TT", int('00000100', 2)),
        RegisterBitmask("CY", int('00000010', 2)),
        RegisterBitmask("HH", int('00000001', 2)),
    ),
    "Feedback strength / Panning / Synthesis type" : (
        RegisterBitmask("Pan right", int('00100000', 2)),
        RegisterBitmask("Pan left", int('00010000', 2)),
        RegisterBitmask("Feedback", int('00001110', 2)),
        RegisterBitmask("Synthesis type", int('00000001', 2)),
    ),
    "Waveform Select" : (
        RegisterBitmask("Waveform Select", int('00000111', 2)),
    ),
}

