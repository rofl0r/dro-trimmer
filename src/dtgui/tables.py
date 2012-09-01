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
        self.InsertColumn(1, "Bank")
        self.InsertColumn(2, "Reg.")
        self.InsertColumn(3, "Value")
        self.InsertColumn(4, "Description")
        self.InsertColumn(5, "Description (all register options)")
        parent = self.GetParent()
        self.SetColumnWidth(0, parent.GetCharWidth() * 10)
        self.SetColumnWidth(1, parent.GetCharWidth() * 7)
        self.SetColumnWidth(2, parent.GetCharWidth() * 8)
        self.SetColumnWidth(3, parent.GetCharWidth() * 13)
        self.SetColumnWidth(4, parent.GetCharWidth() * 70)
        self.SetColumnWidth(5, parent.GetCharWidth() * 70)

    def OnGetItemText(self, item, column):
        # Possible TODO: split the description into sub-components
        # eg for "Tremolo / Vibrato / Sustain / KSR / Frequency Multiplication Factor"
        # (can't use bitmask because we may be disabling items - could possibly be solved by
        # keeping track of register changes/state when loading the song)
        if self.drosong is None:
            return ""

        if column == 0:
            return str(item).zfill(4) + ">"
        # Bank
        elif column == 1:
            return self.drosong.get_bank_description(item)
        # Register
        elif column == 2:
            return self.drosong.get_register_display(item)
        # Value
        elif column == 3:
            return self.drosong.get_value_display(item)
        # Description
        elif column == 4:
            return self.drosong.get_detailed_register_description(item)
        # Description (all register options)
        elif column == 5:
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
        self.Focus(ind)

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
