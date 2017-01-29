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
import ics_proto as P
import sshrpc
from common import *
import sys
import hvac_interface as HI
import proxy_interface as PI

def modbus_exchange(params, host, port, username, password, keep_alive=False):
    s = sshrpc.sshrpc(host, port, username, password)
    obj = s.execute("python proxy_interface.py", PI.set_hvac, params)
    if not keep_alive:
        s.close()
    return obj


def exchange(params, host, port, username, password=None, keep_alive=False):
    s = sshrpc.sshrpc(host, port, username, password)
    obj = s.execute("python hvac_interface.py", HI.set_hvac, params)
    if not keep_alive:
        s.close()
    return obj


if __name__ == '__main__':

    p = P.HVACParams(0,0,0)
    c = P.Control(P.FAIL, P.SET_PARAMS)
    a = P.HVACFrame(c,p)
    #obj = modbus_exchange(a, '172.17.0.2', 22, 'root', 'root')
    import time
    t1 = time.time()
    for i in range(0,10,1):
        if i%2 == 0:
            p.heat = 1
            p.cool = 0
            p.fan =  1
        else:
            p.heat = 0
            p.cool = 0
            p.fan =  0
        obj = modbus_exchange(a, '192.168.1.198', 22, 'hvac', 'pihvac1', keep_alive=True)
        #obj = PI.set_hvac(a)
    print "Execution time = {0}".format(time.time() - t1)
    #~ obj = exchange(a, '192.168.7.187', 22, 'hvac')
    #~ p.heat = 1
    #~ p.cool = 0
    #~ p.fan =  1
    
    print obj


