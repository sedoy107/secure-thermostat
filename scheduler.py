'''
	This file is part of Secure Thermostat project.
    Copyright (C) 2017  Sergey Gorbov

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''


from atomic import *
import time

class Task:
    READY = 'READY'
    SUSPENDED = 'SUSPENDED'
    RUNNING = 'RUNNING'
    STOPPED = 0xff
    def __init__(self, tag, task, tstamp, args, interval, sched_event):
        self.tag = tag
        self.task = task
        self.tstamp = tstamp
        self.args = args
        self.interval = interval
        self.sched_event = sched_event
        self.et = EventTable()
        self.result = None
        self.status = AtomicUnit(v=Task.READY)
        self.thread = None
    def start(self):
        if self.args == None:
            self.thread = Thread(target=self.task)
            self.thread.start()
        else:
            try:
                args = list(self.args)
            except TypeError:
                args = [args]
            self.thread = Thread(target=self.task, args=args)
            self.thread.start()
    def suspend(self, event, timeout=None):
        Thread(target=self._suspend_, args=(event,timeout,)).start()
    def _suspend_(self, event, timeout=None):
        self.status.set(Task.SUSPENDED)
        print "Task %s suspended" % self.tag
        if timeout != None:
            event.wait(timeout)
        else:
            event.wait()
        if self.status.get() == Task.SUSPENDED:
            self.status.set(Task.READY)
            print "Task %s resume" % self.tag
            self.sched_event.set()
        elif self.status.get() == Task.STOPPED:
            print "Task %s has already been stopped" % self.tag
    def stop(self):
        self.status.set(Task.STOPPED)

class Scheduler(Thread):
    TIMEOUT = 10
    def __init__(self):
        Thread.__init__(self)
        self.lock = Lock()
        self.task_table = {}
        self.status = AtomicUnit()
        self.loop_event = Event()
        self.loop_event.clear()
    def getJob(self, tag):
        try:
            self.lock.acquire()
            return self.task_table[tag]
        except KeyError:
            return None
        finally:
            self.lock.release()
    def list(self):
        self.lock.acquire()
        for k,v in self.task_table.iteritems():
            print '{0} : {1} : {2} : {3}'.format(k, v.interval, v.task, v.args)
        self.lock.release()
    def enter(self, task, interval, args, tag, delay=0):
        self.lock.acquire()
        task = Task(tag, task, time.time(), args, interval, self.loop_event)
        if delay > 0:
            e = Event()
            e.clear()
            task.suspend(e)
            Timer(delay, e.set).start()
        self.task_table[tag] = task
        if Scheduler.TIMEOUT < interval:
            print "Scheduler timeout changed from {0} to {1}".format(Scheduler.TIMEOUT, interval)
            Scheduler.TIMEOUT = interval
        self.loop_event.set()
        self.lock.release()
        print "Task %s added to scheduler" % tag
    def stop(self):
        self.status.set(0xff, False)
        self.loop_event.set()
    def suspend(self, task_tag, event, timeout=None):
        if task_tag in self.task_table:
            self.task_table[task_tag].suspend(event, timeout)
    def resetWaitFor(self, tag):
        try:
            self.lock.acquire()
            self.task_table[tag].status.event().set()
            return True
        except KeyError as err:
            print "The job {0} either missing in, or has been removed from the task table".format(tag)
            return False
        finally:
            self.lock.release()
    def run(self):
        print "Scheduler started"
        while self.status.get() != 0xff:
            i = 0
            print '---'
            self.loop_event.wait(timeout=Scheduler.TIMEOUT)
            self.lock.acquire()
            if self.status.get() == 0xff: # The status may change during the waiting, so we should check on it
                self.lock.release()
                break
            for k,v in self.task_table.iteritems():
                if v.status.get() == Task.READY:
                    i = 1
                    v.status.set(Task.RUNNING)
                    v.status.event().clear()
                    v.tstamp = time.time()
                    v.start()
                    self.loop_event.clear()
                    Thread(target=self._joiner_, args=(v,)).start()
            if i == 0:
                self.loop_event.clear()
                
            self.lock.release()
        print "Scheduler stopped"
    def rm(self, tag):
        self.lock.acquire()
        if tag in self.task_table:
            self.task_table[tag].stop()
            self.task_table[tag].status.event().set()
            del self.task_table[tag]
            print "Task %s removed from scheduler" % tag
            if len(self.task_table) == 0:
                self.loop_event.clear()
            self.lock.release()
            return 0
        else:
            self.lock.release()
            return -1
    def _joiner_(self, task):
        if task.status.get() == Task.RUNNING:
            try:
                task.thread.join()
            except RuntimeError as err:
                print 'Allakh Akbar', err
            task.status.event().wait(task.interval)
            task.status.set(Task.READY)
            self.lock.acquire()
            if len(self.task_table) != 0:
                self.loop_event.set()
            self.lock.release()
        else:
            pass # In case if a job gets stopped we just do not set the event

class EventTable:
    def __init__(self):
        self.etbl = {}
        self.lock = Lock()
    def add(self, event_id):
        self.lock.acquire()
        if event_id in self.etbl and not self.etbl[event_id].is_set:
            print "Found confilicting event: %s. Setting it on." % event_id
            self.etbl[event_id].set()
        #print "Setup new event %s" % event_id)
        e = Event()
        self.etbl[event_id] = e
        self.etbl[event_id].clear()
        self.lock.release()
        return e
    def post(self, event_id):
        self.lock.acquire()
        if event_id in self.etbl:
            self.etbl[event_id].set()
            retval = 0
        else:
            retval = -1
        self.lock.release()
        return retval
    def check(self, event_id):
        self.lock.acquire()
        if event_id in self.etbl:
            retval = not self.etbl[event_id].is_set()
        else:
            retval = False
        self.lock.release()
        return retval
    def p(self):
        for i in range(0,10,1):
            e = self.add(i)
            res = e.wait(1)
            if res:
                print "Event %s went through" % i
            else:
                print "Event %s timed out" % i
    def c(self):
        for i in range(0,10,1):
            time.sleep(0.1)
            e = self.post(i)
    def test(self):
        Thread(target=self.p).start()
        Thread(target=self.c).start()

P1 = 0
P2 = 0
P3 = 0
P4 = 0

def pt():
    print time.time()
def p1():
    global P1
    P1 += 1
    print 'p1:', P1
def p2():
    global P2
    P2 += 1
    print 'p2:', P2
def p3():
    global P3
    P3 += 1
    print 'p3:', P3
def p4():
    global P4
    P4 += 1
    print 'p4:', P4
def test_scheduler(duration):
    s = Scheduler()
    s.enter(pt, 0.5, (), 'j1')
    s.enter(p1, 0.2, (), 'j2')
    s.enter(p2, 0.2, (), 'j3')
    s.enter(p3, 0.2, (), 'j4')
    s.enter(p4, 1, (), 'j5', 1)
    s.start()
    s.resetWaitFor('j5')
    time.sleep(1)
    s.rm('j2')
    s.rm('j1')
    s.rm('j3')
    s.rm('j4')
    s.rm('j5')
    time.sleep(1)
    s.enter(pt, 0.5, (), 'j1')
    s.enter(p1, 0.2, (), 'j2')
    s.enter(p2, 0.2, (), 'j3')
    s.enter(p3, 0.2, (), 'j4')
    s.enter(p4, 1, (), 'j5')
    time.sleep(duration)
    s.stop()
if __name__ == '__main__':
    test_scheduler(3)
    #~ TI = ThermostatInterface()
    #~ TI.connect('172.17.0.2', 22, 'sergey', sha512('321'))
    #~ TI.disconnect()
