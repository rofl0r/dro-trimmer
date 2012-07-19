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

"""
This module wraps around events. It provides the ability to bind functions to

This allows dro_data (Detailed Register Description Analysis) to raise an event when finished,
without knowing that it's contained within a GUI (wxPython) application.
Doing so decouples the analyzer from the GUI, so it can be used from the console (for example).

TODO: unbinding events / handlers.
TODO: move stuff out of the module-level scope.
"""
from collections import defaultdict
from functools import partial
try:
    import wx
    import wx.lib.newevent
except ImportError:
    wx = None
from dro_util import StructFromKeywords

__event_handlers = defaultdict(list)
__event_binders = {}
__event_classes = {}

def __create_event(event_name):
    global __event_binders
    global __event_classes
    if wx is not None:
        EventPayloadClass, EVT_BINDER = wx.lib.newevent.NewEvent()
        __event_binders[event_name] = EVT_BINDER
        __event_classes[event_name] = EventPayloadClass
    else:
        __event_binders[event_name] = partial(__register_event_handler, event_name)
        __event_classes[event_name] = StructFromKeywords

def __register_event_handler(event_name, handler_instance, handler_func):
    global __event_handlers
    __event_handlers[event_name].append((handler_instance, handler_func))

def trigger_event(event_name, **kwds):
    """ Sends and event to a handler function.
    Creates event classes if not already created, so that an event can
    be triggered when there are no handlers."""
    global __event_classes
    global __event_handlers
    if event_name not in __event_binders:
        __create_event(event_name)
    evt_payload_class = __event_classes[event_name]
    if wx is not None:
        for handler_instance, handler_func in __event_handlers[event_name]:
            wx.PostEvent(handler_instance, evt_payload_class(**kwds))
    else:
        for handler_instance, handler_func in __event_handlers[event_name]:
            handler_func(evt_payload_class(**kwds))

def bind_event(event_name, handler_instance, handler_func):
    """ Binds an event to a handler instance & function.
    Creates event classes if not already created."""
    global __event_binders
    if event_name not in __event_binders:
        __create_event(event_name)
    binder = __event_binders[event_name]
    binder(handler_instance, handler_func)



def __test():
    global wx
    global __event_binders
    wx = None
    class TestHandler(object):
        def handle_event(self, event):
            print event.payload
            assert event.payload == "The event ran okay"
    th = TestHandler()
    th2 = TestHandler()
    bind_event("TEST_EVENT", th, th.handle_event)
    bind_event("TEST_EVENT", th2, th2.handle_event)
    trigger_event("TEST_EVENT", payload="The event ran okay")

if __name__ == "__main__": __test()