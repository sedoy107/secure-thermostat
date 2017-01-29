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


import time
from threading import Timer
import sys_api as API
import ics_proto as P
import ics_types as T
import sensor as S
import hvac as H
import config
from common import *
import cPickle as pic
from datetime import datetime
import sshrpc
import mysql.connector
from threading import Thread
import logging, logger
from atomic import *
from scheduler import Scheduler

LOG_NAME = 'daemon.log'
logger.create_log(LOG_NAME, None)
log = logging.getLogger(LOG_NAME)

def job_daemon():
    cnx = API.get_connection()
    c_jobs = API.select(cnx, T.hvac_jobs_table)
    # For each job
    for k,v in c_jobs.iteritems():
        try:
            if v.job_type != config.CURRENT and v.job_type != config.DELAYED:
                # Throw away an entry if any value does not comply with the format
                API.unset_job(job_id=v.job_id)
                continue
            elif v.job_type == config.CURRENT:
                res = API.sync_job(v)
            elif v.job_type == config.DELAYED:
                # If we dealing with a delayed job than we must check the time on it
                t = time.time()
                v.timestamp = timestamp(t=t)
                t_diff = (datetime.strptime(v.start_time, config.DATE_FORMAT) - datetime.strptime(v.timestamp, config.DATE_FORMAT)).total_seconds()
                if t_diff <= 0:
                    API.unset_job(job_type=config.CURRENT, hvac_id=v.hvac_id) # unset a current job
                    if v.period > 0:
                        API.set_job(config.DELAYED, v.auth_id, timestamp(t=(t_diff + t + v.period)), timestamp(), v.period, v.hvac_id, v.hvac_fan, v.hvac_mode, v.hvac_temp, v.hvac_delta)
                    v.job_type = config.CURRENT # make the delayed job current
                    res = API.sync_job(v) # sync job with hvac and sensors
                else:
                    res = v
        except sshrpc.SSHRPCError as err: # No matter what RPC error we get, just unset this job
            log.error(err.msg)
            API.unset_job(job_type=config.CURRENT) # unset a current job
            continue
        if res != None:
            # Create a new object
            newobj = T.hvac_jobs_table(res.job_id, res.job_type, res.auth_id, res.publisher, res.start_time, timestamp(), res.period, res.hvac_id, res.hvac_fan, res.hvac_mode, res.hvac_temp, res.hvac_delta)
            API.update(cnx, newobj)
    cnx.close()

def client_daemon():
    cnx = API.get_connection()
    cur_users = API.select(cnx, T.current_clients_table)
    for k,v, in cur_users.iteritems():
        if (datetime.strptime(timestamp(), config.DATE_FORMAT) - datetime.strptime(v.activity_tstamp, config.DATE_FORMAT)).total_seconds() > config.SESSION_TIME:
            API.unset_client(v.auth_id) # Logout a user
    cnx.close()

def sensor_daemon():
    cnx = API.get_connection()
    cur_sensors = API.select(cnx, T.current_sensors_table)
    for k,v, in cur_sensors.iteritems():
        try:
            c_sensor, sinfo, res = API.sync_sensor(v.sensor_id)
        except API.CLIENTError as err:
            log.error(err.msg)
            if err.getError() == API.CLIENTError.DESYNCHRONIZATION:
                log.warning("Sensor {0} is not set anymore".v.sensor_id)
            elif err.getError() == API.CLIENTError.INTEGRITY_VIOLATION:
                API.unset_sensor(v.sensor_id) # Unset bad sensor
    cnx.close()

def cache_daemon():
    # Sensors
    KILL_LIST = []
    for k,v in API.S_CACHE.iteritems():
        t_diff = (datetime.strptime(timestamp(), config.DATE_FORMAT) - datetime.strptime(v[0].timestamp, config.DATE_FORMAT)).total_seconds()
        #~ log.debug('-----------S --- {0}'.format( t_diff ))
        if t_diff  > config.CACHE_LIFETIME:
            KILL_LIST.append(k)
    API.S_LOCK.acquire()
    for i in KILL_LIST:
        del API.S_CACHE[i]
    API.S_LOCK.release()
    # HVACs
    KILL_LIST = []
    for k,v in API.H_CACHE.iteritems():
        t_diff = (datetime.strptime(timestamp(), config.DATE_FORMAT) - datetime.strptime(v[0].timestamp, config.DATE_FORMAT)).total_seconds()
        #~ log.debug('-----------H --- {0}'.format( t_diff ))
        if t_diff > config.CACHE_LIFETIME:
            KILL_LIST.append(k)
    API.H_LOCK.acquire()
    for i in KILL_LIST:
        del API.H_CACHE[i]
    API.H_LOCK.release()

def flush_hvac_cache():
    API.H_LOCK.acquire()
    API.H_CACHE = {}
    API.H_LOCK.release()
def flush_sensor_cache():
    API.S_LOCK.acquire()
    API.S_CACHE = {}
    API.S_LOCK.release()

def _caller_(f, *args):
    try:
        f(*args)
    except P.HVACError as err: # This error comes in when HVACFrame is malformed so we need to stop if that is the case
        log.error(err.msg)
        raise err
    except API.AUTHError as err: # Some of the AUTHError instances can get up to this point
        log.error(err.msg)
        raise err
    except T.ICSTypeError as err:
        log.error(err.msg)
        raise err
    except API.DBError as err:
        log.error(err.msg)
    #except API.CLIENTError as err:
    #    log.error(err.msg)
    except ParameterError as err:
        log.error(err.msg)
        raise err
    except mysql.connector.errors.OperationalError as err: # Connection with databse failed # This happens if the connection with database is not established (the service itself is active though in this case)
        log.error(err.msg)
        raise err
    except mysql.connector.errors.ProgrammingError as err: # The target table does not exist # This happens in case of wrod sytax and malformed statements
        log.error(err.msg)
        raise err
    except mysql.connector.errors.InterfaceError as err: # The target table does not exist # This happen is I manually stop DB service, so there is nothing to connect to
        log.error(err.msg)
        raise err
    finally:
        print "Function name: {0}".format(f.__name__)

def show_help():
    print "Better run it from interpriter and control jobs from there"
    print "Type \"exit\" to break out of the loop and get to interpriter the daemon"
    print "Use 'S' literal to address to the Scheduler instance"
    print "Use \"list\" method to list jobs"
    print "Use \"enter\" method to add jobs"
    print "Use \"rm\" method to remove jobs"
    print "Use \"suspend\" method to suspend a job"
    print "Use \"resetWaitFor\" method to force out-of-order job execution"
    print "Use \"stop\" method to stop scheduler"
    print "Type \"run\" to start the daemon"

if __name__ == '__main__':
    s = Scheduler()
    s.enter(_caller_, config.CACHE_PERIOD, (cache_daemon,), "CACHE_DAEMON")
    s.enter(_caller_, config.JOB_QUERY_PERIOD, (job_daemon,), "JOB_DAEMON")
    s.enter(_caller_, config.SENSOR_QUERY_PERIOD, (sensor_daemon,), "SENSOR_DAEMON")
    s.enter(_caller_, config.SESSION_TIME, (client_daemon,), "CLIENT_DAEMON")
    show_help()
    #~ h = show_help
    #~ while (True):
        #~ x = raw_input(">> ")
        #~ if x == 'exit':
            #~ break
        #~ elif x == 'help':
            #~ show_help()
    #~ print "Exiting..."
    s.start()
    
        
