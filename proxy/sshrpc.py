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


import paramiko
import sys
import base64, time
import cPickle as pic
import argparse
import tempfile
import types
import socket
from multiprocessing import RLock

# When we want to transmit somthing over our SSH RPC, we have to supply
# the transmitted, deserialized, and base64-encoded object to 
# the destination module. 
# We acheive that by using optional argument --sshrpc-in

_SSHRPC_IN = '--sshrpc-in'
SSHRPC_IN = None

parser = argparse.ArgumentParser(description="SSH RPC module")
parser.add_argument(_SSHRPC_IN, dest='_sshrpc_in', default=None)
args = parser.parse_args()

_CONNECTION_REGISTRY = {}
class cleaner:
    def __del__(self):
        global _CONNECTION_REGISTRY
        c = _CONNECTION_REGISTRY
        for k,v in c.iteritems():
            v.close()

_CLEANER = cleaner()

class SSHRPCError(Exception):
    PREFIX = 'SSHRPC error'
    SSH_AUTHENTICATION_ERROR = 0xff
    SSH_ERROR = 0xfe
    BAD_PARAMETER = 0xfd
    CONNECTION_ERROR = 0xfc
    CONNECTION_TIMEOUT = 0xfb
    BAD_ADDRESS = 0xfa
    REMOTE_EXCEPTION = 0x01
    INTERNAL_ERROR = 0x02
    BROKEN_INVOKATION_SEQUENCE = 0x03
    KNOWN_ERRORS = {SSH_AUTHENTICATION_ERROR:'SSH_AUTHENTICATION_ERROR',
                    SSH_ERROR:'SSH_ERROR', BAD_PARAMETER:'BAD_PARAMETER',
                    CONNECTION_ERROR:'CONNECTION_ERROR',
                    REMOTE_EXCEPTION:'REMOTE_EXCEPTION',
                    INTERNAL_ERROR:'INTERNAL_ERROR',
                    BROKEN_INVOKATION_SEQUENCE:'BROKEN_INVOKATION_SEQUENCE',
                    BAD_ADDRESS:'BAD_ADDRESS',
                    CONNECTION_TIMEOUT:'CONNECTION_TIMEOUT' }
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
            return str(
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



class sshrpc:
    OK = 0
    FAIL = 1
    def __init__(self, host, port, username, password=None):
        if not isinstance(host, str):
            raise SSHRPCError("bad parameter 'host': {0}; 'str' type required".format(host), SSHRPCError.BAD_PARAMETER)
        if not isinstance(username, str):
            raise SSHRPCError("bad parameter 'username': {0}; 'str' type required".format(username), SSHRPCError.BAD_PARAMETER)
        if not isinstance(port, int):
            raise SSHRPCError("bad parameter 'port': {0}; 'int' type required".format(port), SSHRPCError.BAD_PARAMETER)
        global _CONNECTION_REGISTRY
        self.registry = _CONNECTION_REGISTRY
        # Initialization attributes
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        # Runtime attributes
        self.ssh = None
        self.l = RLock()
    # Close sshrpc session
    def close(self):
        self.l.acquire()
        try:
            self.ssh.close() # suppressing AttributeError in case if the ssh == None
        except AttributeError:
            pass
        connection_id = "{0}@{1}:{2}".format(self.username, self.host, self.port)
        if connection_id in self.registry:
            del self.registry[connection_id]
        self.l.release()
        print "Connection {0} closed and removed from registry...".format(connection_id)
    # Start sshrpc session
    def connect(self):
        connection_id = "{0}@{1}:{2}".format(self.username, self.host, self.port)
        self.l.acquire()
        # First, check the registry:
        if connection_id in self.registry:
            self.ssh = self.registry[connection_id]
        # If the connection already established and authenticated then do not connect but just return
        if self.ssh != None:
            if self.ssh.get_transport() != None and self.ssh.get_transport().is_authenticated():
                self.l.release()
                return 0
        
        self.ssh = paramiko.SSHClient()
        try:
            self.ssh.load_system_host_keys()

            # Set the policy to accept the SSH key for the SSH server (If not done, an exception is raised saying that the server is not found in known_hosts)
            # It will auto-accept unknown keys
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # refuse to connect to a host who does not have a key stored in your local ''known_hosts'' file
            # self.ssh.set_missing_host_key_policy(paramiko.RejectPolicy())

            # both pkey and key_filename works, password for unlocking private key (if set)
            if self.password == None:
                self.ssh.connect(self.host, port=self.port, username=self.username, look_for_keys=True, timeout=5)
            else:
                self.ssh.connect(self.host, port=self.port, username=self.username, password=self.password, timeout=5)
            
            self.registry[connection_id] = self.ssh
            print "Connected successfully, adding connection {0} to registry...".format(connection_id)

        except paramiko.AuthenticationException:
            self.close()
            raise SSHRPCError("authentication failed", SSHRPCError.SSH_AUTHENTICATION_ERROR)
        except paramiko.SSHException:
            self.close()
            raise SSHRPCError('server not found in known hosts or the remote service is not an ssh', SSHRPCError.SSH_ERROR)
        except paramiko.ssh_exception.NoValidConnectionsError:
            self.close()
            raise SSHRPCError("connection with remote ssh service could not be established", SSHRPCError.CONNECTION_ERROR)
        except socket.gaierror:
            self.close()
            raise SSHRPCError("bad URL for remote ssh service", SSHRPCError.BAD_ADDRESS)
        except socket.timeout:
            self.close()
            raise SSHRPCError("connection with remote ssh service was timed out", SSHRPCError.CONNECTION_TIMEOUT)
        finally:
            self.l.release()
        #chan = self.ssh.invoke_shell()
        return 0
    # Execute remote procedure over sshrpc
    def execute(self, cmd, func, *params):
        '''1. When invoke a command w/o sshrpc the ftable and pos_argt MUST remain None'''
        '''2. When invoke a script with sshrpc support then ftable and pos_argt can be
              used as argunemt for the target script.
              All argumants are encapsulated into one list construct and are fed as --sshrpc-in
              argument. 
              Arguments when are read, get parsed. If an arguments set supplied
              does not comply with the arguments taken by the taget script, the error stream
              will contain en error message
        '''
        self.connect()
        ftable = {}
        if func:
            ftable['f'] = func
        if params:
            ftable['p'] = params
        
        if len(ftable) > 0:
            cmd += ' ' + _SSHRPC_IN + ' ' + base64.b64encode(pic.dumps(ftable))
        
        try:
            stdin, stdout, stderr = self.ssh.exec_command(cmd)
        except AttributeError as err:
            print err
            self.close()
            raise SSHRPCError("failed to execute command over ssh. Connection lost", SSHRPCError.CONNECTION_ERROR)
        '''There is a potential threat that too large object may be passed that consumes to much memory. The application will crash'''
        out = stdout.read()
        err = stderr.read()
        
        obj = interprit(out, False)
        try:
            if obj[0] == sshrpc.FAIL:
                sys.stdout.write(obj[1])
                msg = "\n-------------------- REMOTE EXCEPTION TEXT --------------------\n\n" + err + "\n---------------------------------------------------------------"
                raise SSHRPCError(msg, SSHRPCError.REMOTE_EXCEPTION)
            elif obj[0] == sshrpc.OK:
                sys.stdout.write(obj[1])
                return obj[2]
            else:
                raise SSHRPCError("unknown status: {0}".format(obj[0]))
        except TypeError as e:
            print '-'*80
            print out
            print '-'*80
            print err
            print '-'*80

def pack(v, b64=True):
    try:
        obj = pic.dumps(v)
        if b64:
            obj = base64.b64encode(obj)
        return obj
    except pickle.PicklingError:
        sys.stderr.write("Error in cPickle: unserializabla object\n")
        return v
        
def interprit(v, b64=True):
    try:
        if b64:
            v = base64.b64decode(v)
        obj = pic.loads(v)
        return obj
    except ValueError:
        sys.stderr.write("Make sure base 64 is on\n")
    except pic.UnpicklingError as e:
        sys.stderr.write("Error in cPickle: deserialization failed\n")
        sys.stderr.write( v)
        raise e
    except EOFError:
        sys.stderr.write("Warning: no output printed\n")
    except TypeError as e:
        sys.stderr.write("Error in base64: decoding failed\n")
        sys.stderr.write( v)
    except AttributeError as e:
        sys.stderr.write("Error in cPickle: deserializable object is not declared in the given scope\n")
        sys.stderr.write( v)
        raise e

def init():
    out = sys.stdout
    sys.stdout = tempfile.NamedTemporaryFile(mode='w+r')
    global SSHRPC_IN
    # Trying to retreive the passed sshrpc frame
    if args._sshrpc_in != None:
        SSHRPC_IN = interprit(args._sshrpc_in)
    
    try:
        p = SSHRPC_IN['p']
    except KeyError:
        p = None
    except TypeError:
        return None

    f = SSHRPC_IN['f']
    # If f is a string then call it by-name:
    if isinstance(f, str):
        # Split the supplied string to produce a invokation sequence
        F = f.split('.')
        # First element in the sequence is a module
        M = F[0]
        # Importing the module and store it into f literal
        f = __import__(M)
        # If the sequence is longer then onle item, e.g., it contains modules or class names, then we have to parse it.
        if len(F) > 1:
            for i in range(1,len(F),1):
                try:
                    f = getattr(f, F[i])
                except KeyError as err:
                    print err
                    raise SSHRPCError("Broken invokation sequence: element {0} is not in an attribute of module/class {1}".format(f,F[i]), SSHRPCError.BROKEN_INVOKATION_SEQUENCE)
    
    try:
        if p != None and p != (None,):
            res = f(*p)
        else:
            res = f()
    except Exception as e:
        sys.stdout.seek(0)
        out.write(pack((sshrpc.FAIL, sys.stdout.read(), None), False))
        raise e
    sys.stdout.seek(0)
    out.write(pack((sshrpc.OK, sys.stdout.read(), res), False))

def clean_registry():
    global _CONNECTION_REGISTRY
    c = _CONNECTION_REGISTRY
    for k,v in c.iteritems():
        v.close()

if __name__ == '__main__':
    import ics_types as T
    import client
    a = T.users_table('asd','asd','123')
    s = sshrpc('172.17.0.2', 22, 'root', 'root') # Success
    s.connect()
    obj = s.execute("python /ICS/client.py", client.readf, "/ICS/hvac.py")
    print obj
