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
import weakref

def undoable(description, undo_controller_getter, undo_function):
    """ Decorator. Allows any side effects
    of the method to be undone or redone at a later stage.

    Requirements for use:
    - It must be used to decorate a method on a class.
    - You must pass in a method that returns an "UndoController" object (or similar),
      which in turn must have a boolean property "bypass", representing whether this
      invocation should track the "undo" state.
    - The wrapped method must return an object, representing the original
      state of the changed data. (The "original state")
    - If you want to also return a value as normal, instead return a
      StateAndReturnValue object, constructed from the "original state"
      and any return value you want. (Use a tuple to return multiple values)
    - You must specify a complementary method that will actually perform
      the "undo".
    - The "undo" method must take the "original state" object.
    - It's assumed the original arguments and keywords passed in to the
      function will be sufficient to "redo" the action later (i.e. there
      is no other context that could affect the behaviour of the "redo"
      function).
    """
    def wrap(func):
        def inner_func(self, *args, **kwds):
            result = func(self, *args, **kwds)
            if type(result) == StateAndReturnValue:
                undo_state = StateAndReturnValue.state
                value = StateAndReturnValue.value
            else:
                undo_state = result
                value = None

            bypass_undo = undo_controller_getter().bypass
            if not bypass_undo:
                undo_controller_getter().append(
                    UndoMemo(description, self, undo_function, undo_state, func, (args, kwds))
                )

            return value
        return inner_func
    return wrap

class StateAndReturnValue():
    def __init__(self, state, value):
        self.state = state
        self.value = value # not sure if this supports multiple values. Maybe should use *args?

class UndoMemo(object):
    def __init__(self, description, instance, undo_function, changed_state, redo_function, redo_args_and_kwds):
        self.description = description
        self.instance = weakref.proxy(instance) # don't want "undo" functionality stopping GC
        self.undo_function = undo_function
        self.changed_state = changed_state
        self.redo_function = redo_function
        self.redo_args_and_kwds = redo_args_and_kwds

    def undo(self):
        self.undo_function(self.instance, self.changed_state)

    def redo(self):
        self.redo_function(self.instance, *self.redo_args_and_kwds[0], **self.redo_args_and_kwds[1])

class UndoController(object):
    def __init__(self):
        self.reset()

    def reset(self):
        self.bypass = False
        self.buffer = []
        self.position = -1

    def is_buffer_empty(self):
        return len(self.buffer) == 0

    def has_something_to_undo(self):
        return not self.is_buffer_empty() and self.position != -1

    def has_something_to_redo(self):
        return not self.is_buffer_empty() and self.position < len(self.buffer) - 1

    def append(self, value):
        # If we've already tried undoing, truncate the list
        if self.has_something_to_redo():
            del self.buffer[self.position:]
        self.buffer.append(value)
        self.position += 1

    def undo(self):
        """ Perform an undo action, using the entry in the undo buffer
        pointed to from the current position.

        Returns a string if an undo was performed, described the action
        that was undone, otherwise returns None.

        If there have been no previous calls to "undo", the current
        position will be the last entry in the buffer.
        If buffer is emtpy, will do nothing.
        """
        if self.has_something_to_undo(): # silently ignore calls if nothing to undo.
            memo = self.buffer[self.position]
            self.bypass = True # If the "undo" function is also "undoable", we don't want to keep track of that undo.
            memo.undo()
            self.bypass = False
            self.position -= 1
            return memo.description
        return None

    def redo(self):
        """
        Returns a string if an redo was performed, described the action
        that was redone, otherwise returns None.
        """
        if self.has_something_to_redo():  # silently ignore calls if nothing to redo.
            memo = self.buffer[self.position]
            self.bypass = True # If the "redo" function is also "undoable", we don't want to keep track of that undo.
            memo.redo()
            self.bypass = False
            self.position += 1
            return memo.description
        return None

