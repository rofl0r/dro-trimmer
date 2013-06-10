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
import math
import optparse
import os
import sys
import time
import dro_analysis
import dro_globals
import dro_io
import dro_player
import dro_util

def __split_percussion_channel(player, dro_song, bank_num, perc_usage):
    PERC_NAME_MAP = [
        "HH",
        "CY",
        "TT",
        "SD",
        "BD"
    ]

    # Ignore high bits
    percs = sorted([p for p in perc_usage.keys() if perc_usage[p] and p <= 16])
    channel = (bank_num << 8) | 0xBD
    channel_num = (channel & 0xFF) - 0xAF
    if not len(percs):
        print "Skipping bank %01i, perc channel" % (bank_num,)
        return
    for p in percs:
        inst_num = int(math.log(p, 2))
        player.reset()
        player.active_channels = set([(bank_num << 8) | channel])
        player.active_percussion = [0xE0, 0xE0]
        player.active_percussion[bank_num] = 0xE0 | p
        player.set_wav_fname("%s.%01i.%02i.%s.wav" % (dro_song.name, bank_num, channel_num, PERC_NAME_MAP[inst_num]))
        player.play()
        while player.is_playing:
            sys.stdout.write("\r" + dro_util.ms_to_timestr(player.time_elapsed) + " / " + dro_util.ms_to_timestr(dro_song.ms_length))
            sys.stdout.flush()
            time.sleep(0.05)
        sys.stdout.write("\r" + dro_util.ms_to_timestr(dro_song.ms_length) + " / " + dro_util.ms_to_timestr(dro_song.ms_length))
        print " - Finished rendering percussion %01i - %s" % (inst_num + 1,
            PERC_NAME_MAP[inst_num])
    print "Finished rendering bank %01i, perc channel" % (bank_num,)

def split_tracks(player, dro_song, isolate_percussion=False):
    # First, analyse to identify channels that aren't used.
    usage_analyzer = dro_analysis.DRORegisterUsageAnalyzer(detailed_percussion_analysis=True)
    usage, perc_usage = usage_analyzer.analyze_dro(dro_song)
    channels_to_render = sorted(list(player.CHANNEL_REGISTERS)) + [0xBD, 0x1BD]
    if dro_song.OPL_TYPE_MAP[dro_song.opl_type] == "OPL-2":
        channels_to_render = [ctr for ctr in channels_to_render if ctr < 0x100]
    for channel in channels_to_render:
        channel_num = (channel & 0xFF) - 0xAF
        bank_num = (channel & 0x100) >> 8
        if usage[channel] == 0:
            print "Skipping bank %01s, channel %02s" % (bank_num, channel_num,)
            continue
        if isolate_percussion and (channel & 0xFF) == 0xBD:
            __split_percussion_channel(player, dro_song, bank_num, perc_usage)
        else:
            player.reset()
            player.active_channels = set([channel])
            player.active_percussion = [0xE0, 0xE0] # allow some values sent to 0xBD
            if (channel & 0xFF) == 0xBD:
                player.active_percussion[bank_num] = 0xFF
            player.set_wav_fname("%s.%01i.%02i.wav" % (dro_song.name, bank_num, channel_num))
            player.play()
            while player.is_playing:
                sys.stdout.write("\r" + dro_util.ms_to_timestr(player.time_elapsed) + " / " + dro_util.ms_to_timestr(dro_song.ms_length))
                sys.stdout.flush()
                time.sleep(0.05)
            sys.stdout.write("\r" + dro_util.ms_to_timestr(dro_song.ms_length) + " / " + dro_util.ms_to_timestr(dro_song.ms_length))
            print " - Finished rendering bank %01i, channel %02i" % (bank_num, channel_num,)
    print "Done!"

def __parse_arguments():
    usage = ("Usage: %prog [options] dro_file\n\n" +
             "Renders a DRO song into multiple WAV files, one file per channel used.")
    version = dro_globals.g_app_version
    oparser = optparse.OptionParser(usage, version=version)
    oparser.add_option("-p", "--preserve-panning", action="store_true", dest="preserve_panning", default=False,
                      help="Keeps any panning settings on each channel, producing a stereo output file. "
                           "(This requires double the hard drive space!)")
    oparser.add_option("-i", "--isolate-percussion", action="store_true", dest="isolate_percussion", default=False,
                      help="Renders each drum on the percussion channel to its own output file.")
    options, args = oparser.parse_args()
    return oparser, options, args

def main():
    oparser, options, args = __parse_arguments()
    if len(args) < 1:
        print "Please pass the name of the song to split as the first argument."
        oparser.print_help()
        return 1
    song_to_play = args[0]
    if not os.path.isfile(song_to_play):
        print "Song does not appear to exist, or is not a file: %s" % song_to_play
        oparser.print_help()
        return 3

    file_reader = dro_io.DroFileIO()
    dro_song = file_reader.read(song_to_play)
    player = dro_player.DROPlayer(channels=(2 if options.preserve_panning else 1))
    player.sound_on = False
    player.recording_on = True
    player.load_song(dro_song)
    print dro_song.pretty_string()

    try:
        split_tracks(player, dro_song, options.isolate_percussion)
    except KeyboardInterrupt, ke:
        pass
    except Exception, e:
        print e
        return 2
    finally:
        if player.is_playing:
            player.stop()
    return 0

if __name__ == "__main__":
    sys.exit(main())
