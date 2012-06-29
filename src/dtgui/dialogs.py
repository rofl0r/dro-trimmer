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
import dro_data
from ui_util import guiID, errorAlert

class DTDialogGoto(wx.Dialog):
    def __init__(self, parent, max_pos, *args, **kwds):
        # begin wxGlade: DTDialogGoto.__init__
        kwds["style"] = wx.DEFAULT_DIALOG_STYLE
        wx.Dialog.__init__(self, parent, *args, **kwds)
        self.scPosition = wx.SpinCtrl(self, -1, "", min=0, max=max_pos)
        self.btnGo = wx.Button(self, guiID("BUTTON_GOTO_GO"), "Go")
        self.btnClose = wx.Button(self, wx.ID_CANCEL, "")

        self.__set_properties()
        self.__do_layout()
        # end wxGlade
        self.parent = parent
        wx.EVT_BUTTON(self, guiID("BUTTON_GOTO_GO"), self.parent.parent.buttonGoto) # "parent.parent" is gross

    def __set_properties(self):
        # begin wxGlade: DTDialogGoto.__set_properties
        self.SetTitle("Goto Position")
        # end wxGlade

    def __do_layout(self):
        # begin wxGlade: DTDialogGoto.__do_layout
        szMain = wx.BoxSizer(wx.VERTICAL)
        szButtons = wx.BoxSizer(wx.HORIZONTAL)
        szMain.Add(self.scPosition, 0, wx.EXPAND | wx.ALIGN_CENTER_HORIZONTAL, 0)
        szButtons.Add((20, 20), 1, 0, 0)
        szButtons.Add(self.btnGo, 1, wx.ALIGN_RIGHT | wx.ALIGN_BOTTOM | wx.ALIGN_CENTER_HORIZONTAL, 0)
        szButtons.Add(self.btnClose, 1, wx.ALIGN_RIGHT | wx.ALIGN_BOTTOM, 0)
        szMain.Add(szButtons, 1, wx.EXPAND, 0)
        self.SetSizer(szMain)
        szMain.Fit(self)
        self.Layout()
        # end wxGlade

    def reset(self, max_pos):
        self.scPosition.SetValue(0)
        self.scPosition.SetRange(0, max_pos)

# end of class DTDialogGoto


class DTDialogFindReg(wx.Dialog):
    def __init__(self, *args, **kwds):
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

        wx.EVT_BUTTON(self, guiID("BUTTON_FINDREG"), self.parent.parent.buttonFindReg) # gross
        wx.EVT_BUTTON(self, guiID("BUTTON_FINDREGPREV"), self.parent.parent.buttonFindRegPrevious) # gross

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
        calculated_delay = dro_data.DROTotalDelayCalculator().sum_delay(dro_song)
        self.tcLengthMsCalc = wx.TextCtrl(self, -1, str(calculated_delay))
        self.bEdit = wx.Button(self, guiID("BUTTON_DROINFO_EDIT"), "Edit")
        self.bClose = wx.Button(self, wx.ID_CANCEL, "Close")

        self.__set_properties()
        self.__do_layout()
        # end wxGlade

        self.dro_song = dro_song
        self.edit_mode = False
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

    def __do_layout(self):
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
        sButtons.Add(self.bEdit, 1, wx.ALL | wx.ALIGN_RIGHT | wx.ALIGN_BOTTOM, 5)
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
        md = wx.MessageDialog(self,
            ("Editing this information is not recommended, and is only required for broken DRO files. "
             "I would try ripping the song again, instead. "
             "Don't alter anything here if you don't have to!\n"
             "Proceed?"),
            style=wx.OK|wx.CANCEL|wx.ICON_EXCLAMATION)
        result = md.ShowModal()
        md.Destroy()
        if result == wx.ID_OK:
            self.edit_mode = True
            #self.tcDROVersion.Enable()
            self.cHardwareType.Enable()
            self.tcLengthMs.Enable()
            self.bEdit.SetLabel("Save")
            self.bClose.SetLabel("Cancel")

    def SaveChanges(self, event):
        # Probably should move this to the App class
        try:
            opl_type = self.cHardwareType.GetSelection()
            assert 0 <= opl_type < len(self.dro_song.OPL_TYPE_MAP)
            ms_length = int(self.tcLengthMs.GetValue())
        except Exception, e:
            errorAlert(self, "Error updating DRO info, check that the entered values are correct.")
            return
        self.parent.parent.UpdateDROInfo(opl_type, ms_length) # "parent.parent" stuff is crap. TODO: make a proper app controller.
        md = wx.MessageDialog(self,
            "DRO info updated.\n"
            "Remember to save the file.",
            style=wx.OK|wx.ICON_INFORMATION)
        md.ShowModal()
        md.Destroy()