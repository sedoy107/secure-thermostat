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


import socket
import time
import ics_proto as P
import sys, os
import sshrpc
import config
from common import *

def set_hvac(hvac_params):
    print hvac_params.cntl.fcode
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    addr = config.HVAC_DEAMON_HOST, config.HVAC_DEAMON_PORT
    sock.connect(addr)
    sock.send(pickle(hvac_params))
    res = unpic(sock.recv(1024))
    return res

if __name__ == '__main__':
    sshrpc.init()
