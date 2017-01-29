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


from db_api import *
from ics_types import *
import ics_proto
from common import *
import random
import config
import sensor as S
from datetime import datetime
import sshrpc
import hvac as H
from threading import Lock
import logging, logger


S_CACHE = {}
S_LOCK = Lock()
H_CACHE = {}
H_LOCK = Lock()

LOG_NAME = 'sys_api.log'
logger.create_log(LOG_NAME, None)
log = logging.getLogger(LOG_NAME)


class CLIENTError(Exception):
    PREFIX = "Client error"
    BAD_PARAMETER = 0xff
    NONE_VALUE = 0xfe
    ACCOUNT_ERROR = 0xfd 
    ORIGIN_ERROR = 0Xfc  # value doesnt exists e.g. username doesnt exists in db to login using that username
    DATABASE_ERROR = 0Xfb
    INTEGRITY_VIOLATION = 0xfa
    DESYNCHRONIZATION = 0xf9
    EXPIRATION = 0xf0
    HVAC_ERROR = 0xef
    SENSOR_ERROR = 0xee
    KNOWN_ERRORS = {HVAC_ERROR:'HVAC_ERROR', DESYNCHRONIZATION:'DESYNCHRONIZATION', NONE_VALUE:'NONE_VALUE', BAD_PARAMETER:'BAD_PARAMETER', ACCOUNT_ERROR:'ACCOUNT_ERROR', ORIGIN_ERROR:'ORIGIN_ERROR', DATABASE_ERROR:'DATABASE_ERROR', EXPIRATION:'EXPIRATION', INTEGRITY_VIOLATION:'INTEGRITY_VIOLATION', SENSOR_ERROR:'SENSOR_ERROR'}
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
            return repr(
                "{0}(#{1}: {2}): {3}".format(self.__class__.PREFIX, self.errno, self.__class__.KNOWN_ERRORS[self.errno],
                                             self.msg))
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


class AUTHError(Exception):
    PREFIX = "Authentication error"
    BAD_PRIMARY_KEY = 0xff
    OBJECT_NOT_FOUND = 0xfe
    ORIGIN_ERROR = 0xfd
    INTEGRITY_VIOLATION = 0xfc
    KNOWN_ERRORS = {BAD_PRIMARY_KEY: 'BAD_PRIMARY_KEY', OBJECT_NOT_FOUND: 'OBJECT_NOT_FOUND',
                    ORIGIN_ERROR: 'ORIGIN_ERROR', INTEGRITY_VIOLATION: 'INTEGRITY_VIOLATION'}
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
            return repr(
                "{0}(#{1}: {2}): {3}".format(self.__class__.PREFIX, self.errno, self.__class__.KNOWN_ERRORS[self.errno],
                                             self.msg))
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

def get_connection():
    return db_init()

def close_connection(conn):
    conn.close()
    print "Connection with database closed."

def authenticate(conn, ics_type, key):
    # The point of having higher-level api is that it is narrowed down to a particular scope of problems
    # e.g. authenticate is used to just make sure that an object is specified by its primary key
    # does exist in the specified table.
    data = select(conn, ics_type, keyv=key)
    '''
     - make sure only one value is returned as we are checking only primary keys
     - multiple values returned is not authentication
    '''
    if len(data) == 1:
        return data
    elif len(data) == 0:
        raise AUTHError("no objects found with the supplied key: %s" % key, AUTHError.OBJECT_NOT_FOUND)
    else:
        raise AUTHError("multiple entries associated with the supplied key. Key: %s, Entries: %s" % (key, data),
                        AUTHError.BAD_PRIMARY_KEY)  # Show the programmer what's up is going on

'''
' Generates unique authentication id. 
' Uses recursion. Potentially can hand inti infinite loop. But we won't have 2^32 entries ever!!!
'''

def generate_auth_id(conn, ics_type):
    auth_id = random.randint(0, 1 << 31)
    # print "id ---> ", auth_id
    # sql_condition = "auth_id = " + str(auth_id)
    try:
        authenticate(conn, ics_type, auth_id)
        return generate_auth_id(conn, ics_type)
    except AUTHError as err:
        if err.getError() == AUTHError.OBJECT_NOT_FOUND:
            return auth_id  # Once we have found auth_id that is not in the table then return it
        else:
            print err
            raise err  # Otherwise a programmer has screwed up and supplied the wrong value for the primary key


"""
" Sets object into current_clients table.  Performs all necessary checks on whether the object is authentic
" and can be legally placed into the table. Verifies the origin of the object, i.e. whether it comes from 'users' table.
"""
def set_client(auth_id,username, pass_hash):
    if not isinstance(username, str):
        raise ParameterError("bad parameter 'username': {0}; 'str' type required".format(username), ParameterError.BAD_PARAMETER)
    if not isinstance(pass_hash, str):
        raise ParameterError("bad parameter 'pass_hash': {0}; 'str' type required".format(username), ParameterError.BAD_PARAMETER)
    if len(pass_hash) != 128:
        raise ParameterError("bad parameter 'pass_hash': {0}; SHA512 must have 128 characters, but has {1}".format(username, len(pass_hash)), ParameterError.BAD_PARAMETER)
    if not isinstance(auth_id, int) and not isinstance(auth_id, type(None)):
        raise ParameterError("bad parameter 'auth_id': {0}; 'int' type required".format(auth_id), ParameterError.BAD_PARAMETER)
    conn = get_connection()
    try:
        # If this function doesn't fail, i.e., throws an exception then the username is authenticated
        user_obj = authenticate(conn, users_table, username)[username]
        if user_obj.pass_hash != sha512(user_obj.username + user_obj.salt + pass_hash):
            raise CLIENTError("Wrong password", CLIENTError.ACCOUNT_ERROR) # This error will be caught by the a user(client) and handeled by the client side
        
    except AUTHError as err:
        if err.getError() == AUTHError.OBJECT_NOT_FOUND:
            close_connection(conn)
            raise AUTHError("couldn't verify the origin for the 'username' {0}".format(username), AUTHError.ORIGIN_ERROR)
        else:
            raise err
    
    if auth_id is None:
        # generate new auth_id that is unique
        auth_id = generate_auth_id(conn, current_clients_table)
       
        # generate new object with newly generated auth_id
        obj = current_clients_table(auth_id, username, timestamp(), timestamp())
        insert(conn, obj)  # add user to current_clients and store value of auth_id
    # check if auth_id exists in current_clients
    else:
        '''
        - Authenticate auth_id
        - Get last_inserted object in dictionary, raise exception if auth_id invalid
        '''
        try:
            # try to authenticate object with the supplied auth_id
            res_obj = authenticate(conn, current_clients_table, auth_id)
        except AUTHError as err:
            close_connection(conn)
            if err.getError() == AUTHError.OBJECT_NOT_FOUND:  # Object not found, authentication failed
                raise err  # We should handle this situation, when you supply the auth_id and the user with this auth_id has been removed from the current_clients table.
                # This can be possible if a user makes request and expires at the same time, so he is not in the table anymore when the request comes in
            else:  # Some other bad error accured
                raise err  # All other errors must be passed along
        '''
        - Now, user exists in current_clients,
        - Update entry if username matches for given auth_id
        '''
        if res_obj.get(auth_id).username == username:
            login_tstamp = res_obj.get(auth_id).login_tstamp  # get login time stamp
            # create new_obj with old login_stamp
            new_obj = current_clients_table(auth_id, username, timestamp(), login_tstamp)
            update(conn, new_obj)
            close_connection(conn)
        else:  # auth_id is valid but not for given user
            close_connection(conn)
            raise AUTHError("attribute 'username'={0} doesn't match with the corresponsive attribute fetched from the 'users' where 'username'={1} table by 'auth_id'={2}".format(
                    res_obj.get(auth_id).username, username, auth_id), AUTHError.INTEGRITY_VIOLATION)
    return auth_id

def unset_client(auth_id):
    if not isinstance(auth_id, int):
        raise ParameterError("bad parameter 'authentication ID': {0}; 'int' type required".format(auth_id), ParameterError.BAD_PARAMETER)
    if auth_id == None:
        raise ParameterError("auth_id cannot be equal to 'None'", ParameterError.NONE_VALUE)
    conn = get_connection()
    obj = authenticate(conn, current_clients_table, auth_id)[auth_id]  # if it works out to authenticate then it returns the object that we are looking for
    hist = clients_history_table(None, obj.username, obj.login_tstamp, timestamp())
    insert(conn, hist)
    delete(conn, current_clients_table, keyv=auth_id)
    close_connection(conn)


def set_hvac(host, port, sensor_id):
    if not isinstance(host, str):
        raise ParameterError("bad parameter 'host': {0}; 'str' type required".format(host), ParameterError.BAD_PARAMETER)
    if not isinstance(sensor_id, str):
        raise ParameterError("bad parameter 'sensor_id': {0}; 'int' type required".format(sensor_id), ParameterError.BAD_PARAMETER)
    if not isinstance(port, int):
        raise ParameterError("bad parameter 'port': {0}; 'int' type required".format(port), ParameterError.BAD_PARAMETER)
    conn = get_connection()
    hvac_id = "{0}:{1}".format(host, port)
    # Checking if the sensor does exist. If NOT then we cannot use this hvac
    try:
        authenticate(conn, current_sensors_table, sensor_id)
    except AUTHError as err:
        print err
        close_connection(conn)
        if err.getError() == AUTHError.OBJECT_NOT_FOUND:
            raise AUTHError("specified 'sensor_id' = '{0}' not found. Cannot associate hvac with a non-existing sensor".format(sensor_id), AUTHError.OBJECT_NOT_FOUND)
    try:
        authenticate(conn, hvacs_table, hvac_id)  # If this function doesn't fail, i.e., throws an exception then the username is authenticated
    except AUTHError as err:
        if err.getError() == AUTHError.OBJECT_NOT_FOUND:
            close_connection(conn)
            raise AUTHError("couldn't verify the origin for the 'hvac_id'={0}".format(hvac_id), AUTHError.ORIGIN_ERROR)
    try:
        res = authenticate(conn, current_hvacs_table, hvac_id)
        print "The 'hvac_id'={0} is already set".format(hvac_id)
    except AUTHError as err:
        if err.getError() == AUTHError.OBJECT_NOT_FOUND:
            obj = current_hvacs_table(host, port, timestamp(), timestamp(), sensor_id, 0, 0, 0, 0)
            insert(conn, obj)
        else:
            raise err
    finally:
        close_connection(conn)


def unset_hvac(host, port):
    if not isinstance(host, str):
        raise ParameterError("bad parameter 'host': {0}; 'str' type required".format(host), ParameterError.BAD_PARAMETER)
    if not isinstance(port, int):
        raise ParameterError("bad parameter 'port': {0}; 'int' type required".format(port), ParameterError.BAD_PARAMETER)
    hvac_id = "{0}:{1}".format(host, port)
    conn = get_connection()
    # Find all jobs that are assosiated with the given hvac_id
    res = select(conn, hvac_jobs_table, sql_condition="hvac_id='{0}'".format(hvac_id))
    if len(res) > 0:
        jobs = [] # List of jobs
        for k,v in res.iteritems():
            if v.hvac_id == hvac_id:
                jobs.append(v.job_id)
        raise AUTHError("supplied 'hvac_id' = {0} is currently associated with jobs: {1}; cancel the jobs first.".format(hvac_id, jobs))
        
    obj = authenticate(conn, current_hvacs_table, hvac_id)[hvac_id]  # if it works out to authenticate then it returns the object that we are looking for
    delete(conn, current_hvacs_table, keyv=hvac_id)
    close_connection(conn)


def set_sensor(host, port, path, status, priority):
    if not isinstance(host, str):
        raise ParameterError("bad parameter 'sensor_id': {0}; 'str' type required".format(sensor_id),
                             ParameterError.BAD_PARAMETER)
    if not isinstance(port, int):
        raise ParameterError("bad parameter 'port': {0}; 'int' type required".format(port),
                             ParameterError.BAD_PARAMETER)
    if not isinstance(path, str):
        raise ParameterError("bad parameter 'path': {0}; 'str' type required".format(path),
                             ParameterError.BAD_PARAMETER)
    if not isinstance(status, int):
        raise ParameterError("bad parameter 'status': {0}; 'int' type required".format(status),
                             ParameterError.BAD_PARAMETER)
    if not isinstance(priority, int):
        raise ParameterError("bad parameter 'priority': {0}; 'int' type required".format(priority),
                             ParameterError.BAD_PARAMETER)
    sensor_id = "{0}:{1}:{2}".format(host, port, path)
    conn = get_connection()
    try:
        authenticate(conn, sensors_table,
                     sensor_id)  # If this function doesn't fail, i.e., throws an exception then the sensor_id is authenticated
    except AUTHError as err:
        if err.getError() == AUTHError.OBJECT_NOT_FOUND:
            close_connection(conn)
            raise AUTHError("couldn't verify the origin for the 'sensor_id'={0}".format(sensor_id),
                            AUTHError.ORIGIN_ERROR)
    try:
        res = authenticate(conn, current_sensors_table, sensor_id)
        print "The 'sensor_id'={0} is already set".format(sensor_id)
    except AUTHError as err:
        if err.getError() == AUTHError.OBJECT_NOT_FOUND:
            obj = current_sensors_table(sensor_id, status, priority, timestamp(), timestamp(), None)
            insert(conn, obj)
        else:
            raise err
    finally:
        close_connection(conn)


def unset_sensor(host, port, path):
    if not isinstance(host, str):
        raise ParameterError("bad parameter 'host': {0}; 'str' type required".format(host), ParameterError.BAD_PARAMETER)
    if not isinstance(path, str):
        raise ParameterError("bad parameter 'path': {0}; 'str' type required".format(path), ParameterError.BAD_PARAMETER)
    if not isinstance(port, int):
        raise ParameterError("bad parameter 'port': {0}; 'int' type required".format(port), ParameterError.BAD_PARAMETER)
    sensor_id = "{0}:{1}:{2}".format(host, port, path)
    conn = get_connection()
    try:
        data = select(conn, current_hvacs_table, field="sensor_id", sql_condition="sensor_id='{0}'".format(sensor_id))
    except AUTHError as err:
        if err.getError() == AUTHError.OBJECT_NOT_FOUND:  # The object not associated with an HVAC. Can be safely deleted
            pass
        else:
            raise err
    if len(data) == 0:
        # Trying to delete the sensor. Throw an error if the sensor couldn't be authenticated
        obj = authenticate(conn, current_sensors_table, sensor_id)[sensor_id]  # if it works out to authenticate then it returns the object that we are looking for
        delete(conn, current_sensors_table, keyv=sensor_id)
    else:
        hvacs = []
        for i in data:
            hvacs.append(i)
        raise CLIENTError("Sensor {0} is associated with HVACs: {1}. Unset all HVACs first.".format(sensor_id, hvacs), CLIENTError.SENSOR_ERROR)
    close_connection(conn)
        


def register_hvac(host, port, username, password, path, protocol, cool_wattage, heat_wattage, cool_kwph=0,
                  heat_kwph=0, description=None):
    if not isinstance(host, str):
        raise ParameterError("bad parameter 'host': {0}; 'str' type required".format(host), ParameterError.BAD_PARAMETER)
    if not isinstance(port, int):
        raise ParameterError("bad parameter 'port': {0}; 'int' type required".format(port), ParameterError.BAD_PARAMETER)
    if not isinstance(username, str):
        raise ParameterError("bad parameter 'username': {0}; 'str' type required".format(username),
                             ParameterError.BAD_PARAMETER)
    if not isinstance(path, str):
        raise ParameterError("bad parameter 'path': {0}; 'str' type required".format(path), ParameterError.BAD_PARAMETER)
    if not protocol in config.PROTOCOLS:
        raise ParameterError(
            "bad parameter 'protocol': {0}; can be only one of the following: {1}".format(protocol, config.PROTOCOLS),
            ParameterError.BAD_PARAMETER)
    if not isinstance(cool_wattage, int):
        raise ParameterError("bad parameter 'cool_wattage': {0}; 'int' type required".format(cool_wattage),
                             ParameterError.BAD_PARAMETER)
    if not isinstance(heat_wattage, int):
        raise ParameterError("bad parameter 'heat_wattage': {0}; 'int' type required".format(heat_wattage),
                             ParameterError.BAD_PARAMETER)
    if not isinstance(cool_kwph, int):
        raise ParameterError("bad parameter 'cool_kwph': {0}; 'int' type required".format(cool_kwph),
                             ParameterError.BAD_PARAMETER)
    if not isinstance(heat_kwph, int):
        raise ParameterError("bad parameter 'heat_kwph': {0}; 'int' type required".format(heat_kwph),
                             ParameterError.BAD_PARAMETER)
    conn = get_connection()
    
    hvac_id = "{0}:{1}".format(host, port)
    try:
        authenticate(conn, hvacs_table, hvac_id)  # If this function doesn't fail, i.e., throws an exception then the hvac is authenticated
        print "The 'hvac_id'={0} is already registered, updating...".format(hvac_id)
        obj = hvacs_table(host, port, username, password, path, protocol, cool_wattage, heat_wattage, cool_kwph, heat_kwph, None, None, description)
        obj.hvac_id = hvac_id
        update(conn, obj)
        print "Hvac info updated"
    except AUTHError as err:
        if err.getError() == AUTHError.OBJECT_NOT_FOUND:
            obj = hvacs_table(host, port, username, password, path, protocol, cool_wattage, heat_wattage, cool_kwph, heat_kwph, None, None, description)
            insert(conn, obj)
        else:
            raise err
    finally:
        close_connection(conn)


def register_sensor(stype, host, port, username, password, path, protocol):
    if not stype in S.SENSORS:
        raise S.SensorError("sensor {0} is not in the SENSORS list: {1}".format(stype, S.SENSORS))
    if not protocol in config.PROTOCOLS:
        raise ParameterError(
            "bad parameter 'protocol': {0}; can be only one of the following: {1}".format(protocol, config.PROTOCOLS),
            ParameterError.BAD_PARAMETER)
    if not isinstance(username, str):
        raise ParameterError("bad parameter 'username': {0}; 'str' type required".format(username),
                             ParameterError.BAD_PARAMETER)
    if not isinstance(path, str):
        raise ParameterError("bad parameter 'path': {0}; 'str' type required".format(path), ParameterError.BAD_PARAMETER)
    if not isinstance(host, str):
        raise ParameterError("bad parameter 'host': {0}; 'str' type required".format(host), ParameterError.BAD_PARAMETER)
    if not isinstance(port, int):
        raise ParameterError("bad parameter 'port': {0}; 'int' type required".format(port), ParameterError.BAD_PARAMETER)
    conn = get_connection()
    sensor_id = '{0}:{1}:{2}'.format(host, port, path)
    try:
        authenticate(conn, sensors_table,
                     sensor_id)  # If this function doesn't fail, i.e., throws an exception then the username is authenticated
        print "The 'sensor_id'={0} is already registered, updating...".format(sensor_id)
        obj = sensors_table(S.pic.dumps(stype), host, port, username, password, path, protocol)
        obj.sensor_id = sensor_id
        update(conn, obj)
        print 'Sensor info updated'
    except AUTHError as err:
        if err.getError() == AUTHError.OBJECT_NOT_FOUND:
            obj = sensors_table(S.pic.dumps(stype), host, port, username, password, path, protocol)
            insert(conn, obj)
        else:
            raise err
    finally:
        close_connection(conn)


def unregister_sensor(host, port, path):
    if not isinstance(host, str):
        raise ParameterError("bad parameter 'host': {0}; 'str' type required".format(host), ParameterError.BAD_PARAMETER)
    if not isinstance(path, str):
        raise ParameterError("bad parameter 'path': {0}; 'str' type required".format(path), ParameterError.BAD_PARAMETER)
    if not isinstance(port, int):
        raise ParameterError("bad parameter 'port': {0}; 'int' type required".format(port), ParameterError.BAD_PARAMETER)
    sensor_id = "{0}:{1}:{2}".format(host, port, path)
    conn = get_connection()
    try:
        authenticate(conn, current_sensors_table, sensor_id)
        # If the sensor_id is in current_sensors_table then we cannot unregister the sensor because it is currently set
        raise AUTHError(
            "cannot unregister 'sensor_id'={0} because it is currently set. You have to call unset_sensor first".format(
                sensor_id), AUTHError.INTEGRITY_VIOLATION)
    except AUTHError as err:
        if err.getError() == AUTHError.OBJECT_NOT_FOUND:  # If the sensor_id was not found then we can unregister the sensor
            obj = authenticate(conn, sensors_table, sensor_id)[sensor_id]
            hist = sensors_history_table(None, pickle(obj), timestamp())
            insert(conn, hist)
            delete(conn, sensors_table, keyv=sensor_id)
        else:
            raise err
    finally:
        close_connection(conn)


def unregister_hvac(host, port):
    if not isinstance(host, str):
        raise ParameterError("bad parameter 'host': {0}; 'str' type required".format(host), ParameterError.BAD_PARAMETER)
    if not isinstance(port, int):
        raise ParameterError("bad parameter 'port': {0}; 'int' type required".format(port), ParameterError.BAD_PARAMETER)
    hvac_id = "{0}:{1}".format(host, port)
    conn = get_connection()
    try:
        authenticate(conn, current_hvacs_table, hvac_id)
        # If the sensor_id is in current_sensors_table then we cannot unregister the sensor because it is currently set
        raise AUTHError(
            "cannot unregister 'hvac_id'={0} because it is currently set. You have to call unset_hvac first".format(
                hvac_id), AUTHError.INTEGRITY_VIOLATION)
    except AUTHError as err:
        if err.getError() == AUTHError.OBJECT_NOT_FOUND:  # If the sensor_id was not found then we can unregister the sensor
            obj = authenticate(conn, hvacs_table, hvac_id)[hvac_id]
            hist = hvacs_history_table(None, pickle(obj), timestamp())
            insert(conn, hist)
            delete(conn, hvacs_table, keyv=hvac_id)
        else:
            raise err
    finally:
        close_connection(conn)


def register_client(username, password):
    if not isinstance(username, str):
        raise ParameterError("bad parameter 'username': {0}; 'str' type required".format(username),
                             ParameterError.BAD_PARAMETER)
    if not isinstance(password, str):
        raise ParameterError("bad parameter 'password': {0}; 'str' type required".format(password),
                             ParameterError.BAD_PARAMETER)   
    conn = get_connection()   
    
    obj=users_table(username,sha512(password),timestamp())
    try:
        insert(conn, obj)
    except DBError as err:
        if err.getError() == DBError.DUP_KEY_ERROR:
            raise AUTHError("username '{0}' is alreagy taken".format(username), AUTHError.INTEGRITY_VIOLATION)
    close_connection(conn)

def unregister_client(username):
#     if is in table current_client, he is logged in so you cannot unregister him; first do unset
    if not isinstance(username, str):
        raise ParameterError("bad parameter 'username': {0}; 'str' type required".format(username),
                             ParameterError.BAD_PARAMETER)
    conn = get_connection()  
    data=select(conn, current_clients_table, 'auth_id', sql_condition="username='{0}'".format(username))
    if len(data)>0:
        raise AUTHError("username '{0}' is currently set; you have to call unset_client".format(username),AUTHError.INTEGRITY_VIOLATION)
    authenticate(conn, users_table, username)
    delete(conn,users_table,keyv=username)

def set_job(job_type, auth_id, start_time, timestamp, period, hvac_id, hvac_fan, hvac_mode, hvac_temp, delta):
    if job_type not in config.JOB_TYPES:
        raise ParameterError(
            "bad parameter 'job type': {0}; can be only one of the following: {1}".format(job_type, config.JOB_TYPES), ParameterError.BAD_PARAMETER)
    if not isinstance(auth_id, int):
        raise ParameterError("bad parameter 'auth_id': {0}; 'int' type required".format(auth_id), ParameterError.BAD_PARAMETER)
    if not isinstance(start_time, str):
        raise ParameterError("bad parameter 'start_time': {0}; 'str' type required".format(start_time),
                         ParameterError.BAD_PARAMETER)
    if not isinstance(timestamp, str):
        raise ParameterError("bad parameter 'timestamp': {0}; 'str' type required".format(timestamp),
                             ParameterError.BAD_PARAMETER)
    if not isinstance(hvac_id, str):
        raise ParameterError("bad parameter 'hvac_id': {0}; 'str' type required".format(hvac_id),
                             ParameterError.BAD_PARAMETER)
    if not isinstance(period, int):
        raise ParameterError("bad parameter 'period': {0}; 'str' type required".format(period),
                             ParameterError.BAD_PARAMETER)
    if hvac_fan not in ics_proto.FAN_MODES:
        raise ParameterError("bad parameter 'hvac_fan': {0}; can be only one of the following: {1}".format(ics_proto.FAN_MODES),
                             ParameterError.BAD_PARAMETER)
    if hvac_mode not in ics_proto.HVAC_MODES:
        raise ParameterError("bad parameter 'hvac_mode': {0}; can be only one of the following: {1}".format(ics_proto.HVAC_MODES),
                             ParameterError.BAD_PARAMETER)
    if (hvac_temp > config.TEMP_MAX) or (hvac_temp < config.TEMP_MIN):
        raise ParameterError(
            "bad parameter 'hvac_temp': {0}; acceptable range: {1}-{2}".format(hvac_temp, config.TEMP_MIN, config.TEMP_MAX),
            ParameterError.BAD_PARAMETER)
    if not isinstance(hvac_temp, int):
        raise ParameterError("bad parameter 'hvac_temp': {0}; 'int' type required".format(hvac_temp),
                             ParameterError.BAD_PARAMETER)
    if not isinstance(delta, int) and not isinstance(delta, float):
        raise ParameterError("bad parameter 'delta': {0}; 'float' or 'int' type required".format(hvac_temp),
                             ParameterError.BAD_PARAMETER)
    if (delta > config.DELTA_MAX) or (delta < config.DELTA_MIN):
        raise ParameterError("bad parameter 'delta': {0}; acceptable range: {1}-{2}".format(delta,config.DELTA_MIN, config.DELTA_MAX),
                             ParameterError.BAD_PARAMETER)
    conn = get_connection()
    try:
        user = authenticate(conn, current_clients_table, auth_id)
    except AUTHError as err:
        if err.getError()== AUTHError.OBJECT_NOT_FOUND:
            close_connection(conn)
            raise AUTHError("specified 'auth_id' = '{0}' not found. ".format(auth_id), AUTHError.ORIGIN_ERROR)

    try:
        authenticate(conn, current_hvacs_table, hvac_id)
    except AUTHError as err:
        if err.getError() == AUTHError.OBJECT_NOT_FOUND:
            close_connection(conn)
            raise AUTHError("specified 'hvac_id' = '{0}' not found. ".format(hvac_id), AUTHError.ORIGIN_ERROR)
    # Find all CURRENT jobs
    if job_type == config.CURRENT:
        unset_job(job_type=config.CURRENT, hvac_id=hvac_id)
    obj = hvac_jobs_table(None, job_type, auth_id, user[auth_id].username, start_time, timestamp, period, hvac_id, hvac_fan, hvac_mode, hvac_temp, delta)
    insert(conn, obj)
    close_connection(conn)

def unset_job(job_id=None, job_type=None, hvac_id=None):
    conn = get_connection()
    if not job_id is None:
        res = select(conn, hvac_jobs_table, sql_condition="job_id='{0}'".format(job_id))
    else:
        if not isinstance(hvac_id, str):
            raise ParameterError("bad parameter 'hvac_id': {0}; 'str' type required".format(hvac_id), ParameterError.BAD_PARAMETER)
        res = select(conn, hvac_jobs_table, sql_condition="job_type='{0}' AND hvac_id='{1}'".format(job_type, hvac_id))
        print res
        if len(res) > 1 and job_type == config.CURRENT:
            close_connection(conn)
            raise AUTHError("only one job per HVAC unit can have type 'CURRENT', found {0}.".format(len(res)), AUTHError.INTEGRITY_VIOLATION)
    if len(res) > 0:
        for k,v in res.iteritems():
            # Place job to the job history and then remove
            hist = hvac_job_history_table(v.job_id, v.job_type, v.publisher, v.start_time, timestamp(), v.period, v.hvac_fan, v.hvac_mode, v.hvac_temp, v.hvac_delta)
            insert(conn, hist)
            delete(conn, hvac_jobs_table, keyv=k)
    else:
        print "No jobs found"
    return res


def _cleanup(table, fromDate, toDate, field='timestamp'):

    try:
        datetime.strptime(fromDate, config.DATE_FORMAT)
    except ValueError as err:
        raise err

    conn = get_connection()
    cmd = "{0} BETWEEN '{1}' AND '{2}'".format(field, fromDate, toDate)
    delete(conn, table, sql_condition = cmd)
    close_connection(conn)

# kept this function here coz it needs to call get_connection() 
# user can change password only when he/she is logged in
def changePwd(auth_id, pass_hash, new_pass_hash):
    if len(new_pass_hash) != 128:
        raise ParameterError("bad parameter 'new_pass_hash': {0}; SHA512 must have 128 characters, but has {1}".format(username, len(pass_hash)), ParameterError.BAD_PARAMETER)
    if not isinstance(new_pass_hash, str):
        raise ParameterError("bad parameter 'password': {0}; 'str' type required".format(new_pass_hash), ParameterError.BAD_PARAMETER)
    if not isinstance(auth_id, int):
        raise ParameterError("bad parameter 'authentication ID': {0}; 'int' type required".format(auth_id), ParameterError.BAD_PARAMETER)          
    conn = get_connection()     
    try:
        data=authenticate(conn, current_clients_table, auth_id)
        # If this function doesn't fail, i.e., throws an exception then the username is authenticated
        #check if username exists
        username=data.get(auth_id).username
        try:
            dataObj=authenticate(conn, users_table, username)
        except AUTHError as err:
            raise AUTHError("Unregistered used is logged in", AUTHError.INTEGRITY_VIOLATION)
        oldLoginTime=dataObj.get(username).timestamp
        updatedObj=users_table(username,new_pass_hash,oldLoginTime)
        update(conn,updatedObj)
        # dont do unset_client because it will unset user with only one auth_id
        # instead select all auth_id instances of that user with username and unset the
        delete(conn, current_clients_table,  sql_condition="username='{0}'".format(username))             
    except AUTHError as err:
        if err.getError() == AUTHError.OBJECT_NOT_FOUND:
            close_connection(conn)
            raise AUTHError("current session for username '{0}' already expired".format(username),
                            AUTHError.OBJECT_NOT_FOUND)  
        else:
            raise err

# System functions
def sync_sensor(s):
    # Trying cache
    try:
        S_LOCK.acquire()
        c_sensor, sinfo, res = S_CACHE[s]
        log.debug("Sensor cache hit")
        return c_sensor, sinfo, res
    except KeyError as err:
        log.debug("Sensor cache miss")
    finally:
        S_LOCK.release()
    # If no cache entry then query the sensor
    cnx = get_connection()
    try:
        c_sensor = authenticate(cnx, current_sensors_table, s)[s]
        verify(c_sensor)
    except AUTHError as err:
        print err
        cnx.close()
        if err.getError() == AUTHError.OBJECT_NOT_FOUND:
            raise CLIENTError("job desynchronyzed; sensor {0} that is unset or missing".format(s), CLIENTError.DESYNCHRONIZATION)
        else:
            raise err
    try:
        sinfo = authenticate(cnx, sensors_table, c_sensor.sensor_id)[c_sensor.sensor_id]
        verify(sinfo)
    except AUTHError as err:
        print err
        cnx.close()
        if err.getError() == AUTHError.OBJECT_NOT_FOUND:
            raise CLIENTError('authentication error; sensor {0} does not exist and is now unset', CLIENTError.INTEGRITY_VIOLATION)
        else:
            raise err
    try:
        if sinfo.protocol == config.SSHRPC:
            #~ print "Querying sensor:", toString(sinfo)
            res = S.query(sinfo.path, sinfo.host, sinfo.port, sinfo.username, sinfo.password, True)
            c_sensor.raw_data = res # saving raw data into current sensors
            c_sensor.timestamp = timestamp()
            verify(c_sensor)
            update(cnx, c_sensor)
            S_LOCK.acquire()
            S_CACHE[s] = (c_sensor, sinfo, res)
            S_LOCK.release()
            return c_sensor, sinfo, res
        elif sinfo.protocol == config.MODBUS:
            print "MODBUS communication is not implemented for sensors"
        else:
            pass
    except DBError as err:
        print err
        raise err
    except ICSTypeError as err:
        print err
        raise err
    except sshrpc.SSHRPCError as err:
        print err
        raise err
    finally:
        cnx.close()

def sync_hvac(h):
    try:
        H_LOCK.acquire()
        c_hvac, hinfo, res = H_CACHE[h]
        log.debug("HVAC cache hit")
        return c_hvac, hinfo, res
    except KeyError as err:
        log.debug("HVAC cache miss")
    finally:
        H_LOCK.release()
    cnx = get_connection()
    try:
        c_hvac = authenticate(cnx, current_hvacs_table, h)[h]
        verify(c_hvac)
    except AUTHError as err:
        print err
        cnx.close()
        if err.getError() == AUTHError.OBJECT_NOT_FOUND:
            raise CLIENTError("job desynchronyzed; hvac {0} is unset or missing".format(h), CLIENTError.DESYNCHRONIZATION)
        else:
            raise err
    try:
        hinfo = authenticate(cnx, hvacs_table, c_hvac.hvac_id)[c_hvac.hvac_id] # for each current hvac read info about it
        verify(hinfo)
    except AUTHError as err:
        print err
        cnx.close()
        if err.getError() == AUTHError.OBJECT_NOT_FOUND:
            raise CLIENTError('authentication error; hvac {0} does not exist and is now unset', CLIENTError.INTEGRITY_VIOLATION)
        else:
            raise err
    # Composing hvac frame
    p = ics_proto.HVACParams(0,0,0)
    c = ics_proto.Control(ics_proto.FAIL, ics_proto.FETCH_PARAMS)
    a = ics_proto.HVACFrame(c,p)
    ics_proto.verify(a)
    try:
        if hinfo.protocol == config.SSHRPC: # using hvac info sending query
            #~ print "Querying hvac:", toString(hinfo)
            res = H.exchange(a, hinfo.host, hinfo.port, hinfo.username, hinfo.password, True)
            # Identifying how long A/C or heater have worked:
            dT = (datetime.strptime(timestamp(), config.DATE_FORMAT) - datetime.strptime(c_hvac.timestamp, config.DATE_FORMAT)).total_seconds()
            print '---------------------------------------', dT
            hinfo.cool_kwph += float(int(res.params.cool) * (dT/3600.0) * (hinfo.cool_wattage/1000.0))
            hinfo.heat_kwph += float(int(res.params.heat) * (dT/3600.0) * (hinfo.heat_wattage/1000.0))
            cu = hinfo.cool_usage
            hu = hinfo.heat_usage
            if cu == None:
                cu = {}
            else:
                cu = unpic(cu)
            if hu == None:
                hu = {}
            else:
                hu = unpic(hu)
            dict_key = timestamp(fmt=config.USAGE_TIME_FMT)
            if not dict_key in cu:
                cu[dict_key] = 0
            if not dict_key in hu:
                hu[dict_key] = 0
            cu[dict_key] += float(int(res.params.cool) * (dT/3600.0) * (hinfo.cool_wattage/1000.0))
            hu[dict_key] += float(int(res.params.heat) * (dT/3600.0) * (hinfo.cool_wattage/1000.0))
            hinfo.cool_usage = pickle(cu)
            hinfo.heat_usage = pickle(hu)
            # Update static HVAC information
            update(cnx, hinfo)
            c_hvac.timestamp = timestamp() # update data for hvac
            c_hvac.fan = res.params.fan
            c_hvac.heat = res.params.heat
            c_hvac.cool = res.params.cool
            verify(c_hvac)
            update(cnx, c_hvac)
            H_LOCK.acquire()
            H_CACHE[h] = (c_hvac, hinfo, res)
            H_LOCK.release()
            return c_hvac, hinfo, res
        elif hinfo.protocol == config.MODBUS:
            #~ print "Querying hvac:", toString(hinfo)
            res = H.modbus_exchange(a, hinfo.host, hinfo.port, hinfo.username, hinfo.password, True)
            # Identifying how long A/C or heated worked:
            dT = (datetime.strptime(timestamp(), config.DATE_FORMAT) - datetime.strptime(c_hvac.timestamp, config.DATE_FORMAT)).total_seconds()
            hinfo.cool_kwph += (res.params.cool * (dT/3600.0) * (hinfo.cool_wattage/1000.0))
            hinfo.heat_kwph += (res.params.heat * (dT/3600.0) * (hinfo.heat_wattage/1000.0))
            # Update static HVAC information
            update(cnx, hinfo)
            c_hvac.timestamp = timestamp() # update data for hvac
            c_hvac.fan = res.params.fan
            c_hvac.heat = res.params.heat
            c_hvac.cool = res.params.cool
            verify(c_hvac)
            update(cnx, c_hvac)
            H_LOCK.acquire()
            H_CACHE[h] = (c_hvac, hinfo, res)
            H_LOCK.release()
            return c_hvac, hinfo, res
    except DBError as err:
        print err
        raise err
    except ICSTypeError as err:
        print err
        raise err
    except sshrpc.SSHRPCError as err:
        print err
        raise err
    finally:
        cnx.close()


def set_hvac_state(c_hvac, hinfo, heat, cool, fan):
    cnx = get_connection()
    # Composing hvac frame
    p = ics_proto.HVACParams(fan,heat,cool)
    c = ics_proto.Control(ics_proto.FAIL, ics_proto.SET_PARAMS)
    a = ics_proto.HVACFrame(c,p)
    ics_proto.verify(a)
    try:
        if hinfo.protocol == config.SSHRPC: # using hvac info sending query
            #~ print "Setting hvac:", toString(hinfo)
            res = H.exchange(a, hinfo.host, hinfo.port, hinfo.username, hinfo.password, True)
            #c_hvac.timestamp = timestamp() # update data for hvac
            c_hvac.fan = res.params.fan
            c_hvac.heat = res.params.heat
            c_hvac.cool = res.params.cool
            verify(c_hvac)
            update(cnx, c_hvac)
            return c_hvac, hinfo, res
        elif hinfo.protocol == config.MODBUS:
            #~ print "Setting hvac:", toString(hinfo)
            res = H.modbus_exchange(a, hinfo.host, hinfo.port, hinfo.username, hinfo.password, True)
            #c_hvac.timestamp = timestamp() # update data for hvac
            c_hvac.fan = res.params.fan
            c_hvac.heat = res.params.heat
            c_hvac.cool = res.params.cool
            verify(c_hvac)
            update(cnx, c_hvac)
            return c_hvac, hinfo, res
        else:
            pass
    except DBError as err:
        print err
        raise err
    except ICSTypeError as err:
        print err
        raise err
    except sshrpc.SSHRPCError as err:
        print err
        raise err
    finally:
        cnx.close()


def sync_job(j):
    assert(j.job_type == config.CURRENT)
    try:
        c_hvac, h_info, h_data = sync_hvac(j.hvac_id)
        if h_data == None:
            raise CLIENTError("hvac didn't respond on request", CLIENTError.DESYNCHRONIZATION)
    except CLIENTError as err:
        print err
        unset_job(job_id=j.job_id)
        if err.getError() == CLIENTError.INTEGRITY_VIOLATION or err.getError() == CLIENTError.DESYNCHRONIZATION: # If the hvac static data changed
            host, port = tuple(j.hvac_id.split(':')) 
            unset_hvac(host, int(port)) # then unset the hvac
        return None
    except sshrpc.SSHRPCError as err:
        print err
        unset_job(job_id=j.job_id)
        if err.getError() == sshrpc.SSHRPCError.REMOTE_EXCEPTION: # If the hvac static data changed
            host, port = tuple(j.hvac_id.split(':')) 
            unset_hvac(host, int(port)) # then unset the hvac
        return None
    try:
        c_sensor, s_info, s_data = sync_sensor(c_hvac.sensor_id)
        if s_data == None:
            raise CLIENTError("sensor didn't respond on request", CLIENTError.DESYNCHRONIZATION)
    except CLIENTError as err:
        print err
        unset_job(job_id=j.job_id)
        if err.getError() == CLIENTError.INTEGRITY_VIOLATION or err.getError() == CLIENTError.DESYNCHRONIZATION: # If the sensor static data changed
            host, port = tuple(j.hvac_id.split(':'))
            unset_hvac(host, int(port)) # then unset an hvac assosiated with the sensor first
            host, port, path = tuple(c_hvac.sensor_id.split(':'))
            unset_sensor(host, int(port), path) # and then unset the sensor itself
        return None
    except sshrpc.SSHRPCError as err:
        print err
        unset_job(job_id=j.job_id)
        if err.getError() == sshrpc.SSHRPCError.REMOTE_EXCEPTION: # If the hvac static data changed
            unset_hvac(host, int(port)) # then unset an hvac assosiated with the sensor first
            host, port, path = tuple(c_hvac.sensor_id.split(':'))
            unset_sensor(host, int(port), path) # and then unset the sensor itself
        return None
    t = pic.loads(s_info.stype).interprit(s_data, 1000.0) # Not floored, F
    print "\tHVAC: {0}\n\tDesired T: {1}\n\tSensor T: {2} F\n\tDelta: {3}\n\tH = {4}\n\tC = {5}\n\tF = {6}\n\tMODE = {7}\n\tFAN = {8}".format(c_hvac.hvac_id, j.hvac_temp, t, j.hvac_delta, h_data.params.heat, h_data.params.cool, h_data.params.fan, j.hvac_mode, j.hvac_fan)
    params = (h_data.params.heat, h_data.params.cool, h_data.params.fan)
    fan_flag = 0
    if j.hvac_mode == ics_proto.OFF:
        params = (0,0,0)
    elif j.hvac_mode == ics_proto.HEAT:
        if h_data.params.heat == 1: # If heater is on but the T is >= the desired temperature then set the heater off
            if t >= j.hvac_temp:
                params = (0,0,0)
        elif h_data.params.cool == 1:
            params = (0,0,0)
        else: # Heater is off
            if abs(t - j.hvac_temp) >= j.hvac_delta and t < j.hvac_temp:
                params = (1,0,1)
                fan_flag = 1
    elif j.hvac_mode == ics_proto.COOL:
        if h_data.params.cool == 1:
            if t <= j.hvac_temp:
                params = (0,0,0)
        elif h_data.params.heat == 1:
            params = (0,0,0)
        else: # Heater is off
            if abs(t - j.hvac_temp) >= j.hvac_delta and t > j.hvac_temp:
                params = (0,1,1)
                fan_flag = 1
    elif j.hvac_mode == ics_proto.CLIM:
        if h_data.params.heat == 1 and h_data.params.cool == 0:
            if t >= j.hvac_temp:
                params = (0,0,0)
        elif h_data.params.cool == 1 and h_data.params.heat == 0:
            if t <= j.hvac_temp:
                params = (0,0,0)
        elif h_data.params.cool == 0 and h_data.params.heat == 0:
            if abs(t - j.hvac_temp) >= j.hvac_delta:
                if t > j.hvac_temp:
                    params = (0,1,1)
                    fan_flag = 1
                elif t < j.hvac_temp:
                    params = (1,0,1)
                    fan_flag = 1
    else:
        raise CLIENTError("job_table has unacceptable value for hvac_mode: {0}".format(j.hvac_mode) , CLIENTError.INTEGRITY_VIOLATION)
    if j.hvac_fan == ics_proto.ON:
        params = (params[0], params[1], 1)
    elif j.hvac_fan == ics_proto.AUTO:
        params = (params[0], params[1], 1*fan_flag)
    else:
        raise CLIENTError("job_table has unacceptable value for hvac_fan: {0}".format(j.hvac_fan) , CLIENTError.INTEGRITY_VIOLATION)
    
    if params[0]:
        print "Turning on heater..."
    if params[1]:
        print "Turning on cooler..."
    if params[2]:
        print "Turning on fan..."
    try:
        c_h, h_i, h_d = set_hvac_state(c_hvac, h_info, *params)
        if h_d == 0:
            raise CLIENTError("hvac filed to set parameters, returned NULL", CLIENTError.DESYNCHRONIZATION)
    except CLIENTError as err:
        print err
        unset_job(job_id=j.job_id)
        if err.getError() == err.getError() == CLIENTError.DESYNCHRONIZATION:
            host, port = tuple(j.hvac_id.split(':'))
            unset_hvac(host, int(port)) # then unset an hvac assosiated with the sensor first
            host, port, path = tuple(c_hvac.sensor_id.split(':'))
            unset_sensor(host, int(port), path) # and then unset the sensor itself
        return None
    except sshrpc.SSHRPCError as err:
        print err
        unset_job(job_id=j.job_id)
        if err.getError() == err.getError() == CLIENTError.DESYNCHRONIZATION:
            host, port = tuple(j.hvac_id.split(':'))
            unset_hvac(host, int(port)) # then unset an hvac assosiated with the sensor first
            host, port, path = tuple(c_hvac.sensor_id.split(':'))
            unset_sensor(host, int(port), path) # and then unset the sensor itself
        return None
    ics_proto.verify(h_d)
    if h_d.cntl.status == ics_proto.FAIL:
        raise CLIENTError("failed to set parameters for HVAC; status: {0}".format(h_d.cntl.status) , CLIENTError.HVAC_ERROR)
    else:
        print "Status: {0}".format(h_d.cntl.status)
    verify(j)
    return j

def read_history(ics_type, fromDate, toDate,field='timestamp'):
    try:
        datetime.strptime(fromDate, config.DATE_FORMAT)
    except ValueError as err:
        raise errc
    conn = get_connection()
    dataDict = select(conn, ics_type, sql_condition="{0} BETWEEN '{1}' AND '{2}'".format(field,fromDate, toDate))
    close_connection(conn)
    return dataDict


def read(ics_type):
    try:
        conn = get_connection()
        return select(conn, ics_type)
    except DBError as dbError:
        print DBError
        raise CLIENTError("couldn't perform read from '{0}'".format(ics_type.table), CLIENTError.DATABASE_ERROR)

if __name__ == '__main__':
    pass

    #register_client('sergey1', '123')
    #set_client(None, 'sergey1', '3c9909afec25354d551dae21590bb26e38d53f2173b8d3dc3eee4c047e7ab1c1eb8b85103e3be7ba613b31bb5c9c36214dc9f14a42fd7a2fdb84856bca5c44c2')
    #set_client(None, 'sergey')
    #set_client(None, 'sergey')

    #unset_client(360211595)
    #unregister_client('sergey')


    
    #register_sensor(S.BS18D20, '192.168.1.198', 22, 'sensor', 'pisensor1', '/sys/bus/w1/devices/28-011600571dff/w1_slave', config.SSHRPC)
    #~ register_sensor(S.BS18D20, '192.168.7.187', 22, 'sensor', 'pisensor1', '/sys/bus/w1/devices/28-0216007634ff/w1_slave', config.SSHRPC)
    #register_hvac('192.168.1.198', 22, 'hvac', 'pihvac1', '/home/hvac', config.MODBUS, 100, 300, 0, 0, "My HVAC unit")
    #~ register_hvac('192.168.7.187', 22, 'hvac', 'pihvac1', '/home/hvac', config.SSHRPC, 100, 300, 0, 0, "My HVAC unit")
    #set_sensor('192.168.1.198:22:/sys/bus/w1/devices/28-011600571dff/w1_slave', S.ACTIVE, 1)
    #set_sensor('192.168.7.187:22:/sys/bus/w1/devices/28-0216007634ff/w1_slave', S.ACTIVE, 1)
    #set_hvac('192.168.1.198',22, '192.168.1.198:22:/sys/bus/w1/devices/28-011600571dff/w1_slave')
    #set_hvac('192.168.7.187',22, '192.168.7.187:22:/sys/bus/w1/devices/28-0216007634ff/w1_slave')
    

    #set_job(config.CURRENT, 186866213, timestamp(),timestamp(), '192.168.7.187:223', ics_proto.ON, ics_proto.HEAT, 72, 1.5)
    #unset_job(job_type=config.CURRENT, hvac_id='192.168.7.187:223')
    
    #unset_hvac('192.168.1.198', 22)
    #unset_sensor('192.168.1.198', 22, '/sys/bus/w1/devices/28-011600571dff/w1_slave')
    #~ unregister_sensor('192.168.7.187', 22, '/sys/bus/w1/devices/28-0216007634ff/w1_slave')
    #~ unregister_hvac('192.168.7.187', 22)
    
