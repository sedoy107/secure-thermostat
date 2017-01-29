
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

from pymodbus.client.sync import ModbusTcpClient as ModbusClient
import ics_proto as P
import sys, os
import sshrpc
import config
from common import *

def set_hvac(hvac_params):
    P.verify(hvac_params)
    print hvac_params.cntl.fcode
    client = ModbusClient(config.MODBUS_HOST, port=config.MODBUS_PORT)
    client.connect()
    # Convert HVACFrame into modbus
    if hvac_params.cntl.fcode == P.FETCH_PARAMS:
        rr = client.read_coils(1, 3)
        print rr.bits
        hvac_params.params.cool, hvac_params.params.fan, hvac_params.params.heat = rr.bits[0], rr.bits[1], rr.bits[2]
    elif hvac_params.cntl.fcode == P.SET_PARAMS:
        client.write_coils(1, [ hvac_params.params.cool, hvac_params.params.fan, hvac_params.params.heat])
        rr = client.read_coils(1, 3)
        print rr.bits
        hvac_params.params.cool, hvac_params.params.fan, hvac_params.params.heat = rr.bits[0], rr.bits[1], rr.bits[2]
    elif hvac_params.cntl.fcode == P.RESET:
        client.write_coils(1, [0,0,0])
        rr = client.read_coils(1, 3)
        print rr.bits
        hvac_params.params.cool, hvac_params.params.fan, hvac_params.params.heat = rr.bits[0], rr.bits[1], rr.bits[2]
        #elif hvac_params.cntl.fcode == P.EXIT:
    else:
        client.write_coils(1, [0,0,0])
        rr = client.read_coils(1, 3)
        print rr.bits
        hvac_params.params.cool, hvac_params.params.fan, hvac_params.params.heat = rr.bits[0], rr.bits[1], rr.bits[2]
    hvac_params.cntl.status = P.OK
    return hvac_params

if __name__ == '__main__':
    
    sshrpc.init()
