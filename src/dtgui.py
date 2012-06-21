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
import os.path
import StringIO
import traceback
try:
    import win32api
except ImportError:
    win32api = None
import wx
import dro_data
import dro_io
try:
    import dro_player
except ImportError:
    dro_player = None
import dro_undo
import dro_util


gVERSION = "v3 r8"
gGUIIDS = {}

def errorAlert(parent, msg, title="Error"):
    alert = wx.MessageDialog(parent, #hrmmm
            msg,
            title,
            wx.OK|wx.ICON_ERROR)
    alert.ShowModal()
    alert.Destroy()

def catchUnhandledExceptions(func):
    def inner_func(self, *args, **kwds):
        try:
            func(self, *args, **kwds)
        except Exception, e:
            fp = StringIO.StringIO()
            traceback.print_exc(file=fp)

            traceback.print_exc()
            errorAlert(self.mainframe, #that's a bit gross
                 "An unhandled exception was thrown, please contact support.\n" +
                   "\nError:\n" + fp.getvalue(),
                "Unhandled Exception")
    return inner_func

def requiresDROLoaded(func):
    def inner_func(self, *args, **kwds):
        if self.drosong is None:
            # A bit gross
            self.mainframe.statusbar.SetStatusText("Please open a DRO file first.")
            return
        else:
            func(self, *args, **kwds)
    return inner_func

def guiID(name):
    """ Takes a name and returns an ID retrieved from the gGUIIDS dictionary.
    If the name is not in the dict, it's added."""
    if not gGUIIDS.has_key(name):
        gGUIIDS[name] = wx.NewId()
    return gGUIIDS[name]


class DTSongDataList(wx.ListCtrl):
    def __init__(self, parent, drosong):
        """
        @type drosong: DROSong
        """
        wx.ListCtrl.__init__(self, parent, -1, style=wx.LC_REPORT|wx.SUNKEN_BORDER|wx.LC_VIRTUAL|wx.VSCROLL)

        self.drosong = drosong
        self.parent = parent
        self.SetItemCount(self.GetItemCount()) # not as dumb as it looks. Because it's virtual, need to calculate the item count.

        self.CreateColumns()
        self.RegisterEvents()

    def CreateColumns(self):
        self.InsertColumn(0, "Pos.")
        self.InsertColumn(1, "Reg.")
        self.InsertColumn(2, "Value")
        self.InsertColumn(3, "Description")
        parent = self.GetParent()
        self.SetColumnWidth(0, parent.GetCharWidth() * 10)
        self.SetColumnWidth(1, parent.GetCharWidth() * 8)
        self.SetColumnWidth(2, parent.GetCharWidth() * 16)
        self.SetColumnWidth(3, parent.GetCharWidth() * 70)
 
    def OnGetItemText(self, item, column):
        # Possible TODO: split the description into sub-components
        # eg for "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor"
        # (can't use bitmask because we may be disabling items)
        if self.drosong is None:
            return ""
        
        if column == 0:
            return str(item).zfill(4) + ">"
        # Register
        elif column == 1:
            return self.drosong.get_register_display(item)
        # Value
        elif column == 2:
            return self.drosong.get_value_display(item)
        # Description
        elif column == 3:
            return self.drosong.get_instruction_description(item)

    def GetItemCount(self):
        if self.drosong is None:
            return 0
        return self.drosong.getLengthData()

    def GetLastSelected(self):
        if not self.HasSelected():
            return None
        item = self.GetFirstSelected()
        last_item = None
        while item != -1:
            last_item = item
            item = self.GetNextSelected(item)
        return last_item

    def SelectItemManual(self, ind):
        self.Select(ind, 1) # select

    def SelectNextItem(self):
        oldsel = self.GetLastSelected()
        if oldsel is not None and oldsel < self.GetItemCount() - 1:
            self.Deselect()
            self.SelectItemManual(oldsel + 1)
            # scroll if we're getting too near the bottom of the view
            if oldsel + 1 >= (self.GetTopItem() + self.GetCountPerPage() - 2):
                self.ScrollLines(1)

    def CreateList(self, insong):
        """ Regenerates the list based on data from a DROSong object. Takes a DROSong object.

        @type insong: DROSong"""
        self.DeleteAllItems()
        if self.HasSelected():
            self.Deselect()
        self.drosong = insong
        self.SetItemCount(self.GetItemCount())
        self.RefreshViewableItems()

    def Deselect(self):
        item = self.GetFirstSelected()
        while item != -1:
            self.Select(item, 0)
            item = self.GetNextSelected(item)

    def RefreshViewableItems(self):
        """ Updates items from the index of the topmost visible item to the index of the topmost visible item plus the number of items visible."""
        first_index = self.GetTopItem()
        last_index = min(self.GetTopItem() + self.GetCountPerPage(), self.GetItemCount() - 1)
        self.RefreshItems(first_index, last_index) #redraw

    def RefreshItemCount(self):
        self.SetItemCount(self.GetItemCount())

    def RegisterEvents(self):
        #wx.EVT_LIST_ITEM_SELECTED(self, -1, self.SelectItem)
        pass

    def HasSelected(self):
        return self.GetSelectedItemCount() > 0

    def GetAllSelected(self):
        sel_items = []
        item = self.GetFirstSelected()
        while item != -1:
            sel_items.append(item)
            item = self.GetNextSelected(item)
        return sel_items


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


class DTMainMenuBar(wx.MenuBar):
    def __init__(self, *args, **kwds):
        wx.MenuBar.__init__(self, *args, **kwds)
        
        # File menu
        self.menuFile = wx.Menu()      
        self.menuFile.Append(guiID("MENU_OPENDRO"), "&Open DRO...\tCtrl-O", "Open a DRO file.", wx.ITEM_NORMAL)
        self.menuFile.Append(guiID("MENU_SAVEDRO"), "&Save DRO\tCtrl-S", "Save the current DRO file.", wx.ITEM_NORMAL)
        self.menuFile.Append(guiID("MENU_SAVEDROAS"), "Save DRO &As...\tCtrl-Shift-S", "Save the current DRO file under a new name.", wx.ITEM_NORMAL)
        self.menuFile.AppendSeparator()
        self.menuFile.Append(wx.ID_EXIT, "E&xit", "Quit, begone, depart, flee.", wx.ITEM_NORMAL)
        self.Append(self.menuFile, "&File")

        self.menuEdit = wx.Menu()
        self.undoMenuItem = self.menuEdit.Append(guiID("MENU_UNDO"), "&Undo\tCtrl-Z", "Undoes the last change you made to the data.", wx.ITEM_NORMAL)
        self.redoMenuItem = self.menuEdit.Append(guiID("MENU_REDO"), "&Redo\tCtrl-Y", "Redoes the previously undone change you made to the data.", wx.ITEM_NORMAL)
        self.menuEdit.AppendSeparator()
        self.menuEdit.Append(guiID("MENU_GOTO"), "&Goto...\tCtrl-G", "Goes to a specific position.", wx.ITEM_NORMAL)
        self.menuEdit.Append(guiID("MENU_FINDREG"), "&Find Register...\tCtrl-F", "Find the next occurrence of a register.", wx.ITEM_NORMAL)
        self.menuEdit.Append(guiID("MENU_FINDLOOP"), "Find &Loop\tCtrl-L", "Tries to find a matching section of data.", wx.ITEM_NORMAL) # Wraithverge
        self.menuEdit.Append(guiID("MENU_DROINFO"), "DRO &Info...\tCtrl-I", "View or edit the DRO file info (song length, hardware type)", wx.ITEM_NORMAL)
        self.menuEdit.AppendSeparator()
        self.menuEdit.Append(guiID("MENU_DELETE"), "&Delete Instruction(s)\tDEL", "Deletes the currently selected instruction.", wx.ITEM_NORMAL)
        self.Append(self.menuEdit, "&Edit")

        # Help menu
        self.menuHelp = wx.Menu()
        self.menuHelpHelp = wx.MenuItem(self.menuHelp, wx.ID_HELP, "&Help...\tCtrl-H", "Displays a little bit of help.", wx.ITEM_NORMAL)
        self.menuHelp.AppendItem(self.menuHelpHelp)
        self.menuHelpAbout = wx.MenuItem(self.menuHelp, guiID("MENU_ABOUT"), "&About...", "Open the about dialog.", wx.ITEM_NORMAL)
        self.menuHelp.AppendItem(self.menuHelpAbout)
        self.Append(self.menuHelp, "&Help")

        self.__set_properties()
        self.__do_layout()

    def __set_properties(self):
        self.undoMenuItem.Enable(False)
        self.redoMenuItem.Enable(False)

    def __do_layout(self):
        pass

    def updateUndoRedoMenuItems(self):
        # Check if there's anything left to undo
        if dro_undo.g_undo_controller.has_something_to_undo():
            self.undoMenuItem.Enable(True)
        else:
            self.undoMenuItem.Enable(False)
        # Check if there's anything left to undo
        if dro_undo.g_undo_controller.has_something_to_redo():
            self.redoMenuItem.Enable(True)
        else:
            self.redoMenuItem.Enable(False)

class DTMainFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        kwds["style"] = wx.DEFAULT_FRAME_STYLE
        self.parent = kwds['dtparent']
        tail_length = kwds['tail_length']
        del kwds['dtparent']
        del kwds['tail_length']
        wx.Frame.__init__(self, *args, **kwds)

        # set window icon (for Windows binaries only)
        if win32api is not None:
            exeName = win32api.GetModuleFileName(win32api.GetModuleHandle(None))
            icon = wx.Icon(exeName, wx.BITMAP_TYPE_ICO)
            self.SetIcon(icon)

        self.statusbar = self.CreateStatusBar()

        self.dtlist = DTSongDataList(self, self.parent.drosong)
        
        self.panel_1 = wx.Panel(self, -1)
        self.button_delete = wx.Button(self.panel_1, guiID("BUTTON_DELETE"), "Delete instruction")
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
        self.__do_layout()

    def __set_properties(self):
        #self.SetTitle("DRO Trimmer")
        self.SetMenuBar(DTMainMenuBar())

    def __do_layout(self):
        # This is a complete mess
        grid_sizer_1 = wx.FlexGridSizer(2, 1, 0, 0)
        grid_sizer_1.Add(self.dtlist, 1, wx.EXPAND, 0)
        
        sizer_1 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_1.Add(self.button_delete, 0, wx.FIXED_MINSIZE, 0)
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
        
        self.Layout()
        self.SetSize((600, 400))


class DTApp(wx.App):
    def OnInit(self):
        global gVERSION
        self.drosong = None
        # The DRO player functionality is optional, so users without the PyOPL and PyAudio modules installed can
        #  still make use of the editor.
        if dro_player is not None:
            self.dro_player = dro_player.DROPlayer()
        else:
            self.dro_player = None

        try:
            config = dro_util.read_config()
            self.tail_length = config.getint("ui", "tail_length")
        except Exception, e:
            print "Could not read tail length from drotrim.ini, using default value."
            self.tail_length = 3000
        self.goto_dialog = None # Goto diaog
        self.frdialog = None # Find Register dialog

        self.mainframe = DTMainFrame(None, -1, "DRO Trimmer %s" % (gVERSION,), size=wx.Size(640, 480),
            dtparent=self, tail_length=self.tail_length)
        self.mainframe.Show(True)
        self.SetTopWindow(self.mainframe)
        
        self._RegisterEventHandlers()
        
        return True
    
    def _RegisterEventHandlers(self):
        wx.EVT_MENU(self.mainframe, guiID("MENU_OPENDRO"), self.menuOpenDRO)
        wx.EVT_MENU(self.mainframe, guiID("MENU_SAVEDRO"), self.menuSaveDRO)
        wx.EVT_MENU(self.mainframe, guiID("MENU_SAVEDROAS"), self.menuSaveDROAs)
        wx.EVT_MENU(self.mainframe, wx.ID_EXIT, self.menuExit)
        wx.EVT_MENU(self.mainframe, guiID("MENU_UNDO"), self.menuUndo)
        wx.EVT_MENU(self.mainframe, guiID("MENU_REDO"), self.menuRedo)
        wx.EVT_MENU(self.mainframe, guiID("MENU_GOTO"), self.menuGoto)
        wx.EVT_MENU(self.mainframe, guiID("MENU_FINDREG"), self.menuFindReg)
        wx.EVT_MENU(self.mainframe, guiID("MENU_DELETE"), self.menuDelete)
        wx.EVT_MENU(self.mainframe, guiID("MENU_DROINFO"), self.menuDROInfo)
        wx.EVT_MENU(self.mainframe, guiID("MENU_FINDLOOP"), self.menuFindLoop)
        wx.EVT_MENU(self.mainframe, wx.ID_HELP, self.menuHelp)
        wx.EVT_MENU(self.mainframe, guiID("MENU_ABOUT"), self.menuAbout)
        
        wx.EVT_BUTTON(self.mainframe, guiID("BUTTON_DELETE"), self.buttonDelete)
        wx.EVT_BUTTON(self.mainframe, guiID("BUTTON_PLAY"), self.buttonPlay)
        wx.EVT_BUTTON(self.mainframe, guiID("BUTTON_STOP"), self.buttonStop)
        wx.EVT_BUTTON(self.mainframe, guiID("BUTTON_PLAY_TAIL"), self.buttonPlayTail)

        wx.EVT_CLOSE(self.mainframe, self.closeFrame)

        wx.EVT_KEY_DOWN(self, self.keyListener)
        wx.EVT_LIST_KEY_DOWN(self.mainframe, -1, self.keyListenerForList)
        
    # ____________________
    # Start Menu Event Handlers
    @catchUnhandledExceptions
    def menuOpenDRO(self, event):
        od = wx.FileDialog(self.mainframe,
                           "Open DRO",
                           wildcard="DRO files (*.dro)|*.dro|All Files|*.*",
                           style=wx.OPEN|wx.FILE_MUST_EXIST|wx.CHANGE_DIR)
        if od.ShowModal() == wx.ID_OK:
            filename = od.GetPath()

            importer = dro_io.DroFileIO()
            self.drosong = importer.read(filename)

            # Delete first instruction if it's a bogus delay (mostly for V1)
            first_delay_analyzer = dro_data.DROFirstDelayAnalyzer()
            first_delay_analyzer.analyze_dro(self.drosong)
            if first_delay_analyzer.result:
                self.drosong.delete_instructions([0])
                auto_trimmed = True
            else:
                auto_trimmed = False

            # Check if the totaly delay calculated doesn't match the delay recorded
            #  in the DRO file header.
            delay_mismatch_analyzer = dro_data.DROTotalDelayMismatchAnalyzer()
            delay_mismatch_analyzer.analyze_dro(self.drosong)
            delay_mismatch = delay_mismatch_analyzer.result

            if self.dro_player is not None:
                self.dro_player.stop()
                self.dro_player.load_song(self.drosong)
            self.mainframe.dtlist.CreateList(self.drosong)
            self.mainframe.statusbar.SetStatusText("Successfully opened " + os.path.basename(filename) + ".")
            # File was auto-trimmed, notify user
            dats = "T" # despite auto-trimming string
            if auto_trimmed:
                dats = "Despite auto-trimming, t"
                md = wx.MessageDialog(self.mainframe,
                            'The DRO was found to contain a bogus delay as\n' + \
                            'its first instruction. It has been automatically\n' + \
                            'removed. (Don\'t forget to save!)',
                            'DRO auto-trimmed',
                            style=wx.OK|wx.ICON_INFORMATION)
                md.ShowModal()
            # File has mismatch between measured and reported 
            if delay_mismatch:
                md = wx.MessageDialog(self.mainframe,
                            dats + 'here was a mismatch between\n' + \
                            'the measured length of the song in milliseconds,\n' + \
                            'and the length stored in the DRO file.\n' + \
                            'You can fix this in the DRO Info page.',
                            'DRO timing mismatch',
                            style=wx.OK|wx.ICON_INFORMATION)
                md.ShowModal()
            # Reset undo history when a new file is opened.
            dro_undo.g_undo_controller.reset()
            self.mainframe.GetMenuBar().updateUndoRedoMenuItems()
            # Reset the Goto dialog, if it exists.
            if self.goto_dialog is not None:
                self.goto_dialog.reset(len(self.drosong.data) - 1)

    @catchUnhandledExceptions
    @requiresDROLoaded
    def menuSaveDRO(self, event):
        filename = self.drosong.name
        # Seeing as the filename is stored in the drosong, I should modify
        #  save_dro to only take a DROSong.
        dro_io.DroFileIO().write(filename, self.drosong)
        self.mainframe.statusbar.SetStatusText("File saved to " + filename + ".")

    @requiresDROLoaded
    def menuSaveDROAs(self, event):
        sd = wx.FileDialog(self.mainframe,
                           "Save DRO file",
                           wildcard="DRO files (*.dro)|*.dro|All Files|*.*",
                           style=wx.SAVE|wx.OVERWRITE_PROMPT|wx.CHANGE_DIR)
        if sd.ShowModal() == wx.ID_OK:
            self.drosong.name = sd.GetPath()
            self.menuSaveDRO(event)
    
    def menuExit(self, event):
        self.mainframe.Close(False)

    @catchUnhandledExceptions
    @requiresDROLoaded
    def menuGoto(self, event):
        if self.goto_dialog is not None:
            self.goto_dialog.Destroy()
        self.goto_dialog = DTDialogGoto(self.mainframe, len(self.drosong.data) - 1)
        self.goto_dialog.Show()

    @requiresDROLoaded
    def menuFindReg(self, event):
        if self.frdialog is not None:
            self.frdialog.Destroy() # TODO: destroy the dialog when it closes normally! (bit of a memory leak)
        self.frdialog = DTDialogFindReg(self.mainframe, self.drosong.file_version)
        self.frdialog.Show()

    # This section was added by Wraithverge.
    @catchUnhandledExceptions
    @requiresDROLoaded
    def menuFindLoop(self, event):
        result = dro_data.DROLoopAnalyzer().analyze_dro(self.drosong)
        self.mainframe.statusbar.SetStatusText("Please look at the console to view the result ...")

    def menuDelete(self, event):
        self.buttonDelete(None)

    @requiresDROLoaded
    def menuDROInfo(self, event):
        dro_info_dialog = DROInfoDialog(self.mainframe, self.drosong)
        dro_info_dialog.ShowModal()
        dro_info_dialog.Destroy()

    @catchUnhandledExceptions
    @requiresDROLoaded
    def menuUndo(self, event):
        undo_desc = dro_undo.g_undo_controller.undo()
        if undo_desc:
            self.mainframe.statusbar.SetStatusText("Undone: %s" % (undo_desc,))
            self.mainframe.dtlist.RefreshItemCount()
            self.mainframe.dtlist.RefreshViewableItems()
            self.mainframe.GetMenuBar().updateUndoRedoMenuItems()
        else:
            self.mainframe.statusbar.SetStatusText("Nothing to undo.")

    @catchUnhandledExceptions
    @requiresDROLoaded
    def menuRedo(self, event):
        redo_desc = dro_undo.g_undo_controller.redo()
        if redo_desc:
            self.mainframe.statusbar.SetStatusText("Redone: %s" % (redo_desc,))
            self.mainframe.dtlist.RefreshItemCount()
            self.mainframe.dtlist.RefreshViewableItems()
            self.mainframe.GetMenuBar().updateUndoRedoMenuItems()
        else:
            self.mainframe.statusbar.SetStatusText("Nothing to redo.")

    def menuHelp(self, event):
        hd = wx.MessageDialog(self.mainframe,
            'Full instructions are available online.\n' +
            'https://bitbucket.org/jestar_jokin/dro-trimmer/wiki/Home\n'
            '\n' +
            '1) Select an instruction.\n' +
            '2) Delete via button or the Del key.\n' +
            '3) Profit!\n\n' +
            'If you\'re trimming a looping song, look for a\n' +
            'whole bunch of instructions with no delays, as\n' +
            'this might be where the instruments are set up.',
            'Help',
            style=wx.OK|wx.ICON_INFORMATION)
        hd.ShowModal()
        hd.Destroy()
    
    def menuAbout(self, event):
        ad = wx.MessageDialog(self.mainframe,
            ('DRO Trimmer ' + gVERSION + "\n"
            'Laurence Dougal Myers\n' +
            'Web: http://www.jestarjokin.net/apps/drotrimmer\n' +
            '     https://bitbucket.org/jestar_jokin/dro-trimmer/\n' +
            'E-Mail: jestarjokin@jestarjokin.net\n\n' +
            'Thanks to:\n' +
            'The DOSBOX team\n' +
            'The AdPlug team\n' +
            'Adam Nielsen for PyOPL\n' +
            'Wraithverge for testing, feedback and contributions\n' +
            'pi-r-squared for their original attempt at a DRO editor'),
            'About',
            style=wx.OK|wx.ICON_INFORMATION)
        ad.ShowModal()
        ad.Destroy()
    
    # ____________________
    # Start Button Event Handlers
    @catchUnhandledExceptions
    @requiresDROLoaded
    def buttonDelete(self, event):
        if self.mainframe.dtlist.HasSelected():
            if self.dro_player is not None:
                self.dro_player.stop()
            # I think all of this should be moved to the dtlist...
            selected_items = self.mainframe.dtlist.GetAllSelected()
            self.drosong.delete_instructions(selected_items)
            self.mainframe.dtlist.RefreshItemCount()
            # Deselect all, and re-select only the first index we deleted,
            # or the last item in the list.
            first_item = selected_items[0]
            self.mainframe.dtlist.Deselect()
            if first_item < self.mainframe.dtlist.GetItemCount():
                newly_selected = first_item
            else:
                # Otherwise, select the list item in the list
                newly_selected = self.mainframe.dtlist.GetItemCount() - 1
            self.mainframe.dtlist.SelectItemManual(newly_selected)
            self.mainframe.dtlist.EnsureVisible(newly_selected)
            self.mainframe.dtlist.RefreshViewableItems()
            # Keep track of Undo buffer.
            # (Crap, requires knowledge that this is an "undoable" action.
            # Might be better to investigate triggering an event, or using
            # observer/listener pattern.)
            self.mainframe.GetMenuBar().updateUndoRedoMenuItems()

    @requiresDROLoaded
    def buttonPlay(self, event):
        if self.dro_player is not None:
            self.dro_player.stop()
            self.dro_player.reset()
            if self.mainframe.dtlist.HasSelected():
                self.dro_player.seek_to_pos(self.mainframe.dtlist.GetFirstSelected())
            self.dro_player.play()

    @requiresDROLoaded
    def buttonStop(self, event):
        if self.dro_player is not None:
            self.dro_player.stop()
            self.dro_player.reset()

    @requiresDROLoaded
    def buttonPlayTail(self, event):
        if self.dro_player is not None:
            self.dro_player.stop()
            self.dro_player.reset()
            self.dro_player.seek_to_time(max(self.dro_player.current_song.ms_length - self.tail_length, 0))
            self.dro_player.play()

    @catchUnhandledExceptions
    def buttonGoto(self, event):
        position = self.goto_dialog.scPosition.GetValue()
        try:
            position = int(position)
        except Exception:
            self.mainframe.statusbar.SetStatusText("Invalid position for goto: %s" % position)
            return
        if position < 0 or position >= len(self.drosong.data):
            self.mainframe.statusbar.SetStatusText("Position for goto is out of range: %s" % position)
            return
        self.mainframe.dtlist.Deselect()
        self.mainframe.dtlist.SelectItemManual(position)
        self.mainframe.dtlist.EnsureVisible(position)
        self.mainframe.dtlist.RefreshViewableItems()
        self.mainframe.statusbar.SetStatusText("Gone to position: %s" % position)

    @catchUnhandledExceptions
    def buttonFindReg(self, event, look_backwards=False):
        rToFind = self.frdialog.cbRegisters.GetValue()
        if rToFind == '': return
        if not self.mainframe.dtlist.HasSelected():
            start = 0
        else:
            start = self.mainframe.dtlist.GetLastSelected() + 1
        i = self.drosong.find_next_instruction(start, rToFind, look_backwards=look_backwards)
        if i == -1:
            self.mainframe.statusbar.SetStatusText("Could not find another occurrence of " + rToFind + ".")
            return
        self.mainframe.dtlist.Deselect()
        self.mainframe.dtlist.SelectItemManual(i)
        self.mainframe.dtlist.EnsureVisible(i)
        self.mainframe.dtlist.RefreshViewableItems()
        self.mainframe.statusbar.SetStatusText("Occurrence of " + rToFind + " found at position " + str(i) + ".")

    def buttonFindRegPrevious(self, event):
        self.buttonFindReg(event, look_backwards=True) # blech

    @catchUnhandledExceptions
    @requiresDROLoaded
    def buttonNextNote(self, event, look_backwards=False):
        if not self.mainframe.dtlist.HasSelected():
            start = 0
        else:
            start = self.mainframe.dtlist.GetLastSelected() + 1
        i = self.drosong.find_next_instruction(start, "DALL", look_backwards=look_backwards)
        if i == -1:
            self.mainframe.statusbar.SetStatusText("No more notes found.")
            return
        self.mainframe.dtlist.Deselect()
        self.mainframe.dtlist.SelectItemManual(i)
        self.mainframe.dtlist.EnsureVisible(i)
        self.mainframe.dtlist.RefreshViewableItems()

    def buttonPreviousNote(self, event):
        self.buttonNextNote(event, look_backwards=True)

    # ____________________
    # Start Misc Event Handlers
    def keyListenerForList(self, event):
        keycode = event.GetKeyCode()
        if keycode in (wx.WXK_DELETE, wx.WXK_BACK): # delete or backspace
            self.buttonDelete(None)
            event.Veto()
        elif keycode == 44:
            # < or , Previous note
            self.buttonPreviousNote(event)
            event.Veto()
        elif keycode == 46:
            # > or . Next note
            self.buttonNextNote(event)
            event.Veto()
        else:
            event.Skip()

    def keyListener(self, event):
        keycode = event.GetKeyCode()
        if keycode == 70 and event.CmdDown(): # CTRL-F
            self.menuFindReg(event)
        elif keycode == 71 and event.CmdDown(): # CTRL-G
            self.menuGoto(event)
        elif keycode == 72 and event.CmdDown(): # CTRL-H
            self.menuHelp(event)
        elif keycode == 73 and event.CmdDown(): # CTRL-I
            self.menuDROInfo(event)
        elif keycode == 79 and event.CmdDown(): # CTRL-O
            self.menuOpenDRO(event)
        elif keycode == 83 and event.ShiftDown() and event.CmdDown(): # CTRL-SHIFT-S
            self.menuSaveDROAs(event)
        elif keycode == 83 and event.CmdDown(): # CTRL-S
            self.menuSaveDRO(event)
        elif keycode == 89 and event.CmdDown(): # CTRL-Y
            self.menuRedo(event)
        elif keycode == 90 and event.CmdDown(): # CTRL-Z
            self.menuUndo(event)
        elif keycode == 32:
            self.togglePlayback(event)
        else:
            #print keycode
            event.Skip()
        
    def closeFrame(self, event):
        wx.Window.DestroyChildren(self.mainframe)
        wx.Window.Destroy(self.mainframe)
        if self.dro_player is not None:
            self.dro_player.stop()

    def togglePlayback(self, event):
        if self.dro_player is not None:
            if self.dro_player.is_playing:
                self.buttonStop(event)
            else:
                self.buttonPlay(event)

    # Other stuff
    def __UpdateDROInfoRedo(self, args_list): # sigh
        self.UpdateDROInfo(*args_list)

    #@requiresDROLoaded # not really required here
    @dro_undo.undoable("DRO Header Changes", dro_undo.g_undo_controller, __UpdateDROInfoRedo)
    def UpdateDROInfo(self, opl_type, ms_length):
        original_values = [self.drosong.opl_type, self.drosong.ms_length]
        self.drosong.opl_type = opl_type
        self.drosong.ms_length = ms_length
        return original_values


def run():
    app = None
    
    try:
        app = DTApp(0)
        app.SetExitOnFrameDelete(True)
        app.MainLoop()
    finally:
        if app is not None:
            if app.dro_player is not None:
                app.dro_player.stop() # usually not needed, since it's handled by closeFrame
            app.Destroy()

if __name__ == "__main__": run()    