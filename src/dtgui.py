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
# Idea: have a message queue for processing components to communicate with GUI
#  e.g. load_file adds a message to the queue. T
#  At some point (either a set point in code, or in a thread?), all messages
#  are processed and displayed as appropriate. (How to handle multiple status bar things?
#  perhaps display, wait, display).
#

import wx
import dro_data
import dro_io
import os.path
import StringIO
import traceback
from regdata import registers

gVERSION = "3.0"
gGUIIDS = {}

def catchUnhandledExceptions(func):
    def inner_func(self, *args, **kwds):
        try:
            func(self, *args, **kwds)
        except Exception, e:
            fp = StringIO.StringIO()
            traceback.print_exc(file=fp)

            traceback.print_exc()
            alert = wx.MessageDialog(self.mainframe,
                "An unhandled exception was thrown, please contact support.\n" +
                "\nError:\n" + fp.getvalue(),
                "Unhandled Exception",
                wx.OK|wx.ICON_ERROR)
            alert.ShowModal()
            alert.Destroy()
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
        wx.ListCtrl.__init__(self, parent, -1, style=wx.LC_REPORT|wx.SUNKEN_BORDER|wx.LC_VIRTUAL|wx.LC_SINGLE_SEL|wx.VSCROLL)

        self.drosong = drosong
        self.selected = None
        self.parent = parent
        self.SetItemCount(self.GetItemCount()) # not as dumb as it looks.

        self.CreateColumns()
        self.RegisterEvents()

    def CreateColumns(self):
        self.InsertColumn(0, "Line")
        self.InsertColumn(1, "Reg")
        self.InsertColumn(2, "Value")
        self.InsertColumn(3, "Description")
        parent = self.GetParent()
        self.SetColumnWidth(0, parent.GetCharWidth() * 16)
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

    def SelectItem(self, event):
        self.selected = event.GetIndex()

    def SelectItemManual(self, ind):
        self.selected = ind
        self.Select(self.selected, 1) # select

    def SelectNextItem(self):
        oldsel = self.selected
        if oldsel is not None and oldsel < self.GetItemCount() - 1:
            self.Deselect()
            self.SelectItemManual(oldsel + 1)
            # scroll if we're getting too near the bottom of the view
            if oldsel+1 >= (self.GetTopItem() + self.GetCountPerPage() - 2):
                self.ScrollLines(1)

    def CreateList(self, insong):
        """ Regenerates the list based on data from a DROSong object. Takes a DROSong object."""
        self.DeleteAllItems()
        if self.selected is not None:
            self.Deselect()
        self.drosong = insong
        self.SetItemCount(self.GetItemCount())
        self.RefreshViewableItems()

    def Deselect(self):
        ##if self.selected != None:
            self.Select(self.selected, 0) # deselect
            self.selected = None

    def RefreshViewableItems(self):
        """ Updates items from the index of the topmost visible item to the index of the topmost visible item plus the number of items visible."""
        self.RefreshItems(self.GetTopItem(), self.GetTopItem() + self.GetCountPerPage()) #redraw

    def RefreshItemCount(self):
        self.SetItemCount(self.GetItemCount())

    def RegisterEvents(self):
        wx.EVT_LIST_ITEM_SELECTED(self, -1, self.SelectItem)


class DTDialogFindReg(wx.Dialog):
    def __init__(self, *args, **kwds):
        # TODO: allow user to search from the bottom (change DROSong search to
        #  decrement instead of increment)
        
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
            self.regchoices = ["DLYS", "DLYL", "DALL"] + [('0x%02X' % rk) for rk in range(0xFF)]
        else:
            self.regchoices = ["D-08", "D-16", "DALL", "BANK"] + [('0x%02X' % rk) for rk in range(0x105)]
        
        self.lRegister = wx.StaticText(self, -1, "Instruction:")
        self.cbRegisters = wx.ComboBox(self, -1, choices=self.regchoices, style=wx.CB_DROPDOWN|wx.CB_DROPDOWN|wx.CB_READONLY)
        self.bOk = wx.Button(self, guiID("BUTTON_FINDREG"), "Find Next")
        self.bCancel = wx.Button(self, wx.ID_CANCEL, "Close")
        
        wx.EVT_BUTTON(self, guiID("BUTTON_FINDREG"), self.parent.parent.buttonFindReg)

        self.__set_properties()
        self.__do_layout()
        # end wxGlade

    def __set_properties(self):
        # begin wxGlade: DTDialogFindReg.__set_properties
        self.SetTitle("Find Register")
        self.cbRegisters.SetSelection(-1)
        # end wxGlade

    def __do_layout(self):
        # begin wxGlade: DTDialogFindReg.__do_layout
        sMain = wx.BoxSizer(wx.VERTICAL)
        sBottom = wx.BoxSizer(wx.HORIZONTAL)
        gsTop = wx.FlexGridSizer(1, 2, 0, 0)
        gsTop.Add(self.lRegister, 0, 0, 0)
        gsTop.Add(self.cbRegisters, 0, 0, 0)
        sMain.Add(gsTop, 1, wx.EXPAND, 0)
        sBottom.Add(self.bOk, 0, 0, 0)
        sBottom.Add(self.bCancel, 0, wx.LEFT, 10)
        sMain.Add(sBottom, 0, wx.ALL|wx.ALIGN_RIGHT, 5)
        self.SetSizer(sMain)
        sMain.Fit(self)
        self.Layout()
        # end wxGlade

# end of class DTDialogFindReg

class DTMainMenuBar(wx.MenuBar):
    def __init__(self, *args, **kwds):
        wx.MenuBar.__init__(self, *args, **kwds)
        
        # File menu
        self.menuFile = wx.Menu()      
        self.menuFile.Append(guiID("MENU_OPENDRO"), "Open DRO", "Open a DRO file.", wx.ITEM_NORMAL)
        self.menuFile.Append(guiID("MENU_SAVEDRO"), "Save DRO", "Save the current DRO file.", wx.ITEM_NORMAL)
        self.menuFile.Append(guiID("MENU_SAVEDROAS"), "Save DRO As...", "Save the current DRO file under a new name.", wx.ITEM_NORMAL)
        self.menuFile.AppendSeparator()
        self.menuFile.Append(wx.ID_EXIT, "Exit", "Quit, begone, depart, flee.", wx.ITEM_NORMAL)
        self.Append(self.menuFile, "File")

        self.menuEdit = wx.Menu()
        self.menuEdit.Append(guiID("MENU_FINDREG"), "Find Register", "Find the next occurance of a register.", wx.ITEM_NORMAL)
        self.menuEdit.AppendSeparator()
        self.menuEdit.Append(guiID("MENU_DELETE"), "Delete", "Deletes the currently selected instruction.", wx.ITEM_NORMAL)
        self.Append(self.menuEdit, "Edit")

        # Help menu
        self.menuHelp = wx.Menu()
        self.menuHelpHelp = wx.MenuItem(self.menuHelp, wx.ID_HELP, "Help", "Open the help file.", wx.ITEM_NORMAL)
        self.menuHelp.AppendItem(self.menuHelpHelp)
        self.menuHelpAbout = wx.MenuItem(self.menuHelp, guiID("MENU_ABOUT"), "About", "Open the about dialog.", wx.ITEM_NORMAL)
        self.menuHelp.AppendItem(self.menuHelpAbout)
        self.Append(self.menuHelp, "Help")

        self.__set_properties()
        self.__do_layout()

    def __set_properties(self):
        pass

    def __do_layout(self):
        pass

class DTMainFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        kwds["style"] = wx.DEFAULT_FRAME_STYLE
        self.parent = kwds['dtparent']
        del kwds['dtparent']
        wx.Frame.__init__(self, *args, **kwds)

        self.statusbar = self.CreateStatusBar()

        self.dtlist = DTSongDataList(self, self.parent.drosong)
        
        self.panel_1 = wx.Panel(self, -1)
        self.button_delete = wx.Button(self.panel_1, guiID("BUTTON_DELETE"), "Delete instruction")
        
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
        self.drosong = None
        
        self.mainframe = DTMainFrame(None, -1, "DRO Trimmer", size=wx.Size(640, 480), dtparent=self)
        self.mainframe.Show(True)
        self.SetTopWindow(self.mainframe)
        
        self._RegisterEventHandlers()
        
        return True
    
    def _RegisterEventHandlers(self):
        wx.EVT_MENU(self.mainframe, guiID("MENU_OPENDRO"), self.menuOpenDRO)
        wx.EVT_MENU(self.mainframe, guiID("MENU_SAVEDRO"), self.menuSaveDRO)
        wx.EVT_MENU(self.mainframe, guiID("MENU_SAVEDROAS"), self.menuSaveDROAs)
        wx.EVT_MENU(self.mainframe, wx.ID_EXIT, self.menuExit)
        wx.EVT_MENU(self.mainframe, guiID("MENU_FINDREG"), self.menuFindReg)
        wx.EVT_MENU(self.mainframe, guiID("MENU_DELETE"), self.menuDelete)
        wx.EVT_MENU(self.mainframe, wx.ID_HELP, self.menuHelp)
        wx.EVT_MENU(self.mainframe, guiID("MENU_ABOUT"), self.menuAbout)
        
        wx.EVT_BUTTON(self.mainframe, guiID("BUTTON_DELETE"), self.buttonDelete)
        
        
        wx.EVT_CLOSE(self.mainframe, self.closeFrame)
        
        wx.EVT_LIST_KEY_DOWN(self.mainframe, -1, self.keyListener)
        
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

            self.drosong, at, lm = dro_io.DroFileIO().read(filename)
            self.mainframe.dtlist.CreateList(self.drosong)
            self.mainframe.statusbar.SetStatusText("Successfully opened " + os.path.basename(filename) + ".")
            # File was auto-trimmed, notify user
            dats = "T" # despite auto-trimming string
            if at:
                dats = "Despite auto-trimming, t"
                md = wx.MessageDialog(self.mainframe,
                            'The DRO was found to contain a bogus delay as\n' + \
                            'its first instruction. It has been automatically\n' + \
                            'removed. (Don\'t forget to save!)',
                            'DRO auto-trimmed',
                            style=wx.OK|wx.ICON_INFORMATION)
                md.ShowModal()
            # File has mismatch between measured and reported 
            if lm:
                md = wx.MessageDialog(self.mainframe,
                            dats + 'here was a mismatch between\n' + \
                            'the measured length of the song in milliseconds,\n' + \
                            'and the length stored in the DRO file.\n' + \
                            'Buuuut, I wouldn\'t worry about it. Just tellin\' ya.',
                            'DRO timing mismatch',
                            style=wx.OK|wx.ICON_INFORMATION)
                md.ShowModal()

    @catchUnhandledExceptions
    def menuSaveDRO(self, event):
        if self.drosong is None:
            self.mainframe.statusbar.SetStatusText("Please open a DRO file first.")
            return
        filename = self.drosong.name
        # Seeing as the filename is stored in the drosong, I should modify
        #  save_dro to only take a DROSong.
        dro_io.DroFileIO().write(filename, self.drosong)
        self.mainframe.statusbar.SetStatusText("File saved to " + filename + ".")
    
    def menuSaveDROAs(self, event):
        if self.drosong is None:
            self.mainframe.statusbar.SetStatusText("Please open a DRO file first.")
            return
        
        sd = wx.FileDialog(self.mainframe,
                           "Save DRO file",
                           wildcard="DRO files (*.dro)|*.dro|All Files|*.*",
                           style=wx.SAVE|wx.OVERWRITE_PROMPT|wx.CHANGE_DIR)
        if sd.ShowModal() == wx.ID_OK:
            self.drosong.name = sd.GetPath()
            self.menuSaveDRO(event)
    
    def menuExit(self, event):
        self.mainframe.Close(False)
    
    def menuFindReg(self, event):
        if self.drosong is None:
            self.mainframe.statusbar.SetStatusText("Please open a DRO file first.")
            return
        self.frdialog = DTDialogFindReg(self.mainframe, self.drosong.file_version)
        self.frdialog.Show()
    
    def menuDelete(self, event):
        self.buttonDelete(None)
    
    def menuHelp(self, event):
        hd = wx.MessageDialog(self.mainframe,
            '1) Select an instruction.\n' + \
            '2) Delete via button or the Del key.\n' + \
            '3) Profit!\n\n' +\
            'If you\'re trimming a looping song, look for a\n' + \
            'whole bunch of instructions with no delays, as\n' + \
            'this might be where the instruments are set up.',
            'Help',
            style=wx.OK|wx.ICON_INFORMATION)
        hd.ShowModal()
    
    def menuAbout(self, event):
        ad = wx.MessageDialog(self.mainframe,
            ('DRO Trimmer ' + gVERSION + "\n"
            'Laurence Dougal Myers\n' +
            'Web: http://www.jestarjokin.net\n' +
            'E-Mail: jestarjokin@jestarjokin.net\n\n' +
            'Thanks to:\n' +
            'The DOSBOX team\n' +
            'The AdPlug team\n' +
            'pi-r-squared for their original attempt at a DRO editor'),
            'About',
            style=wx.OK|wx.ICON_INFORMATION)
        ad.ShowModal()
    
    # ____________________
    # Start Button Event Handlers
    @catchUnhandledExceptions
    def buttonDelete(self, event):
        if self.mainframe.dtlist.selected is not None:
            # I think all of this should be moved to the dtlist...
            self.drosong.delete_instruction(self.mainframe.dtlist.selected)
            self.mainframe.dtlist.RefreshItemCount()
            self.mainframe.dtlist.RefreshViewableItems()
            # Prevents problems if we delete the last item
            if self.mainframe.dtlist.selected >= self.mainframe.dtlist.GetItemCount():
                self.mainframe.dtlist.Deselect()

    @catchUnhandledExceptions
    def buttonFindReg(self, event):
        rToFind = self.frdialog.cbRegisters.GetValue()
        if rToFind == '': return
        if self.mainframe.dtlist.selected is None:
            start = 0
        else:
            start = self.mainframe.dtlist.selected + 1
        i = self.drosong.find_next_instruction(start, rToFind)
        if i == -1:
            self.mainframe.statusbar.SetStatusText("Could not find another occurance of " + rToFind + ".")
            return
        self.mainframe.dtlist.SelectItemManual(i)
        self.mainframe.dtlist.EnsureVisible(i)
        self.mainframe.dtlist.RefreshViewableItems()
        self.mainframe.statusbar.SetStatusText("Occurance of " + rToFind + " found on line " + str(i) + ".")

    # ____________________
    # Start Misc Event Handlers
    def keyListener(self, event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_DELETE or keycode == wx.WXK_BACK: # delete or backspace
            self.buttonDelete(None)
        
    def closeFrame(self, event):
        wx.Window.DestroyChildren(self.mainframe)
        wx.Window.Destroy(self.mainframe)

def run():
    app = None
    
    try:
        app = DTApp(0)
        app.SetExitOnFrameDelete(True)
        app.MainLoop()
    finally:
        if app is not None:
            app.Destroy()

if __name__ == "__main__": run()    