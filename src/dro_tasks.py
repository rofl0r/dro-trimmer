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
import threading
import time
import dro_globals


class TaskThread(threading.Thread):
    """Based on threading.Timer from the standard library.
    You can pass in a "cancel_function" to also be called when the task thread is cancelled.
    An event will be raised when the thread finishes normally, or when cancel is called. It
    does not necessarily indicate that the thread has terminated; it could still run in
    the background.

    Creates events:
     "TASK_FINISHED" when the task has finished normally or been cancelled. To be used by the task manager.
      The returned event object contains a "task" attribute, which is this TaskThread's instance (self).
     "TASK_{NAME}_STARTED" (where "{NAME}" is replaced by the task's name), when the task's callable is
      about to begin.
     "TASK_{NAME}_FINISHED" (where "{NAME}" is replaced by the task's name), when the task's callable has
      finished execution. The returned event object contains a "result" attribute, which is the returned value from
-      the callable.

    Requires "g_customer_event_manager" to be set in the dro_globals module.
    """

    def __init__(self,
                 name,
                 interval,
                 function,
                 cancel_function,
                 args=None,
                 kwargs=None):
        threading.Thread.__init__(self)
        self.name = name
        self.interval = interval
        self.function = function
        self.args = [] if args is None else args
        self.kwargs = {} if kwargs is None else kwargs
        self.cancel_function = cancel_function
        self.finished = threading.Event()

    def cancel(self):
        """Stop the timer if it hasn't finished yet, or to interrupt normal execution.
        Will attempt to call """
        self.finished.set()
        if self.cancel_function is not None:
            self.cancel_function()
        dro_globals.custom_event_manager().trigger_event("TASK_FINISHED", task=self)

    def run(self):
        self.finished.wait(self.interval)
        if not self.finished.is_set():
            dro_globals.custom_event_manager().trigger_event("TASK_%s_STARTED" % (self.name,))
            result = self.function(*self.args, **self.kwargs)
            dro_globals.custom_event_manager().trigger_event("TASK_%s_FINISHED" % (self.name,),
                                                             result=result)
        self.finished.set()
        dro_globals.custom_event_manager().trigger_event("TASK_FINISHED", task=self)


class TaskMaster(object):
    def __init__(self):
        self.tasks = {}
        #self.dead_tasks = {}

    def start_task(self, task_name, delay, callable, cancel_callable, callable_args=None, callable_kwds=None):
        self.tasks[task_name] = TaskThread(task_name, delay, callable, cancel_callable, callable_args, callable_kwds)
        self.tasks[task_name].start()

    def cancel_task(self, task_name):
        if task_name in self.tasks:
            self.tasks[task_name].cancel()

    def stop_all_tasks(self):
        """ Should be called from the main thread. Otherwise, the wx app could close
        before all tasks have been joined, which could lead to a crash.
        """
        active_tasks_exist = len(self.tasks) > 0
        while active_tasks_exist:
            active_tasks_exist = False
            for task in self.tasks.values():
                task.cancel()
                task.join(0.5)
                active_tasks_exist |= task.isAlive()
            if active_tasks_exist:
                time.sleep(0.5)

    def _task_ended(self, event):
        evt_task = event.task
        registered_task = self.tasks[event.task_name]
        if registered_task is evt_task:
            del self.tasks[event.task_name]
        # Doesn't seem to work - causes crashes. Hmm.
#        else:
#            registered_task.join(0.1)
#        evt_task.join(0.1)
