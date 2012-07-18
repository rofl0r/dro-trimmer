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
import os.path
import wx
import dro_data
import dro_io
import dro_globals
try:
    import dro_player
except ImportError:
    dro_player = None
import dro_undo
import dro_util
from containers import DTMainFrame
from dialogs import DTDialogGoto, DTDialogFindReg, DROInfoDialog, LoopAnalysisDialog
from ui_util import guiID, errorAlert, catchUnhandledExceptions, requiresDROLoaded

class DTApp(wx.App):
    def OnInit(self):
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
        self.loop_analysis_dialog = None # Loop Analysis Dialog

        self.mainframe = DTMainFrame(self,
                                     None,
                                     -1,
                                     "DRO Trimmer %s" % (dro_globals.g_app_version,),
                                     size=wx.Size(640, 480),
                                     tail_length=self.tail_length,
                                     dro_player_enabled=self.dro_player is not None)
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
        wx.EVT_MENU(self.mainframe, guiID("MENU_LOOPANALYSIS"), self.menuLoopAnalysis)
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

            # Load detailed register analysis.
            self.drosong.generate_detailed_register_descriptions()

            if self.dro_player is not None:
                self.dro_player.stop()
                self.dro_player.load_song(self.drosong)

            self.mainframe.dtlist.CreateList(self.drosong)
            self.setStatusText("Successfully opened " + os.path.basename(filename) + ".")

            # File was auto-trimmed, notify user
            dats = "T" # despite auto-trimming string
            if auto_trimmed:
                dats = "Despite auto-trimming, t"
                md = wx.MessageDialog(self.mainframe,
                    'The DRO was found to contain a bogus delay as\n' +\
                    'its first instruction. It has been automatically\n' +\
                    'removed. (Don\'t forget to save!)',
                    'DRO auto-trimmed',
                    style=wx.OK|wx.ICON_INFORMATION)
                md.ShowModal()
                # File has mismatch between measured and reported
            if delay_mismatch:
                md = wx.MessageDialog(self.mainframe,
                    dats + 'here was a mismatch between\n' +\
                    'the measured length of the song in milliseconds,\n' +\
                    'and the length stored in the DRO file.\n' +\
                    'You can fix this in the DRO Info page.',
                    'DRO timing mismatch',
                    style=wx.OK|wx.ICON_INFORMATION)
                md.ShowModal()

            # Reset undo history when a new file is opened.
            dro_globals.get_undo_controller().reset()
            self.mainframe.GetMenuBar().updateUndoRedoMenuItems()

            # Reset the Goto dialog, if it exists.
            if self.goto_dialog is not None:
                self.goto_dialog.reset(len(self.drosong.data) - 1)
            # Reset the loop analysis dialog, if it exists.
            if self.loop_analysis_dialog is not None:
                self.loop_analysis_dialog.load_results(None)

    @catchUnhandledExceptions
    @requiresDROLoaded
    def menuSaveDRO(self, event):
        filename = self.drosong.name
        # Seeing as the filename is stored in the drosong, I should modify
        #  save_dro to only take a DROSong.
        dro_io.DroFileIO().write(filename, self.drosong)
        self.setStatusText("File saved to " + filename + ".")

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
        self.goto_dialog = DTDialogGoto(self, self.mainframe, len(self.drosong.data) - 1)
        self.goto_dialog.Show()

    @catchUnhandledExceptions # Added by Wraithverge.
    @requiresDROLoaded
    def menuFindReg(self, event):
        if self.frdialog is not None:
            self.frdialog.Destroy() # TODO: destroy the dialog when it closes normally! (bit of a memory leak)
        self.frdialog = DTDialogFindReg(self, self.mainframe, self.drosong.file_version)
        self.frdialog.Show()

    @catchUnhandledExceptions
    @requiresDROLoaded
    def menuLoopAnalysis(self, event):
        if self.loop_analysis_dialog is not None:
            self.loop_analysis_dialog.Destroy()
        # Create a dummy analyzer so we know how many result pages we need to create.
        analyzer = dro_data.DROLoopAnalyzer()
        self.loop_analysis_dialog = LoopAnalysisDialog(self, analyzer, self.mainframe)
        self.loop_analysis_dialog.Show()

    def menuDelete(self, event):
        self.buttonDelete(None)

    @catchUnhandledExceptions
    @requiresDROLoaded
    def menuDROInfo(self, event):
        dro_info_dialog = DROInfoDialog(self.mainframe, self.drosong)
        dro_info_dialog.ShowModal()
        dro_info_dialog.Destroy()

    @catchUnhandledExceptions
    @requiresDROLoaded
    def menuUndo(self, event):
        undo_desc = dro_globals.get_undo_controller().undo()
        if undo_desc:
            self.setStatusText("Undone: %s" % (undo_desc,))
            self.mainframe.dtlist.RefreshItemCount()
            self.mainframe.dtlist.RefreshViewableItems()
            self.mainframe.GetMenuBar().updateUndoRedoMenuItems()
        else:
            self.setStatusText("Nothing to undo.")

    @catchUnhandledExceptions
    @requiresDROLoaded
    def menuRedo(self, event):
        redo_desc = dro_globals.get_undo_controller().redo()
        if redo_desc:
            self.setStatusText("Redone: %s" % (redo_desc,))
            self.mainframe.dtlist.RefreshItemCount()
            self.mainframe.dtlist.RefreshViewableItems()
            self.mainframe.GetMenuBar().updateUndoRedoMenuItems()
        else:
            self.setStatusText("Nothing to redo.")

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
            ('DRO Trimmer ' + dro_globals.g_app_version + "\n"
             'Laurence Dougal Myers\n' +
             'Web: http://www.jestarjokin.net/apps/drotrimmer\n' +
             'Web: https://bitbucket.org/jestar_jokin/dro-trimmer/\n' +
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
            # Also need to update the detailed register descriptions, since deleting an instruction will
            #  change the state of the chip after the deleted instructions.
            #  Unfortunately we need to update the whole lot. Could speed things up by storing "snapshots" of the
            #  chip state and only refreshing the descriptions, from the nearest snapshot before the first deleted
            #  instruction onwards.
            self.drosong.generate_detailed_register_descriptions()

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
            self.setStatusText("Invalid position for goto: %s" % position)
            return
        if position < 0 or position >= len(self.drosong.data):
            self.setStatusText("Position for goto is out of range: %s" % position)
            return
        self.mainframe.dtlist.Deselect()
        self.mainframe.dtlist.SelectItemManual(position)
        self.mainframe.dtlist.EnsureVisible(position)
        self.mainframe.dtlist.RefreshViewableItems()
        self.setStatusText("Gone to position: %s" % position)

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
            self.setStatusText("Could not find another occurrence of " + rToFind + ".")
            return
        self.mainframe.dtlist.Deselect()
        self.mainframe.dtlist.SelectItemManual(i)
        self.mainframe.dtlist.EnsureVisible(i)
        self.mainframe.dtlist.RefreshViewableItems()
        self.setStatusText("Occurrence of " + rToFind + " found at position " + str(i) + ".")

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
            self.setStatusText("No more notes found.")
            return
        self.mainframe.dtlist.Deselect()
        self.mainframe.dtlist.SelectItemManual(i)
        self.mainframe.dtlist.EnsureVisible(i)
        self.mainframe.dtlist.RefreshViewableItems()

    def buttonPreviousNote(self, event):
        self.buttonNextNote(event, look_backwards=True)

    @catchUnhandledExceptions
    @requiresDROLoaded
    def buttonAnalyzeLoop(self, event):
        if self.loop_analysis_dialog is None:
            errorAlert(self.mainframe, "Loop analysis requires the Loop Analysis dialog to be open, but none found.")
            return
        analyzer = dro_data.DROLoopAnalyzer()
        results = analyzer.analyze_dro(self.drosong)
        self.loop_analysis_dialog.load_results(results)
        self.setStatusText("Loop analysis finished.")

    # ____________________
    # Start Misc Event Handlers
    def keyListenerForList(self, event):
        keycode = event.GetKeyCode()
        if keycode in (wx.WXK_DELETE, wx.WXK_BACK): # delete or backspace
            self.buttonDelete(None)
            event.Veto()
        elif keycode == wx.WXK_LEFT:
            # <-- key. Previous note
            self.buttonPreviousNote(event)
            event.Veto()
        elif keycode == wx.WXK_RIGHT:
            # --> key. Next note
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
        elif self.dro_player is not None and keycode == 32:
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
    def __updateDROInfoRedo(self, args_list): # sigh
        self.updateDROInfo(*args_list)

    #@requiresDROLoaded # not really required here
    @dro_undo.undoable("DRO Header Changes", dro_globals.get_undo_controller, __updateDROInfoRedo)
    def updateDROInfo(self, opl_type, ms_length):
        original_values = [self.drosong.opl_type, self.drosong.ms_length]
        self.drosong.opl_type = opl_type
        self.drosong.ms_length = ms_length
        return original_values

    def setStatusText(self, message):
        self.mainframe.statusbar.SetStatusText(message)

def start_gui_app():
    app = None
    dro_globals.g_undo_controller = dro_undo.UndoController()
    try:
        app = DTApp(0)
        dro_globals.g_wx_app = app
        app.SetExitOnFrameDelete(True)
        app.MainLoop()
    finally:
        if app is not None:
            if app.dro_player is not None:
                app.dro_player.stop() # usually not needed, since it's handled by closeFrame
            app.Destroy()

if __name__ == "__main__": start_gui_app()