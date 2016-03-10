from flask import Flask, request, Response, abort, g
from flask.ext.api import status
from jsonschema.exceptions import ValidationError
from tables import *
from user import User
import json
import jsonschema
import os
import sqlite3

app = Flask(__name__)
app.config["DATABASE"] = os.getenv('DATABASE', "planet.db")

def success(code = status.HTTP_200_OK, response = ""):
    """
    note, if response is an object it should be serialized
    to a string before calling this
    """
    return (response, code)

def error(code, error_text = ""):
    return (json.dumps({'error': error_text}), code)

@app.before_request
def before_request():
    """
    before each request, create a thread local connection to the
    on-disk sqlite database
    """
    if not hasattr(g, 'connection'):
        g.connection = sqlite3.connect(app.config["DATABASE"])

@app.teardown_request
def teardown_request(exception):
    """ at the end of each request, close the sqlite connection. """
    if hasattr(g, 'connection'):
        g.connection.close()

@app.route('/')
def home():
    return """
           Welcome to Planet App, here's some light reading:
           <br>
           <a href='https://en.wikipedia.org/wiki/Sun-synchronous_orbit'>
               en.wikipedia.org/wiki/Sun-synchronous_orbit
           </a>
           """

@app.route("/users", methods=['POST'])
def create_user():
    """
    create a user and add them to requested groups
    any groups which don't exist will be created.
    """
    try:
        user = User.from_json(json.loads(request.get_data()))
        UsersTable.save(g.connection, user)
        GroupsTable.add_user_to_groups(g.connection, user.userid, user.groups)
        return success(status.HTTP_200_OK)
    except (ValidationError, ValueError):
        return error(status.HTTP_400_BAD_REQUEST, "input validation failed")
    except RecordAlreadyExists:
        return error(status.HTTP_409_CONFLICT, "user {0} already exists".format(user.userid))
    
@app.route("/users/<userid>", methods=['GET'])
def get_user(userid):
    user_record = UsersTable.fetch(g.connection, userid)
    if user_record:
        group_names = UserGroupJoinTable.fetch_user_group_names(g.connection, userid)
        user        = User.from_user_record(user_record, group_names)
        return success(response = user.to_json())
    else:
        return error(status.HTTP_404_NOT_FOUND, "user {0} not found".format(userid))

@app.route("/users/<userid>", methods=['DELETE'])
def delete_user(userid):
    try:
        UsersTable.delete(g.connection, userid)
        return success()
    except RequiredRecordNotFound:
        return error(
            status.HTTP_404_NOT_FOUND,
            "user {0} doesn't exist and cannot be deleted".format(userid)
        )

@app.route("/users/<userid>", methods=['PUT'])
def update_user(userid):
    try:
        user = User.from_json(json.loads(request.get_data()))
        UsersTable.update(g.connection, userid, user)
        return success(status.HTTP_200_OK)
    except (ValidationError, ValueError):
        return error(status.HTTP_400_BAD_REQUEST, "input validation failed")
    except RequiredRecordNotFound:
        return error(status.HTTP_404_NOT_FOUND, "user {0} not found".format(userid))
    except RecordAlreadyExists: 
        return error(
            status.HTTP_409_CONFLICT,
            "update_failed: userid {0} is already taken".format(user.userid)
        )

@app.route("/groups/<group_name>", methods=['GET'])
def get_group(group_name):
    group = GroupsTable.fetch(g.connection, group_name)
    if group: 
        userids = UserGroupJoinTable.fetch_members(g.connection, group_name)
        return success(response = json.dumps(userids))
    else:
        return error(status.HTTP_404_NOT_FOUND, "group {0} not found".format(group_name))

@app.route('/groups', methods=['POST'])
def create_group():
    # typed schema specification for the, albeit simple, group object.
    group_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
        },
        "required": ["name"]     
    }

    try:
        group_object = json.loads(request.get_data())
        jsonschema.validate(group_object, group_schema)
        group_name = group_object["name"]
        try:
            GroupsTable.save(g.connection, group_name) 
            return success()
        except RecordAlreadyExists:
            return error(status.HTTP_409_CONFLICT, "group {0} already exists".format(group_name))
    except (ValidationError, ValueError):
        return error(status.HTTP_400_BAD_REQUEST, "input validation failed")

@app.route('/groups/<group_name>', methods=['PUT'])
def update_group(group_name):
    """
    updates a group membership from a provided list of users
    only succeeds if all users already exist.
    """
    # typed schema specification for a unique or empty list of strings
    request_schema = {
        "type": "array",
        "items": {"type": "string"},
        "uniqueItems": True,
        "minItems": 0
    }

    group = GroupsTable.fetch(g.connection, group_name)
    if group:
        try:
            userids = json.loads(request.get_data())
            jsonschema.validate(userids, request_schema)
            UserGroupJoinTable.update_members(g.connection, group_name, userids)
            return success()
        except (ValidationError, ValueError):
            return error(status.HTTP_400_BAD_REQUEST, "input validation failed")
        except RequiredRecordsNotFound as e:
            return error(status.HTTP_404_NOT_FOUND, str(e))
    else:
        return error(status.HTTP_404_NOT_FOUND, "group {0} not found".format(group_name))

@app.route('/groups/<group_name>', methods=['DELETE'])
def delete_group(group_name):
    try:
        GroupsTable.delete(g.connection, group_name) 
        return success()
    except RequiredRecordNotFound:
        return error(
            status.HTTP_404_NOT_FOUND,
            "group {0} doesn't exist and cannot be deleted".format(group_name)
        )

if __name__ == '__main__':
    app.run()


