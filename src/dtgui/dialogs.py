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
import wx
import dro_analysis
import dro_data
import dro_globals
import dro_util
from containers import TextPanel
from ui_util import guiID, errorAlert

class DTDialogGoto(wx.Dialog):
    def __init__(self, wx_app, parent, max_pos, *args, **kwds):
        # begin wxGlade: DTDialogGoto.__init__
        kwds["style"] = wx.DEFAULT_DIALOG_STYLE
        wx.Dialog.__init__(self, parent, *args, **kwds)
        self.scPosition = wx.SpinCtrl(self, -1, "", min=0, max=max_pos)
        self.btnGo = wx.Button(self, guiID("BUTTON_GOTO_GO"), "Go")
        self.btnClose = wx.Button(self, wx.ID_CANCEL, "Close")

        self.__set_properties()
        self.__do_layout()
        # end wxGlade
        self.parent = parent
        wx.EVT_BUTTON(self, guiID("BUTTON_GOTO_GO"), wx_app.buttonGoto)

    def __set_properties(self):
        # begin wxGlade: DTDialogGoto.__set_properties
        self.SetTitle("Goto Position")
        self.btnGo.SetDefault()
        self.scPosition.SetValueString("")
        # end wxGlade

    def __do_layout(self):
        # begin wxGlade: DTDialogGoto.__do_layout
        szMain = wx.BoxSizer(wx.VERTICAL)
        szButtons = wx.BoxSizer(wx.HORIZONTAL)
        # Layout adjusted by Wraithverge to be consistent with Find Reg layout.
        szMain.Add(self.scPosition, 0, wx.ALL|wx.ALIGN_CENTER, 5)
        szButtons.Add((0, 5), 0, 0, 0)
        szButtons.Add(self.btnGo, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        szButtons.Add(self.btnClose, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        szMain.Add(szButtons, 0, wx.ALL, 0)
        self.SetSizer(szMain)
        szMain.Fit(self)
        self.Layout()
        # end wxGlade

    def reset(self, max_pos):
        self.scPosition.SetValue(0)
        self.scPosition.SetValueString("")
        self.scPosition.SetRange(0, max_pos)

# end of class DTDialogGoto


class DTDialogFindReg(wx.Dialog):
    def __init__(self, wx_app, *args, **kwds):
        # begin wxGlade: DTDialogFindReg.__init__
        kwds["style"] = wx.DEFAULT_DIALOG_STYLE
        wx.Dialog.__init__(self, *args, **kwds)

        self.parent = args[0]
        self.dro_version = args[1]

        # Choices are special values for DRO commands plus registers
        # formerly: [hex(rk) for rk in registers.keys()]
        # but give the option to search for unknown registers (up to 0x105)
        if self.dro_version == dro_data.DRO_FILE_V2:
            # NOTE: could be some confusion with codemaps and low/high banks.
            # Currently looks up the real register value (note the codemap index), and ignores banks.
            self.regchoices = ["DLYS", "DLYL", "DALL"] + [('0x%02X' % rk) for rk in range(0x100)]
        else:
            self.regchoices = ["DLYS", "DLYL", "DALL", "BANK"] + [('0x%02X' % rk) for rk in range(0x100)]

        self.lRegister = wx.StaticText(self, -1, "Instruction:")
        self.cbRegisters = wx.ComboBox(self, -1, choices=self.regchoices, style=wx.CB_DROPDOWN|wx.CB_DROPDOWN|wx.CB_READONLY)
        self.bFindNext = wx.Button(self, guiID("BUTTON_FINDREG"), "Find Next")
        self.bFindPrevious = wx.Button(self, guiID("BUTTON_FINDREGPREV"), "Find Previous")
        self.bCancel = wx.Button(self, wx.ID_CANCEL, "Close")

        wx.EVT_BUTTON(self, guiID("BUTTON_FINDREG"), wx_app.buttonFindReg)
        wx.EVT_BUTTON(self, guiID("BUTTON_FINDREGPREV"), wx_app.buttonFindRegPrevious)

        self.__set_properties()
        self.__do_layout()
        # end wxGlade

    def __set_properties(self):
        # begin wxGlade: DTDialogFindReg.__set_properties
        self.SetTitle("Find Register")
        self.cbRegisters.SetSelection(-1)
        # end wxGlade

    def __do_layout(self):
        # Alignment adjustments by Wraithverge
        # begin wxGlade: DTDialogFindReg.__do_layout
        sMain = wx.BoxSizer(wx.VERTICAL)
        sMiddle = wx.BoxSizer(wx.HORIZONTAL)
        sBottom = wx.BoxSizer(wx.HORIZONTAL)
        gsTop = wx.FlexGridSizer(1, 2, 0, 5)
        gsTop.Add(self.lRegister, 1, wx.ALIGN_CENTER, 0)
        gsTop.Add(self.cbRegisters, 0, 0, 0)
        sMain.Add(gsTop, 0, wx.ALL|wx.ALIGN_CENTER, 2)
        sMiddle.Add(self.bFindPrevious, 0, 0, 0)
        sMiddle.Add(self.bFindNext, 0, 0, 0)
        sMain.Add(sMiddle, 0, wx.ALL|wx.ALIGN_RIGHT, 5)
        sBottom.Add(self.bCancel, 0, wx.LEFT, 10)
        sMain.Add(sBottom, 0, wx.ALL|wx.ALIGN_RIGHT, 5)
        self.SetSizer(sMain)
        sMain.Fit(self)
        self.Layout()
        # end wxGlade

# end of class DTDialogFindReg


class DROInfoDialog ( wx.Dialog ):
    def __init__(self, parent, dro_song, *args, **kwds):
        try:
            config = dro_util.read_config()
            dro_info_edit_enabled = config.getboolean("ui", "dro_info_edit_enabled")
        except Exception, e:
            print 'Could not read the value for "dro_info_edit_enabled" in "drotrim.ini"; defaulting to false.'
            dro_info_edit_enabled = False
        # begin wxGlade: MyDialog.__init__
        self.parent = parent
        kwds["style"] = wx.DEFAULT_DIALOG_STYLE
        wx.Dialog.__init__(self, parent, *args, **kwds)
        self.lDROVersion = wx.StaticText(self, -1, "DRO Version")
        self.tcDROVersion = wx.TextCtrl(self, -1, str(dro_song.file_version))
        self.lHardwareType = wx.StaticText(self, -1, "Hardware Type")
        self.cHardwareType = wx.Choice(self, -1, choices=dro_song.OPL_TYPE_MAP)
        self.cHardwareType.Select(dro_song.opl_type)
        self.lLengthMs = wx.StaticText(self, -1, "Length (MS)")
        self.tcLengthMs = wx.TextCtrl(self, -1, str(dro_song.ms_length))
        self.lLengthMsCalc = wx.StaticText(self, -1, "Calculated Length (MS)")
        calculated_delay = dro_analysis.DROTotalDelayCalculator().sum_delay(dro_song)
        self.tcLengthMsCalc = wx.TextCtrl(self, -1, str(calculated_delay))
        if dro_info_edit_enabled:
            self.bEdit = wx.Button(self, guiID("BUTTON_DROINFO_EDIT"), "Edit")
        self.bClose = wx.Button(self, wx.ID_CANCEL, "Close")

        self.__set_properties()
        self.__do_layout(dro_info_edit_enabled)
        # end wxGlade

        self.dro_song = dro_song
        self.edit_mode = False
        if dro_info_edit_enabled:
            wx.EVT_BUTTON(self, guiID("BUTTON_DROINFO_EDIT"), self.EditSaveButtonEvent)

    def __set_properties(self):
        # begin wxGlade: MyDialog.__set_properties
        self.SetTitle("DRO Info")
        self.SetSize((330, 242))
        self.tcDROVersion.Disable()
        self.cHardwareType.Disable()
        self.tcLengthMs.Disable()
        self.tcLengthMsCalc.Disable()
        self.bClose.SetDefault()
        # end wxGlade

    def __do_layout(self, dro_info_edit_enabled):
        # begin wxGlade: MyDialog.__do_layout
        sMain = wx.GridSizer(5, 2, 0, 0)
        sButtons = wx.BoxSizer(wx.HORIZONTAL)
        sMain.Add(self.lDROVersion, 0, wx.ALL, 5)
        sMain.Add(self.tcDROVersion, 0, wx.ALL, 5)
        sMain.Add(self.lHardwareType, 0, wx.ALL, 5)
        sMain.Add(self.cHardwareType, 0, wx.ALL, 5)
        sMain.Add(self.lLengthMs, 0, wx.ALL, 5)
        sMain.Add(self.tcLengthMs, 0, wx.ALL, 5)
        sMain.Add(self.lLengthMsCalc, 0, wx.ALL, 5)
        sMain.Add(self.tcLengthMsCalc, 0, wx.ALL, 5)
        sMain.Add((0, 0), 1, wx.EXPAND, 5)
        if dro_info_edit_enabled:
            sButtons.Add(self.bEdit, 1, wx.ALL | wx.ALIGN_RIGHT | wx.ALIGN_BOTTOM, 5)
        else:
            sButtons.Add((0, 0), 1, wx.ALL | wx.ALIGN_RIGHT | wx.ALIGN_BOTTOM, 5)
        sButtons.Add(self.bClose, 1, wx.ALL | wx.ALIGN_RIGHT | wx.ALIGN_BOTTOM, 5)
        sMain.Add(sButtons, 1, wx.EXPAND | wx.ALIGN_RIGHT, 5)
        self.SetSizer(sMain)
        self.Layout()

    def EditSaveButtonEvent(self, event):
        if self.edit_mode:
            self.SaveChanges(event)
        else:
            self.StartEditMode(event)

    def StartEditMode(self, event):
        dro_globals.g_wx_app.setStatusText("DRO Info edit mode enabled.")
        self.edit_mode = True
        self.cHardwareType.Enable()
        self.tcLengthMs.Enable()
        self.bEdit.SetLabel("Save")
        self.bClose.SetLabel("Cancel")

    def SaveChanges(self, event):
        try:
            opl_type = self.cHardwareType.GetSelection()
            assert 0 <= opl_type < len(self.dro_song.OPL_TYPE_MAP)
            ms_length = int(self.tcLengthMs.GetValue())
        except Exception, e:
            errorAlert(self, "Error updating DRO info, check that the entered values are correct.")
            return
        dro_globals.g_wx_app.updateDROInfo(opl_type, ms_length)
        md = wx.MessageDialog(self,
            "DRO info updated.\n"
            "Remember to save the file.",
            style=wx.OK|wx.ICON_INFORMATION)
        md.ShowModal()
        md.Destroy()


class LoopAnalysisDialog(wx.Dialog):
    def __init__(self, wx_app, loop_analyzer, parent,**kwds):
        wx.Dialog.__init__(self,
                           parent,
                           style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER |
                                 wx.MAXIMIZE_BOX | wx.MINIMIZE_BOX | wx.THICK_FRAME,
                           **kwds)
        self.notebook = wx.Notebook(self, size=(400, 300))

        # Create buttons
        self.btnAnalyze = wx.Button(self, guiID("BUTTON_ANALYZE"), "Analyze")
        self.btnClose = wx.Button(self, wx.ID_CANCEL, "Close")

        # Create first page
        info_text = ("This is the loop analysis dialog.\n\n"
        "It provides multiple analyses to determine interesting parts of the song data, "
        "hinting at sections that may be loop points.\n\n"
        "Some analysis methods will work better than others, depending on the song, "
        "where the loop occurs, how many times the song loops, how much data exists "
        "after a loop point, etc.\n\n"
        "Please refer to the online documentation for more information."
        )

        page1 = TextPanel(self.notebook, info_text)
        self.notebook.AddPage(page1, "Info")

        # Create as many tabs as there are analysis methods.
        self.result_pages = []
        for i in xrange(loop_analyzer.num_analyses()):
            page = TextPanel(self.notebook, "No analysis performed yet.")
            self.notebook.AddPage(page, "#%d" % (i + 1,))
            self.result_pages.append(page)

        # Register events
        wx.EVT_BUTTON(self, guiID("BUTTON_ANALYZE"), wx_app.buttonAnalyzeLoop)

        # Do other UI stuff
        self.__set_properties()
        self.__do_layout()

    def __set_properties(self):
        self.SetTitle("Loop Analysis")

    def __do_layout(self):
        # Lay things out
        sizerButtons = wx.BoxSizer(wx.HORIZONTAL)
        sizerButtons.Add(self.btnAnalyze, 1, wx.ALIGN_RIGHT | wx.ALIGN_BOTTOM, 0)
        sizerButtons.Add(self.btnClose, 1, wx.ALIGN_RIGHT | wx.ALIGN_BOTTOM, 0)

        sizerMain = wx.BoxSizer(wx.VERTICAL)
        sizerMain.Add(self.notebook, 1, wx.EXPAND | wx.ALIGN_CENTER_HORIZONTAL, 0)
        sizerMain.Add(sizerButtons, 0, wx.EXPAND, 0)
        self.SetSizer(sizerMain)
        sizerMain.Fit(self)
        self.Layout()

    def load_results(self, result_list):
        if result_list is None:
            result_list = ["No analysis performed yet."] * len(self.result_pages)
        for loop_analysis_result, page in zip(result_list, self.result_pages):
            page.setText(str(loop_analysis_result))
