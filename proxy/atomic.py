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


from threading import Condition, Event, Lock, Thread, RLock, Timer

class AtomicUnit:
    def __init__(self, v=0x00, e=True):
        self.v = v
        self.lock = RLock()
        self.evt = Event()
        if e:
            self.evt.clear()
        else:
            self.evt.set()
    def event(self):
        return self.evt
    def set(self, v, e=True):
        self.lock.acquire()
        self.v = v
        if e and self.evt.is_set():
            self.evt.clear()
        else:
            self.evt.set()
        self.lock.release()
    def get(self):
        self.lock.acquire()
        v = self.v
        self.lock.release()
        return v
    def inc(self, v=1, e=True):
        self.lock.acquire()
        self.v += v
        if e and self.evt.is_set():
            self.evt.clear()
        else:
            self.evt.set()
        self.lock.release()
    def dec(self, v=1, e=True):
        self.lock.acquire()
        self.v -= v
        if e and self.evt.is_set():
            self.evt.clear()
        else:
            self.evt.set()
        self.lock.release()
#~ gcc -pthread -fno-strict-aliasing -DNDEBUG -g -fwrapv -O2 -Wall -Wstrict-prototypes -fPIC -DSWIG_TYPE_TABLE=_wxPython_table -DSWIG_PYTHON_OUTPUT_TUPLE -DSWIG_PYTHON_SILENT_MEMLEAK -DWXP_USE_THREAD=1 -UNDEBUG -D_FILE_OFFSET_BITS=64 -DWXUSINGDLL -D__WXGTK__ -Iinclude -Isrc -I/home/pi/wxPython-src-3.0.2.0/wxpy-bld/lib/wx/include/gtk3-unicode-3.0 -I/home/pi/wxPython-src-3.0.2.0/include -I/usr/include/python2.7 -c src/helpers.cpp -o build/temp.linux-armv7l-2.7/src/helpers.o -pthread -O3
