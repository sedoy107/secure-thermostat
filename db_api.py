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


"""
' Higher-level interface for interaction with database
"""

from ics_proto import *
from ics_types import *
import config
import mysql.connector
#~ from mysql.connector import errorcode
from common import *


class DBError(Exception):
    PREFIX = 'Database error'
    IDENTICAL_OBJECT = 0xff
    KEY_NOT_FOUND = 0xfe
    TYPE_ERROR = 0xfd
    DUP_KEY_ERROR = 0xfc
    DATA_INTERPRITATION_ERROR = 0xfb
    KNOWN_ERRORS = {IDENTICAL_OBJECT: 'IDENTICAL_OBJECT', KEY_NOT_FOUND: 'KEY_NOT_FOUND', TYPE_ERROR: 'TYPE_ERROR', DUP_KEY_ERROR: 'DUP_KEY_ERROR', DATA_INTERPRITATION_ERROR:'DATA_INTERPRITATION_ERROR'}
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


"""
' The following exceptions must be caught at the upper-level api

        except mysql.connector.errors.OperationalError as err: # Connection with databse failed # This happens if the connection with database is not established (the service itself is active though in this case)
            raise err
        except mysql.connector.errors.ProgrammingError as err: # The target table does not exist # This happens in case of wrod sytax and malformed statements
            raise err
        except mysql.connector.errors.InterfaceError as err: # The target table does not exist # This happen is I manually stop DB service, so there is nothing to connect to
            raise err
"""


def db_init(user=config.DB_USERNAME, password=config.DB_PASSWORD, host=config.DB_HOST, database=config.DB_NAME):
    try:
        cnx = mysql.connector.connect(user=user, password=password, host=host, database=database)
        return cnx
    except mysql.connector.Error as err:
        raise err
        #~ if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            #~ sys.stderr.write("Access denied. Wrong user name or password")
        #~ elif err.errno == errorcode.ER_BAD_DB_ERROR:
            #~ sys.stderr.write("Database does not exist")
        #~ else:
            #~ raise err


# get a list of attributes (key,value) of an object
def getDataItems(obj):
    attr = vars(obj).items()
    # delete element 'table'
    for i in range(0, len(attr)):
        if attr[i][0] == 'table':
            del attr[i]
            break
    for i in range(0, len(attr)):
        if attr[i][0] == 'key':
            del attr[i]
            break
    return attr


# get a list of names of attributes of an object
def getDataKey(obj):
    attr = getDataItems(obj)
    attr_list_key = []
    for i in range(0, len(attr)):
        attr_list_key.append(attr[i][0])
    attr_list_key.append('obj')
    # replace quotes with backtick "`" because database doesn't recognize quotes (single or double)
    return str(tuple(attr_list_key)).replace("'", "`")


# get a list of values of attributes of an object
def getDataVal(obj):
    attr = getDataItems(obj)
    attr_list_val = []
    for i in range(0, len(attr)):
        attr_list_val.append(attr[i][1])
    pic_obj = pickle(obj)
    attr_list_val.append(pic_obj)
    return attr_list_val


# computes a (%s,%s...) string depending on object's attributes
def getDataString(obj):
    obj_len = len(vars(obj).keys())
    s_str = '('
    for i in range(0, obj_len - 2):
        s_str += '%s,'
    s_str += '%s)'
    return s_str


# for insert queries
def insert(conn, obj):
    if not verify(obj):
        return None
    else:
        cur = conn.cursor()
        try:
            # key = object attribute names
            data_keys = getDataKey(obj)
            cmd = "Insert into " + obj.table + " " + data_keys + " VALUES " + getDataString(obj)
            # print cmd
            data_values = getDataVal(obj)  # get values of object attribute as a tuple/list
            # print data_values
            cur.execute(cmd, data_values)
            print "New object inserted"
            conn.commit()
            cur.close()
            return cur.lastrowid
        except mysql.connector.errors.IntegrityError as e:
            print e
            if e.errno == 1062:  # Duplicate key
                raise DBError("Object with primary key '{0}' already exists".format(obj.key), DBError.DUP_KEY_ERROR)
        except UnboundLocalError as err:
            print err


def getPrimKey(conn, obj):
    prim_key_index = None
    prim_keyval = None
    prim_key = None
    cur = conn.cursor()

    cmd = "SHOW KEYS FROM " + obj.table + " WHERE Key_name = 'PRIMARY' "
    cur.execute(cmd)
    # fetch all of the rows from the query
    data = cur.fetchall()
    if data > 0:
        prim_key = data[0][4]  # get primary key attribute name
        # print prim_key
        if isinstance(prim_key, unicode):
            prim_key = prim_key.encode("ascii")  # encode utf8 to ascii

        obj_list = getDataItems(obj)  # get list of all attributes (key,value) of object
        # # get primary key name and value from the list and delete that entry
        for i in range(0, len(obj_list)):
            if obj_list[i][0] == prim_key:
                prim_keyval = obj_list[i][1]
                prim_key_index = i
                break

    cur.close()
    conn.commit()
    return prim_key, prim_keyval, prim_key_index


def update(conn, obj):
    table = obj.table
    key = obj.key
    pkey_val = getattr(obj, key)  # get primary key value from object
    try:
        cur = conn.cursor()
        obj_list = getDataItems(obj)  # get list of all attributes (key,value) of object
        str_up = ''  # string to compute values to be updated
        # create %s string for update values such as "attr1 = %s, ..."
        for i in range(0, len(obj_list)):
            str_up += obj_list[i][0] + " = %s, "
        str_up += "obj = %s, "  # update obj at end
        str_up = str_up[:-2]
        # print str_up
        cmd = "UPDATE " + table + " SET " + str_up + " WHERE " + key + " = %s"
        # print cmd

        # compute list of data values to be updated
        data_val_up = []
        for i in range(0, len(obj_list)):
            data_val_up.append(obj_list[i][1])
        pic_obj = pickle(obj)
        data_val_up.append(pic_obj)  # add serialise obj
        data_val_up.append(pkey_val)  # add primary key value for test condition
        # print data_val_up

        cur.execute(cmd, data_val_up)
        # if no rows updated then raise exception
        if cur.rowcount > 0:
            # print "Duplicate Key Updated"
            print cur.rowcount, " row(s) updated"
            conn.commit()
            return pkey_val
        else:
            raise DBError("entry with primary key %s = %s not updated" % (key, pkey_val),
                          DBError.IDENTICAL_OBJECT)

    except DBError as e:
        print e
        conn.rollback()
        if e.getError() == DBError.KEY_NOT_FOUND:
            raise e  # If the key not found then either a programmer has screwed or really the key has gone
            # This situation is ambigous in the way that depending on a situation you either wanna pass it along or suppress
            # therefore it should be re-raised for generality

    finally:
        cur.close()


'''

' If keyv is specified then it selects by primary key, provide the primary key value only
' If sql_condition is specified then ignore keyv and select according with the sql_condition
' If sql_condition == None and keyv == None then select everything
'''


def select(conn, ics_type, field="obj", keyv=None, sql_condition=None):
    table = ics_type.TABLE
    key = ics_type.KEY

    if isinstance(keyv, str) or isinstance(keyv, unicode):
        keyv = "'{0}'".format(keyv)

    cur = conn.cursor()

    if sql_condition is None and keyv is None:
        cmd = "SELECT " + field + "," + key + " from `" + table + "`"
    elif sql_condition is None and keyv is not None:
        sql_condition = "{0}={1}".format(key, keyv)
        cmd = "SELECT " + field + "," + key + " from `" + table + "` WHERE " + sql_condition
    else:
        cmd = "SELECT " + field + "," + key + " from `" + table + "` WHERE " + sql_condition
    print cmd

    try:
        cur.execute(cmd)
    except mysql.connector.errors.ProgrammingError as err:
        print err
        raise DBError("The sql_condition '{0}' has values that do not correspond to their types.".format(sql_condition),
                      DBError.TYPE_ERROR)
    data = cur.fetchall()
    cur.close()
    #~ print data
    obj_res_dict = {}
    for row in data:
        # list to store the objects returned by query
        res_obj = row[0]    # get resulting object
        # print type(res)
        if isinstance(res_obj, unicode):
            res_obj = res_obj.encode("ascii")  # encode utf8 to ascii
            # print res_obj
        try:
            unpic_obj = unpic(res_obj)       # deserialize object
            if unpic_obj != None:
                setattr(unpic_obj, key, row[1])  # Synchronize primary key in the object
            else:
                unpic_obj = res_obj
        except TypeError:
            unpic_obj = res_obj       # deserialize object
        except AttributeError as err:
            print err
            print res_obj
            raise err
        
        # add in dictionary (key,value) pair ---> (primary key value, obj)
        obj_res_dict[row[1]] = unpic_obj

    conn.commit()
    cur.close()
    return obj_res_dict


'''
' If keyv is specified then delete by primary key
' If sql_condition is specified then ignore keyv and delete according with the sql_condition
' If sql_condition == None and keyv == None then truncate the table
'''


def delete(conn, ics_type, keyv=None, sql_condition=None):
    table = ics_type.TABLE
    key = ics_type.KEY
    if isinstance(keyv, str):
        keyv = "'{0}'".format(keyv)

    cur = conn.cursor()
    # remove all rows from the given table
    if sql_condition is None and keyv is None:
        cmd = "TRUNCATE TABLE `" + table + "`"
    # remove rows with given primary key value only
    elif sql_condition is None and keyv is not None:
        sql_condition = "{0}={1}".format(key, keyv)
        cmd = "DELETE from `" + table + "` WHERE " + sql_condition
    # generic delete for all other keys and conditions
    else:
        cmd = "DELETE from `" + table + "` WHERE " + sql_condition
    print cmd
    try:
        cur.execute(cmd)
    except mysql.connector.errors.ProgrammingError as err:
        print err
        raise DBError("The sql_condition '{0}' is malformed".format(sql_condition), DBError.TYPE_ERROR)
    print cur.rowcount, "row(s) deleted"
    conn.commit()
    cur.close()
    return None


if __name__ == '__main__':
    cnx = db_init()
    a = users_table('chitra', sha512('458'), timestamp())
    b = users_table('anji', sha512('789'), timestamp())
    d = current_sensors_table('sensor121', 1, 3, timestamp(), timestamp(), 'zzzzzzzzzzzzzzz')

    # insert(cnx, a)
    # insert(cnx, d)
    # update(cnx, d)
    # f = select (cnx, 'users',"username = 'chitra'")
    # f = select(cnx, current_sensors_table, sql_condition="priority=3")
    # f = select(cnx, current_sensors_table)
    # print f
    # delete(cnx, current_sensors_table, sql_condition="status=1 AND priority=3")

    cnx.close()
