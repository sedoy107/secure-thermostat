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


import cPickle as pic
import base64
import ics_types as T
import sshrpc
from common import *
import sys
import sensor_interface as SI


class SensorError(Exception):
    PREFIX = 'Sensor error'
    UNKNOWN_SENSOR = 0xff
    UNKNOWN_STATUS = 0xfe
    KNOWN_ERRORS = {UNKNOWN_SENSOR:'UNKNOWN_SENSOR', UNKNOWN_STATUS:'UNKNOWN_STATUS'}
    """ COMMON PART FOR EXCEPTION CLASS 
    '   IF an exception needs to be declared, all you need to do is just define the 
    '   PREFIX, error constants and KNOWN_ERRORS which must contain the defined error codes.
    '   The part below can be copied and pasted to a new exception class
    """
    def __init__(self, msg, errno=None):
        self.msg = msg
        self.errno = errno
    def __str__(self):
        if self.errno == None:
            return repr("{0}: {1}".format(self.__class__.PREFIX, self.msg))
        elif self.errno in self.__class__.KNOWN_ERRORS:
            return repr("{0}(#{1}: {2}): {3}".format(self.__class__.PREFIX, self.errno, self.__class__.KNOWN_ERRORS[self.errno], self.msg))
        else:
            raise Exception("Bad error code {0}. KNOWN_ERRORS = {1}".format(self.errno, self.__class__.KNOWN_ERRORS))
    def getError(self):
        return self.errno
    @staticmethod
    def test(code=None):
        try:
            raise ICSTypeError('Hello world', code)
        except ICSTypeError as err:
            print err
            raise err


# Sensor status
ACTIVE = 1
INACTIVE=0

# Sensor types
class BS18D20:
  @staticmethod
  def interprit(raw, *argv):
    floor = 1
    Celsius=False
    if len(argv) > 0:
      floor = argv[0]
    if len(argv) > 1:
      Celsius = argv[1]
    T_pos = raw.find('t=')
    T = int(raw[T_pos+2:])
    F = (T * 9/5 + 32000)/floor
    C = T/floor
    if Celsius:
      return C
    return F

SENSORS = [BS18D20]

def query(path, host, port, username, password=None, keep_alive=False):
    s = sshrpc.sshrpc(host, port, username, password)
    try:
        obj = s.execute("python sensor_interface.py", SI.read_bs18d20, path)
    except sshrpc.SSHRPCError as ex:
        raise ex
    if not keep_alive:
        s.close()
    return obj


if __name__ == '__main__':

    print BS18D20.interprit(query('/sys/bus/w1/devices/28-011600571dff/w1_slave', '192.168.7.187', 22, 'sensor', keep_alive=True), 1000, False)
    print BS18D20.interprit(query('/sys/bus/w1/devices/28-011600571dff/w1_slave', '192.168.7.187', 22, 'sensor', keep_alive=True), 1000, False)
    print BS18D20.interprit(query('/sys/bus/w1/devices/28-011600571dff/w1_slave', '192.168.7.187', 22, 'sensor', keep_alive=True), 1000, False)
    print BS18D20.interprit(query('/sys/bus/w1/devices/28-011600571dff/w1_slave', '192.168.7.187', 22, 'sensor', keep_alive=True), 1000, False)
    print BS18D20.interprit(query('/sys/bus/w1/devices/28-011600571dff/w1_slave', '192.168.7.187', 22, 'sensor', keep_alive=True), 1000, False)
    print BS18D20.interprit(query('/sys/bus/w1/devices/28-011600571dff/w1_slave', '192.168.7.187', 22, 'sensor', keep_alive=True), 1000, False)
    print BS18D20.interprit(query('/sys/bus/w1/devices/28-011600571dff/w1_slave', '192.168.7.187', 22, 'sensor', keep_alive=True), 1000, False)
    sshrpc.clean_registry()
