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
import os
import sys
try:
    import win32api
except ImportError:
    win32api = None
import wx
import dro_globals
import dro_util

from menus import DTMainMenuBar
from tables import DTSongDataList
from ui_util import guiID

class DTMainFrame(wx.Frame):
    def __init__(self, wx_app, *args, **kwds):
        kwds["style"] = wx.DEFAULT_FRAME_STYLE
        tail_length = kwds['tail_length']
        del kwds['tail_length']
        dro_player_enabled = kwds['dro_player_enabled']
        del kwds['dro_player_enabled']
        wx.Frame.__init__(self, *args, **kwds)

        # Maximize window base on config settings (added by Wraithverge)
        try:
            config = dro_util.read_config()
            maximize_window = config.getboolean("ui", "maximize_window")
        except Exception, e:
            print 'Could not read the value for "maximize_window" in "drotrim.ini"; defaulting to windowed mode.'
            maximize_window = False
        self.Maximize(maximize_window)

        # Set icon, if available
        use_external_icon = True
        if win32api is not None:
            exe_name = win32api.GetModuleFileName(win32api.GetModuleHandle(None))
        else:
            exe_name = sys.executable # seems to do the same thing...
            # If the program is being run from the Python interpreter (and not
        #  a packged exe), use the external icon file. Otherwise, load the
        #  icon from the packaged exe resources.
        if not os.path.basename(exe_name).startswith("python"):
            icon = wx.Icon(exe_name, wx.BITMAP_TYPE_ICO)
            self.SetIcon(icon)
            use_external_icon = False
        if use_external_icon:
            exe_path = dro_util.get_exe_path()
            ico_name = os.path.join(exe_path, 'dt.ico')
            icon = wx.Icon(ico_name, wx.BITMAP_TYPE_ICO)
            self.SetIcon(icon)

        self.statusbar = self.CreateStatusBar()
        self.dtlist = DTSongDataList(self, wx_app.drosong)
        self.panel_1 = wx.Panel(self, -1)
        self.button_delete = wx.Button(self.panel_1, guiID("BUTTON_DELETE"), "Delete instruction")
        if dro_player_enabled:
            self.button_play = wx.Button(self.panel_1, guiID("BUTTON_PLAY"), "Play song from current pos.")
            self.button_stop = wx.Button(self.panel_1, guiID("BUTTON_STOP"), "Stop song")
            tail_in_seconds = tail_length / 1000.0
            if tail_in_seconds % 1:
                tail_str = "%.2f" % (tail_in_seconds,)
            else:
                tail_str = "%d" % (tail_in_seconds,)
            self.button_play_tail = wx.Button(self.panel_1, guiID("BUTTON_PLAY_TAIL"),
                "Play last %s second%s" % (tail_str, 's' if tail_in_seconds != 1 else ''))

        self.__set_properties()
        self.__do_layout(dro_player_enabled)

    def __set_properties(self):
        self.SetMenuBar(DTMainMenuBar())
        self.statusbar.SetFieldsCount(2)

    def __do_layout(self, dro_player_enabled):
        grid_sizer_1 = wx.FlexGridSizer(2, 1, 0, 0)
        grid_sizer_1.Add(self.dtlist, 1, wx.EXPAND, 0)

        sizer_1 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_1.Add(self.button_delete, 0, wx.FIXED_MINSIZE, 0)
        if dro_player_enabled:
            sizer_1.Add(self.button_play, 0, wx.FIXED_MINSIZE, 0)
            sizer_1.Add(self.button_stop, 0, wx.FIXED_MINSIZE, 0)
            sizer_1.Add(self.button_play_tail, 0, wx.FIXED_MINSIZE, 0)
        self.panel_1.SetAutoLayout(1)
        self.panel_1.SetSizer(sizer_1)
        sizer_1.Fit(self.panel_1)
        sizer_1.SetSizeHints(self.panel_1)

        grid_sizer_1.Add(self.panel_1, 1, wx.EXPAND, 0)

        self.SetAutoLayout(1)
        self.SetSizer(grid_sizer_1)
        grid_sizer_1.Fit(self)
        grid_sizer_1.SetSizeHints(self)

        grid_sizer_1.AddGrowableCol(0, self.dtlist.GetBestSize().width)
        grid_sizer_1.AddGrowableRow(0, 90)

        self.statusbar.SetStatusWidths([-2, -1])

        self.Layout()
        self.SetSize((600, 400))


class TextPanel(wx.Panel):
    def __init__(self, parent, text=None):
        wx.Panel.__init__(self, parent)
        if text is None:
            text = ""
        self.textCtrl = wx.TextCtrl(self, -1, text, style=wx.TE_MULTILINE)
        self.__set_properties()
        self.__do_layout()

    def __set_properties(self):
        self.textCtrl.SetEditable(False)

    def __do_layout(self):
        sizer = wx.BoxSizer()
        sizer.Add(self.textCtrl, 1, wx.EXPAND)
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Layout()

    def setText(self, text):
        self.textCtrl.SetValue(text)