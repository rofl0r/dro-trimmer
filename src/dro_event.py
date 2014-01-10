#!/usr/bin/python
#
#    Use, distribution, and modification of the DRO Trimmer binaries, source code,
#    or documentation, is subject to the terms of the MIT license, as below.
#
#    Copyright (c) 2008 - 2014 Laurence Dougal Myers
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

"""
This module wraps around events. It provides the ability to bind functions to specified event flags.
Currently, it will use "wx" event functionality, if the "target" is a wx Event Handler object.
If not, it will provide some limited functionality - it is missing things like skipping or vetoing events,
a proper event queue, and more.
You can have a mixture of "wx" and regular Python objects as handlers; the manager will use the wx
event system for "wx" handlers, and the custom (limited) functionality for regular Python objects.

In the limited functionality, event handlers are triggered immediately; this service ends up acting as
a callback abstraction.

This module was designed to allow dro_data (Detailed Register Description Analysis) to raise an event when finished,
without knowing that it's contained within a GUI (wxPython) application. Doing so decouples the analyzer from the GUI,
so it can be used from the console (for example).

TODO: event queue for delayed processing of events.
TODO: skipping or vetoing event handlers?
"""
from collections import defaultdict
from functools import partial
try:
    import wx
    import wx.lib.newevent
except ImportError:
    wx = None
from dro_util import StructFromKeywords

class _EventSettings(object):
    def __init__(self):
        self.gui_binder = None
        self.gui_event_class = None
        self.binder = None
        self.event_class = None
        self.handlers = []

class CustomEventManager(object):
    def __init__(self):
        self.__event_settings = defaultdict(_EventSettings)

    def __create_event(self, event_name):
        new_settings = _EventSettings()
        if wx is not None:
            EventPayloadClass, EVT_BINDER = wx.lib.newevent.NewEvent()
            new_settings.gui_binder = EVT_BINDER
            new_settings.gui_event_class = EventPayloadClass
        new_settings.binder = partial(self.__register_event_handler, event_name)
        new_settings.event_class = StructFromKeywords
        self.__event_settings[event_name] = new_settings

    def __register_event_handler(self, event_name, target, handler_func):
        self.__event_settings[event_name].handlers.append((target, handler_func))

    def __unregister_event_handler(self, event_name, target, handler_func):
        event_handler_list = self.__event_settings[event_name].handlers
        event_handler_list.remove((target, handler_func))

    def trigger_event(self, event_name, target=None, **kwds):
        """ Sends and event to a handler function.
        Creates event classes if not already created, so that an event can
        be triggered when there are no handlers."""
        if event_name not in self.__event_settings:
            self.__create_event(event_name)
        evt_settings = self.__event_settings[event_name]
        # Trigger event for GUI handlers
        if wx is not None and evt_settings.gui_event_class is not None:
            wx_target = wx.GetApp() if target is None else target
            wx.PostEvent(wx_target, evt_settings.gui_event_class(**kwds))
        # Trigger event for non-GUI handlers
        for registered_target, handler_func in evt_settings.handlers:
            if target is None or target == registered_target:
                handler_func(evt_settings.event_class(**kwds))

    def bind_event(self, event_name, target, handler_func):
        """ Binds an event to a handler instance & function.
        Creates event classes if not already created."""
        if event_name not in self.__event_settings:
            self.__create_event(event_name)
        if wx is not None and isinstance(target, wx.EvtHandler):
            binder = self.__event_settings[event_name].gui_binder
        else:
            binder = self.__event_settings[event_name].binder
        binder(target, handler_func)

    def unbind_event(self, event_name, target, handler_func):
        """ Unbinds an event handler from an event.
        If the event does not appear to have been created previously (via a call to bind_event or trigger_event),
        this method will do nothing.
        """
        if event_name not in self.__event_settings:
            return # assume event has not been bound previously, so nothing to unbind.
        if wx is not None and isinstance(target, wx.EvtHandler):
            binder = self.__event_settings[event_name].gui_binder
            binder.Unbind(target, wx.ID_ANY, wx.ID_ANY, handler_func) # not sure if this is right...
        else:
            self.__unregister_event_handler(event_name, target, handler_func)


def __test():
    # TODO: proper unit tests
    global wx
    global __event_binders

    event_manager = CustomEventManager()
    # Test with wx (if it exists)
    if wx is not None:
        class TestHandlerApp(wx.App):
            def __init__(self, *args):
                wx.App.__init__(self, *args)
                self.time_event_triggered = 0

            def OnInit(self):
                self.mainframe = wx.Frame(None)
                self.mainframe.Show(True)
                self.SetTopWindow(self.mainframe)
                return True

            def handle_event(self, event):
                print event.payload
                assert event.payload == "The event ran okay"
                self.time_event_triggered += 1
                self.mainframe.Destroy()
                event_manager.unbind_event("TEST_EVENT", self, self.handle_event) # hrm
                event_manager.trigger_event("TEST_EVENT", payload="The event ran okay")

        app = TestHandlerApp(0)
        app.SetExitOnFrameDelete(True)
        event_manager.bind_event("TEST_EVENT", app, app.handle_event)
        event_manager.trigger_event("TEST_EVENT", payload="The event ran okay")

        app.MainLoop() # should close immediately due to the event trigger. If not, consider the test failed!
        assert app.time_event_triggered == 1

    # Test without wx
    class TestHandler(object):
        def __init__(self):
            self.times_event_trigerred = 0
        def handle_event(self, event):
            print event.payload
            assert event.payload == "The event ran okay"
            self.times_event_trigerred += 1
    th = TestHandler()
    th2 = TestHandler()
    event_manager.bind_event("TEST_EVENT", th, th.handle_event)
    event_manager.bind_event("TEST_EVENT", th2, th2.handle_event)
    event_manager.trigger_event("TEST_EVENT", payload="The event ran okay")
    assert th.times_event_trigerred == 1
    assert th2.times_event_trigerred == 1
    event_manager.unbind_event("TEST_EVENT", th2, th2.handle_event)
    event_manager.trigger_event("TEST_EVENT", payload="The event ran okay")
    assert th.times_event_trigerred == 2
    assert th2.times_event_trigerred == 1

if __name__ == "__main__": __test()