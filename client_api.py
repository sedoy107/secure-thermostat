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


'''
' Client api module. Function mappings for client, cli interfaces with the actual functions that perform the actual action.
' Each function has 2 definitions, remote and client. The remote function is used to invoke a desired functionality
' on the server. The client functions invoke the corresponding functions on the server side.
' 
' Module architecture:
'   The module constantly running the TCP server that listens on the port specified in the appropriate section in
'   the config.py file. When the connection is accepted the module fetches TCP payload and tries to interprit it
'   as a a valid API with parameters:
'       - If the object is successfully interprited, then the corresponding action is invoked and the result
'         is packed into the SSHRPC compliant format and passed back the interface module that has initiated
'         the action.
'       - If the object was not interprited correctly then the ClientError is thrown with an appropriate error code.
'         The error handling procedure must ensure that the error correctly delivered to the callee(remote user).
'         The exception is handeled as follows:
'           1. An instance of the CLIENTError is created with appropriate parameters and is packed into SSHRPC
'              compliant character buffer, and passed to the interface module, which further passes it to the callee.
'           2. The actulal error is simply printed on the server's stdout/stderr, and after that is supressed or handled,
'              whichever is needed. 
'
' Auxilary functions:
'   All read functions are ultimately converge to 3 auxilary functions, that are diverced as follows:
'       1. Read functions that read dynamic data (tables with frequently changing data)
'       2. Read functions that read static data (tables with static data)
'       3. Read functions that read histary data (tables with historic data)
'
' CLIENTError:
'   CLIENTError is the final error handling facility. All the errors on the lower layers are ultimately 
'   converge to the ClientError. The ClientError distinguishes all the error types raised earlier and 
'   is able to deliver truthful error information to the callee.
'   The ClientError should never be thrown at the server's side. It is only for remote party.
'
'   Each of the APIs defined in this module there must be appropriate exceptions provided.
'   
'''

import mysql.connector

from common import *
from db_api import DBError
from sys_api import AUTHError, CLIENTError
import sys_api as API
import ics_proto as P
from ics_types import *
import sensor as S
import hvac as H
from datetime import datetime
import sshrpc

########################### FUNCTION DEFINITIONS #############################


# Account management function definitions
def createUser(username, password):
    try:
        API.register_client(username, password)
    except AUTHError as authError:
        if authError.getError() == AUTHError.INTEGRITY_VIOLATION:
            # replace known errors 
            raise CLIENTError("username '{0}' already exists".format(username), CLIENTError.ACCOUNT_ERROR)
        else:
            raise authError
    except mysql.connector.errors.OperationalError:  # Connection with database failed # This happens if the connection with database is not established (the service itself is active though in this case)
        raise CLIENTError("couldn't establish connection with database", CLIENTError.DATABASE_ERROR)
    except mysql.connector.errors.ProgrammingError:  # The target table does not exist # This happens in case of wrod sytax and malformed statements
        raise CLIENTError("database corrupted", CLIENTError.DATABASE_ERROR)
    except mysql.connector.errors.InterfaceError:  # The target table does not exist # This happen is I manually stop DB service, so there isnothing to connect to
        raise CLIENTError("no database service available", CLIENTError.DATABASE_ERROR)
    
    
          
def deleteUser(auth_id, username, pass_hash, user_to_kill):
    try:
        API.unregister_client(user_to_kill)
    except AUTHError as authError:
        if authError.getError() == AUTHError.INTEGRITY_VIOLATION:
            raise CLIENTError("username '{0}' is currently set; you have to call logout".format(username), CLIENTError.ACCOUNT_ERROR)
        else:
            raise authError


def login(auth_id, username, pass_hash):
    try:
        loginID=API.set_client(auth_id, username, pass_hash)
        print "Your authentication id is : {0}".format(loginID)
        return loginID
    except AUTHError as authError:
        if authError.getError() == AUTHError.INTEGRITY_VIOLATION:
            print "user '{0}'already logged in".format(username)
            #raise CLIENTError("username '{0}' is currently logged in".format(username), CLIENTError.ACCOUNT_ERROR)
        elif authError.getError() == AUTHError.ORIGIN_ERROR:
            raise CLIENTError("username '{0}' doesn't exist".format(username), CLIENTError.ORIGIN_ERROR)
        elif authError.getError() == AUTHError.OBJECT_NOT_FOUND:
            raise CLIENTError("sorry, session for username '{0}' has expired".format(username), CLIENTError.EXPIRATION)
        else:
            raise authError
    except DBError as dbError:
        if dbError.getError()==DBError.DUP_KEY_ERROR:
            raise CLIENTError("username '{0}' already logged in ".format(username),CLIENTError.ACCOUNT_ERROR)
        else:
            raise dbError

def logout(auth_id, username, pass_hash):
    login(auth_id, username, pass_hash)
    try:
        API.unset_client(auth_id)
    except AUTHError as authError:
        if authError.getError() == AUTHError.OBJECT_NOT_FOUND:
            raise CLIENTError("Sorry, either you are not logged in or session for authentication id '{0}' has already expired".format(auth_id), CLIENTError.EXPIRATION)
        else:
            raise authError

def changePassword(auth_id, username, pass_hash, new_pass_hash):
    login(auth_id, username, pass_hash)
    API.changePwd(auth_id, pass_hash, new_pass_hash)

# Job posting function definition
def postJob(auth_id, username, pass_hash, start_time, period, hvac_id, hvac_fan, hvac_mode, hvac_temp, hvac_delta):
    login(auth_id, username, pass_hash)
    _start_time = timestamp(t=start_time)
    t_diff = (datetime.strptime(_start_time, config.DATE_FORMAT) - datetime.strptime(timestamp(), config.DATE_FORMAT)).total_seconds()
    if t_diff <= 0:
        job_type = config.CURRENT
        API.unset_job(job_type=config.CURRENT, hvac_id=hvac_id)
    else:
        job_type = config.DELAYED
    ts = timestamp()
    API.set_job(job_type, auth_id, _start_time, ts, period, hvac_id, hvac_fan, hvac_mode, hvac_temp, hvac_delta)
    return _start_time

# Job cancel function definition
def cancelJob(auth_id, username, pass_hash, job_id=None, job_type=None, hvac_id=None):
    login(auth_id, username, pass_hash)
    res = API.unset_job(job_id, job_type, hvac_id)
    # For each CURRENT job check we must make sure that the HVAC will be turned off
    for k,v in res.iteritems():
        if v.job_type == config.CURRENT:
            try:
                # Syncronize HVAC data
                c_hvac, h_info, h_data = API.sync_hvac(v.hvac_id)
                if h_data == None:
                    raise CLIENTError("hvac didn't respond on request", CLIENTError.DESYNCHRONIZATION)
            except API.CLIENTError as err:
                print err
                if err.getError() == CLIENTError.INTEGRITY_VIOLATION or err.getError() == CLIENTError.DESYNCHRONIZATION: # If the hvac static data changed
                    host, port = tuple(v.hvac_id.split(':')) 
                    unset_hvac(host, int(port)) # then unset the hvac
            except sshrpc.SSHRPCError as err:
                print err
                if err.getError() == sshrpc.SSHRPCError.REMOTE_EXCEPTION: # If the hvac static data changed
                    host, port = tuple(j.hvac_id.split(':')) 
                    unset_hvac(host, int(port)) # then unset the hvac
            # Finally turn off all HVAC signals
            API.set_hvac_state(c_hvac, h_info, 0, 0, 0)

# Read dynamic data function definitions
def read_current_clients(auth_id, username, pass_hash):
    login(auth_id, username, pass_hash)
    return API.read(current_clients_table)
    
def read_current_hvacs(auth_id, username, pass_hash):
    login(auth_id, username, pass_hash)
    return API.read(current_hvacs_table)
    
def read_current_sensors(auth_id, username, pass_hash):
    login(auth_id, username, pass_hash)
    return API.read(current_sensors_table)
    
def read_jobs(auth_id, username, pass_hash):
    login(auth_id, username, pass_hash)
    return API.read(hvac_jobs_table)

# Read static data function definitions
def read_users(auth_id, username, pass_hash):
    login(auth_id, username, pass_hash)
    return API.read(users_table)
    
def read_hvacs(auth_id, username, pass_hash):
    login(auth_id, username, pass_hash)
    return API.read(hvacs_table)
    
def read_sensors(auth_id, username, pass_hash):
    login(auth_id, username, pass_hash)
    return API.read(sensors_table)

# Read history functions function definitions
def read_history_clients(auth_id, username, pass_hash, fromDate=timestamp(t=0), toDate=timestamp()):
    login(auth_id, username, pass_hash)
    try:
        return API.read_history(clients_history_table,fromDate, toDate)
    except DBError as dbError:
        print dbError
        raise CLIENTError("couldn't perform read from 'clients_history_table'", CLIENTError.DATABASE_ERROR)
    
def read_history_hvacs(auth_id, username, pass_hash, fromDate=timestamp(t=0), toDate=timestamp()):
    login(auth_id, username, pass_hash)
    try:
        return API.read_history(hvacs_history_table, fromDate, toDate)
    except DBError as dbError:
        print dbError
        raise CLIENTError("couldn't perform read from 'read_history_hvacs'", CLIENTError.DATABASE_ERROR)

def read_history_sensors(auth_id, username, pass_hash, fromDate=timestamp(t=0), toDate=timestamp()):
    login(auth_id, username, pass_hash)
    try:
        return API.read_history(sensors_history_table,fromDate, toDate)
    except DBError as dbError:
        print dbError
        raise CLIENTError("couldn't perform read from 'sensors_history_table'", CLIENTError.DATABASE_ERROR)
        

def read_history_hvac_job(auth_id, username, pass_hash, fromDate=timestamp(t=0), toDate=timestamp()):
    login(auth_id, username, pass_hash)
    try:
        return API.read_history(hvac_job_history_table,fromDate, toDate,field="start_time")
    except DBError as dbError:
        print dbError
        raise CLIENTError("couldn't perform read from 'hvac_job_history_table'", CLIENTError.DATABASE_ERROR)

def set_hvac(auth_id, username, pass_hash, host, port, sensor_id):
    login(auth_id, username, pass_hash)
    API.set_hvac(host, port, sensor_id)

def unset_hvac(auth_id, username, pass_hash, host, port):
    login(auth_id, username, pass_hash)
    API.unset_hvac(host, port)

def set_sensor(auth_id, username, pass_hash, host, port, path, status, priority):
    login(auth_id, username, pass_hash)
    API.set_sensor(host, port, path, status, priority)

def unset_sensor(auth_id, username, pass_hash, host, port, path):
    login(auth_id, username, pass_hash)
    API.unset_sensor(host, port, path)

def register_hvac(auth_id, username, pass_hash, host, port, user_name, password, path, protocol, cool_wattage, heat_wattage, cool_kwph=0, heat_kwph=0, description=None):
    login(auth_id, username, pass_hash)
    API.register_hvac(host, port, user_name, password, path, protocol, cool_wattage, heat_wattage, cool_kwph, heat_kwph, description)

def unregister_hvac(auth_id, username, pass_hash, host, port):
    login(auth_id, username, pass_hash)
    API.unregister_hvac(host, port)

def register_sensor(auth_id, username, pass_hash, stype, host, port, user_name, password, path, protocol):
    login(auth_id, username, pass_hash)
    API.register_sensor(stype, host, port, user_name, password, path, protocol)

def unregister_sensor(auth_id, username, pass_hash, host, port, path):
    login(auth_id, username, pass_hash)
    API.unregister_sensor(host, port, path)

def get_essentials(auth_id, username, pass_hash):
    login(auth_id, username, pass_hash)
    return API.read(hvac_jobs_table), API.read(hvacs_table), API.read(sensors_table), API.read(current_hvacs_table), API.read(current_sensors_table), API.read(hvacs_history_table), API.read(sensors_history_table)

def clean_hvacs_hist(auth_id, username, pass_hash, fromDate, toDate):
    API._cleanup(hvacs_history_table,fromDate,toDate)

def clean_sensors_hist(auth_id, username, pass_hash, fromDate, toDate):
    login(auth_id, username, pass_hash)
    API._cleanup(sensors_history_table, fromDate, toDate)

def clean_clients_hist(auth_id, username, pass_hash, fromDate, toDate):
    login(auth_id, username, pass_hash)
    API._cleanup(clients_history_table, fromDate, toDate)

def clean_jobs_hist(auth_id, username, pass_hash, fromDate, toDate):
    login(auth_id, username, pass_hash)
    API._cleanup(hvac_job_history_table, fromDate, toDate, field='end_time')

if __name__ == '__main__':
    pass
