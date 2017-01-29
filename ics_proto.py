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


#
# Basic structures that are necessary to describy the interaction with a HVAC and CLIENT unit
# The described classes are used as plain structures.
#

import config

# HVAC Protocol functions codes
FETCH_PARAMS = 'FETCH_PARAMS'
SET_PARAMS = 'SET_PARAMS'
EXIT = 'EXIT'
RESET = 'RESET'
HVAC_FC_LIST = [FETCH_PARAMS, SET_PARAMS, EXIT, RESET]

# HVAC modes
HEAT = 'HEAT'
COOL = 'COOL'
CLIM = 'CLIM'
OFF = 'OFF'
HVAC_MODES = [HEAT,COOL,CLIM,OFF]

# FAN modes
AUTO = 'AUTO'
ON = 'ON'
FAN_MODES = [AUTO,ON]

# HVAC control signal levels
HIGH = 0x1
LOW = 0x0
SIGNALS = [HIGH, LOW]

# Protocol status options
OK = 'OK'
FAIL = 'FAIL'
STATUS_LIST = [OK,FAIL]

# CLIENT Protocol function codes
AUTH = 'AUTH'
LOGOUT = 'LOGOUT'
CHPASS = 'CHPASS'
CLIENT_FC_LIST = [AUTH, LOGOUT, CHPASS]

class HVACParams:
  def __init__(self,fan,heat,cool):
    self.fan = fan
    self.heat = heat
    self.cool = cool
    self.h_timeout_key = 0
    self.c_timeout_key = 0

class Control:
  def __init__(self,status,fcode,msg=None):
    self.status = status
    self.fcode = fcode
    self.msg = msg

class HVACFrame:
  def __init__(self, cntl, params):
    self.cntl = cntl
    self.params = params

class HVACError(Exception):
  def __init__(self, value):
    self.value = value
  def __str__(self):
    return repr("HVAC error: "+self.value)

class CLIENTError(Exception):
  def __init__(self, value):
    self.value = value
  def __str__(self):
    return repr("CLIENT error: "+self.value)

class ProtoError(Exception):
  def __init__(self, value):
    self.value = value
  def __str__(self):
    return repr("Generic error: "+self.value)

class CLIENTAuth:
  def __init__(self, auth_id, username, pass_hash):
    self.auth_id = auth_id
    self.username = username
    self.pass_hash = pass_hash

class CLIENTData:
  def __init__(self,mode,fan,temp,delta):
    self.mode = mode
    self.fan = fan
    self.temp = temp
    self.delta = delta

class CLIENTFrame:
  def __init__(self, cntl, auth, data, in_data=None, out_data=None):
    self.cntl = cntl
    self.auth = auth
    self.data = data
    self.in_data = in_data
    self.out_data = out_data

def verify(frame):
  # If the current frame is HVACFrame
  if isinstance(frame, HVACFrame):
    try:
      # Check if the frame has Control instance
      if not isinstance(frame.cntl, Control):
        raise HVACError("HVACFrame malformed: the cntl field is not an instance of Control object.")
      # Check if the frame has HVACParams instance
      if not isinstance(frame.params, HVACParams):
        raise HVACError("HVACFrame malformed: the params field is not an instance of HVACParams object.")
      # Make sure that the heat and cool fields are never both set
      if frame.params.heat == frame.params.cool and frame.params.cool == HIGH:
        raise HVACError("Bad HVACParams object: signals heat and cool cannot be HIGH at the same time.")
      if frame.params.heat or frame.params.cool:
        frame.params.fan = HIGH
      a = frame.params.fan # Make sure we accessed all fields
      if not frame.cntl.status in STATUS_LIST:
        raise HVACError("Wrong HVAC status: Control object has unknown status: %s" % frame.cntl.status)
      if not frame.cntl.fcode in HVAC_FC_LIST:
        raise HVACError("Wrong HVAC function: Control object has unknown function code: %s" % frame.cntl.fcode)
      if not frame.params.heat in SIGNALS:
        raise HVACError("HVACParams malformed: HVAPParams has unknown signal level for heat field: %s" % frame.params.heat)
      if not frame.params.fan in SIGNALS:
        raise HVACError("HVACParams malformed: HVAPParams has unknown signal level for fan field: %s" % frame.params.fan)
      if not frame.params.cool in SIGNALS:
        raise HVACError("HVACParams malformed: HVAPParams has unknown signal level for cool field: %s" % frame.params.cool)
    except TypeError as err:
      raise err
  # Or if the current frame is CLIENTFrame
  elif isinstance(frame, CLIENTFrame):
    try:
      # Check if the frame has Control instance
      if not isinstance(frame.cntl, Control):
        raise HVACError("CLIENTFrame malformed: the cntl field is not an instance of Control object.")
      elif not isinstance(frame.auth, CLIENTAuth):
        raise HVACError("CLIENTFrame malformed: the auth field is not an instance of CLIENTAuth object.")
      elif isinstance(frame.data, CLIENTData):
        if not frame.data.mode in HVAC_MODES:
          raise HVACError("CLIENTData malformed: unknown HVAC mode supplied: %s." % frame.data.mode)
        if not frame.data.fan in FAN_MODES:
          raise HVACError("CLIENTData malformed: unknown FAN mode supplied: %s." % frame.data.fan)
        if frame.data.temp < config.TEMP_MIN or frame.data.temp > config.TEMP_MAX:
          raise HVACError("CLIENTData malformed: bad temperature value supplied: %s. Check config.py file for allowed ranges" % frame.data.temp)
        if frame.data.delta < config.DELTA_MIN or frame.data.delta > config.DELTA_MAX:
          raise HVACError("CLIENTFrame malformed: bad delta value supplied: %s. Check config.py file for allowed ranges" % frame.data.delta)
      a = frame.in_data
      a = frame.out_data
      if not frame.cntl.status in STATUS_LIST:
        raise HVACError("CLIENTFrame malformed: Control object has unknown status: %s" % frame.cntl.status)
      if not frame.cntl.fcode in CLIENT_FC_LIST:
        raise HVACError("CLIENTFrame malformed: Control object has unknown function code: %s" % frame.cntl.fcode)
      if not isinstance(frame.auth.pass_hash,str) or len(frame.auth.pass_hash) != config.DIGEST_LENGTH:
        raise HVACError("CLIENTAuth malformed: password hash is not sha512 digest: %s" % frame.auth.pass_hash)
      if len(frame.auth.username) > config.USERNAME_LENGTH:
        raise HVACError("CLIENTAuth malformed: username length is %s, the max allowed is %s." % (len(frame.auth.username),config.USERNAME_LENGTH))
      if not isinstance(frame.auth.auth_id, int) or frame.auth.auth_id < config.AUTH_ID_MIN or frame.auth.auth_id > config.AUTH_ID_MAX:
        raise HVACError("CLIENTAuth malformed: authentication id is not int or is out of range: %s" % frame.auth.auth_id)
    except TypeError as err:
      raise err
  else:
    raise ProtoError("Bad protocol format. Invalid object type: %s" % (frame.__class__.__name__))
  return True

if __name__ == '__main__':
    print "ICS PROTOCOL TEST:"
    hvacp = HVACParams(HIGH,HIGH,LOW)
    hvacc = Control(FAIL,RESET,'Hello')
    hvacf = HVACFrame(hvacc,hvacp)
    verify(hvacf)
    print hvacf.params.h_timeout_key
    
