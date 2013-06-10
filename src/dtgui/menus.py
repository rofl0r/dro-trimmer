#!/usr/bin/python
#
#    Use, distribution, and modification of the DRO Trimmer binaries, source code,
#    or documentation, is subject to the terms of the MIT license, as below.
#
#    Copyright (c) 2008 - 2013 Laurence Dougal Myers
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
import dro_globals
import wx

from ui_util import guiID

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
        self.menuEdit.Append(guiID("MENU_LOOPANALYSIS"), "&Loop Analysis...\tCtrl-L", "Attempts to find sections of data that indicate a loop point.", wx.ITEM_NORMAL)
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
        if dro_globals.g_undo_controller.has_something_to_undo():
            self.undoMenuItem.Enable(True)
        else:
            self.undoMenuItem.Enable(False)
            # Check if there's anything left to undo
        if dro_globals.g_undo_controller.has_something_to_redo():
            self.redoMenuItem.Enable(True)
        else:
            self.redoMenuItem.Enable(False)