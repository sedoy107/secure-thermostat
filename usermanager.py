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


import client_api as API
import sys
from common import sha512

def _input(prompt, val_range):
    assert( val_range[0] <= val_range[1])
    x = ''
    while len(x) == 0:
        x = raw_input(prompt)
        if len(x) < val_range[1] and len(x) > val_range[0]:
            break
    return x

def login():
    print "Login:"
    username  = _input("Enter your username: ", (0,100))
    password = API.sha512(_input("Enter your password: ", (0,100)))
    return API.login(None, username, password), username, password

def create_user():
    print "Create new user:"
    username  = _input("Enter your new username: ", (0,100))
    password1 = _input("Enter your new password: ", (0,100))
    password2 = _input("Confirm your password:   ", (0,100))
    if password1 != password2:
        print "Passwords do not match. Cannot create a new user."
        return 1
    API.createUser(username, password1)
    print "User {0} was successfully created".format(username)
    return 0
    
def change_password():
    auth_id, username, pass_hash = login()
    password1 = API.sha512(_input("Enter your new password: ", (0,100)))
    password2 = API.sha512(_input("Confirm your password:   ", (0,100)))
    if password1 != password2:
        print "Passwords do not match. Cannot create a new user."
        return 1
    API.changePassword(auth_id, username, pass_hash, password2)
    print "Password for user {0} was successfully changed".format(username)
    return 0

def delete_user():
    auth_id, username, pass_hash = login()
    user_to_kill = _input("Enter the username you would like to remove: ", (0,100))
    API.deleteUser(auth_id, username, pass_hash, user_to_kill)
    print "User {0} was successfully deleted".format(user_to_kill)
    return 0

def _quit():
    sys.exit(0)
    
def show_help():
	def show_license():
		print "<program>  Copyright (C) <year>  <name of author>"
		print "This program comes with ABSOLUTELY NO WARRANTY."
		print "This is free software, and you are welcome to redistribute it"
		print "under certain conditions; type `show c' for details."
		print ""
	show_license()
	print "Welcome to Secure Thermostat User Manager."
    print "\tn - create a new user"
    print "\tc - change password"
    print "\td - delete a user"
    print "\th - show help"
    print "\tq - quit"

n = create_user
c = change_password
d = delete_user
h = show_help
q = _quit

def main():
    show_help()
    while(True):
        x = raw_input(">>> ")
        try:
            f = globals()[x]
            f()
        except KeyError:
            print "Wrong command"
        except API.CLIENTError as err:
            print err

if __name__ == '__main__':
    main()
