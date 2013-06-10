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
import StringIO
import traceback
import wx
import dro_globals

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
            msg = "Please open a DRO file first."
            if dro_globals.g_wx_app is not None:
                dro_globals.g_wx_app.setStatusText(msg)
            else:
                print msg
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
