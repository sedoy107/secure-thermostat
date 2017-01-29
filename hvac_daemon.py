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


import sys, os
import socket
import argparse
import socket
import time
import ics_proto as P
import atomic
import RPi.GPIO as GPIO
import config
import atomic
from threading import Thread, Timer
from common import *

h_timeout_key = atomic.AtomicUnit(0)
c_timeout_key = atomic.AtomicUnit(0)

# GPIO pins
COOL = 13
FAN = 19
HEAT = 26

GPIO.setmode(GPIO.BCM)

class gpio:
  def __init__(self):
    self.d = {}
  def addout(self, pin):
    GPIO.setup(pin, GPIO.OUT)
    self.d[pin] = GPIO.LOW
  def addin(self, pin):
    os.stderr.write("Not implemented yet\n")
  def turn(self, index, state):
    if index in self.d:
      lvl = GPIO.LOW
      if state == 1:
        lvl = GPIO.HIGH
      self.d[index] = lvl
      GPIO.output(index, self.d[index])
      return 0
    else:
      return -1 
  def get(self, index):
    if index in self.d:
      return self.d[index]
    return -1
      


class daemon(Thread):
    def __init__(self, host, port):
        Thread.__init__(self)
        # Metadata
        self.status = atomic.AtomicUnit()
        self.port = port
        self.host = host
        self.addr = (self.host, self.port)
        # Socket attributes
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setblocking(0)
        try:
            self.sock.bind(self.addr)
        except socket.error as e:
            raise
        self.sock.listen(0)
        
        self.current_params = P.HVACParams(0,0,0)
        
        self.g = gpio()
        self.g.addout(COOL)
        self.g.turn(COOL, 0)
        self.g.addout(FAN)
        self.g.turn(FAN, 0)
        self.g.addout(HEAT)
        self.g.turn(HEAT, 0)
        
        print "HVAC daemon initialized on port %s" % self.port
    def stop(self):
        self.status.set(0x01)
        self.sock.close()
    def run(self):
        print "Server started on port %s" % self.port
        while(self.status.get() == 0x00):
            try:
                connection, client_address = self.sock.accept()
            except socket.error:
                time.sleep(0.1)
                continue
            print "Connection accepted from %s:%s" % client_address
            data = connection.recv(1024)
            obj = unpic(data)
            if obj != None:
                global h_timeout_key
                global c_timeout_key        
                if P.verify(obj):
                    if obj.cntl.fcode == P.FETCH_PARAMS:
                        self.current_params.cool = self.g.get(COOL)
                        self.current_params.fan = self.g.get(FAN)
                        self.current_params.heat = self.g.get(HEAT)
                        self.current_params.h_timeout_key = h_timeout_key.get()
                        self.current_params.c_timeout_key = c_timeout_key.get()
                        obj.params = self.current_params
                        obj.cntl.status = P.OK
                    elif obj.cntl.fcode == P.SET_PARAMS:
                        '''
                        When setting HVAC from HEAT to COOL and vice versa, use the timeout to make sure that
                        the current mode turns off prior the newly set mode is engaged.
                        '''
                        h_prev_state = self.g.get(HEAT)
                        c_prev_state = self.g.get(COOL)
                        
                        '''Transition of HEATER on -> off: Engaging the cool signal timeout'''
                        if h_prev_state == GPIO.HIGH and obj.params.heat == GPIO.LOW:
                            c_timeout_key.inc()
                            timer = Timer(config.HVAC_H_TIMEOUT, c_timeout_key.dec)
                            timer.start()
                        '''Transition of COOLER on -> off: Engaging the heat signal timeout'''
                        if c_prev_state == GPIO.HIGH and obj.params.cool == GPIO.LOW:
                            h_timeout_key.inc()
                            timer = Timer(config.HVAC_C_TIMEOUT, h_timeout_key.dec)
                            timer.start()
                        
                        
                        ''' If heat signal is requested to be on but heat timeout is engaged then do not change the HVAC state or'''
                        ''' If cool signal is requested to be on but cool timeout is engaged then do not change the HVAC state '''
                        if obj.params.heat == GPIO.HIGH and h_timeout_key.get() > 0:
                            print "HVAC_DAEMON: Heat timeout is engaged: [{0}]".format(h_timeout_key.get())
                        elif obj.params.cool == GPIO.HIGH and c_timeout_key.get() > 0:
                            print "HVAC_DAEMON: Cool timeout is engaged: [{0}]".format(c_timeout_key.get())
                        else:
                            self.g.turn(COOL, obj.params.cool)
                            self.g.turn(FAN, obj.params.fan)
                            self.g.turn(HEAT, obj.params.heat)
                        
                        self.current_params.cool = self.g.get(COOL)
                        self.current_params.fan = self.g.get(FAN)
                        self.current_params.heat = self.g.get(HEAT)
                        self.current_params.h_timeout_key = h_timeout_key.get()
                        self.current_params.c_timeout_key = c_timeout_key.get()
                        obj.params = self.current_params
                        obj.cntl.status = P.OK
                        
                    elif obj.cntl.fcode == P.RESET or obj.cntl.fcode == P.EXIT:
                        self.g.turn(COOL, 0)
                        self.g.turn(FAN, 0)
                        self.g.turn(HEAT, 0)
                        self.current_params.cool = self.g.get(COOL)
                        self.current_params.fan = self.g.get(FAN)
                        self.current_params.heat = self.g.get(HEAT)
                        obj.params = self.current_params
                        obj.cntl.status = P.OK
                        if obj.cntl.fcode == P.EXIT:
                            self.stop()
                    else:
                        obj.cntl.status = P.FAIL
                        obj.cntl.msg = "Error: unknown function code %s" % obj.cntl.fcode
                    connection.send(pickle(obj))
                else:
                    connection.send(pickle(P.HVACFrame(P.Control(P.FAIL, None, "Error in HVAC daemon: bad HVACFrame structure"),None)))
            else:
                connection.send(pickle(P.HVACFrame(P.Control(P.FAIL, None, "Error in HVAC daemon: unrecognized object:\n\n---BEGIN--- %s\n---END---" % data),None)))
            connection.close()
        print "Server stopped"

s = daemon(config.HVAC_DEAMON_HOST, config.HVAC_DEAMON_PORT)
ERR = None
try:
    s.run()
except Exception as e:
    ERR = e
finally:
    print "Resetting GPIO"
    GPIO.cleanup()
    if ERR != None:
        raise ERR
