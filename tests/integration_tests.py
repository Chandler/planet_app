from flask import Flask
from flask.ext.api import status
from flask.ext.testing import LiveServerTestCase
from os import path
import copy
import json
import os
import random
import requests
import sys
import tempfile
import unittest
import uuid

sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
from app import planet_app
from utils.create_tables import create_tables

class PlanetAppIntegrationTest(LiveServerTestCase):
    """
    test the planet app specs through a live local HTTP interface

    All behavior in specification.md is enforced through these tests,
    originally undefined behavior is also tested (and now defined) here.

    tests:
        test_fetch_found_user
        test_fetch_not_found_user
        test_create_user_valid_input
        test_create_user_malformed_inputs
        test_create_existing_user
        test_delete_user
        test_delete_not_found_user
        test_update_user
        test_update_not_found_user
        test_update_user_malformed_body
        test_update_userid_already_taken
        test_fetch_group_members
        test_fetch_not_found_group
        test_create_group
        test_create_group_existing_name
        test_create_group_malformed_input
        test_update_group_membership
        test_group_update_with_notfound_users
        test_group_update_malformed_input
        test_delete_group
        test_user_removed_from_deleted_group

    """

    def create_app(self):
        """ 
        configure a test version of planet app that will be started
        locally against a temporary sqlite database
        """
        with tempfile.NamedTemporaryFile(dir='/tmp', delete=False) as tmpfile:
            self.tmp_db_filename = tmpfile.name
        create_tables(self.tmp_db_filename)
        app = planet_app.app
        app.config["DATABASE"] = self.tmp_db_filename
        app.config['TESTING'] = True
        app.config['LIVESERVER_PORT'] = 5001
        app.config["PROPAGATE_EXCEPTIONS"] = True
        return app

    def tearDown(self):
        """ delete the sqlite database from this test run"""
        os.unlink(self.tmp_db_filename)

    def random_string(self):
        return str(uuid.uuid4())
    
    def random_list(self):
        return [self.random_string() for _ in range(random.randint(0,10))]
    
    def random_user_object(self):
        return {
            "first_name": self.random_string(),
            "last_name": self.random_string(),
            "userid": self.random_string(),
            "groups": sorted(self.random_list())
        }
   
    def create_user_fixed_group(self, group):
        user_object = self.random_user_object()
        user_object["groups"] = [group]
        response = requests.post(self.get_server_url() + "/users", data = json.dumps(user_object))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return user_object["userid"]

    # SPEC:
    # GET /users/<userid>
    #     Returns the matching user record or 404 if none exist.
    def test_fetch_found_user(self):
        # first create a user
        user_object = self.random_user_object()
        response = requests.post(self.get_server_url() + "/users", data = json.dumps(user_object))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # then read the write and make sure it's equal to the post
        response = requests.get(self.get_server_url() + "/users/" + user_object["userid"])
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(response.text), user_object)

    def test_fetch_not_found_user(self):
        # then read the write and make sure it's equal to the post
        response = requests.get(self.get_server_url() + "/users/doesnt_exist")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # SPEC:
    # POST /users
    #     Creates a new user record. The body of the request should be a valid user
    #     record. POSTs to an existing user should be treated as errors and flagged
    #     with the appropriate HTTP status code.
    def test_create_user_valid_input(self):
        user_object = self.random_user_object()
        response = requests.post(self.get_server_url() + "/users", data = json.dumps(user_object))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_user_malformed_inputs(self):
        # test totally incorrect input
        response = requests.post(self.get_server_url() + "/users", data = json.dumps({'bogus': 'schema'}))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # test input that is only missing one field
        missing_one_field = self.random_user_object()
        missing_one_field["userid"] = None

        response = requests.post(self.get_server_url() + "/users", data = json.dumps((missing_one_field)))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_existing_user(self):
        user_object = self.random_user_object()

        response = requests.post(self.get_server_url() + "/users", data = json.dumps(user_object))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        #second attempt at creating `user` should fail
        response = requests.post(self.get_server_url() + "/users", data = json.dumps(user_object))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    # SPEC: 
    # DELETE /users/<userid>
    #     Deletes a user record. Returns 404 if the user doesn't exist.
    def test_delete_user(self):
        user_object = self.random_user_object()

        # create a user
        response = requests.post(self.get_server_url() + "/users", data = json.dumps(user_object))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # fetch the user, ensure that it's found
        response = requests.get(self.get_server_url() + "/users/" + user_object["userid"])
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(response.text), user_object)

        # delete the user
        response = requests.delete(self.get_server_url() + "/users/" + user_object["userid"])
        self.assertEqual(response.status_code, status.HTTP_200_OK)
   
        # ensure that the user cannot be found anymore
        response = requests.get(self.get_server_url() + "/users/" + user_object["userid"])
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_not_found_user(self):
        response = requests.delete(self.get_server_url() + "/users/" + self.random_string())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
   
    # SPEC: 
    # PUT /users/<userid>
    #     Updates an existing user record. The body of the request should be a valid
    #     user record. PUTs to a non-existant user should return a 404.
    def test_update_user(self):
        user_object = self.random_user_object()

        # create a user
        response = requests.post(self.get_server_url() + "/users", data = json.dumps(user_object))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        new_user_object = copy.deepcopy(user_object)
        new_user_object["userid"] = self.random_string()
        new_user_object["first_name"] = self.random_string()

        # update the old user with the new fields
        response = requests.put(
            self.get_server_url() + "/users/" + user_object["userid"],
            data = json.dumps(new_user_object)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # old userid should not be not found
        response = requests.get(self.get_server_url() + "/users/" + user_object["userid"])
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # user should be readable at new userid
        response = requests.get(self.get_server_url() + "/users/" + new_user_object["userid"])
        # sort by group name so we can compare to the sorted server response
        new_user_object["groups"].sort()
        self.assertEqual(json.loads(response.text), new_user_object)

    def test_update_not_found_user(self):
        user_object = self.random_user_object()

        # make a request for a user that doesn't exist
        response = requests.put(
            self.get_server_url() + "/users/" + user_object["userid"],
            data = json.dumps(user_object)
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_user_malformed_body(self):
        user_object = self.random_user_object()

        # create a user
        response = requests.post(self.get_server_url() + "/users", data = json.dumps(user_object))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # attempt to update the user with bogus modifications
        response = requests.put(
            self.get_server_url() + "/users/" + user_object["userid"],
            data = json.dumps({'bogus': 'schema'})
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # ensure the user didn't get updated and still has the old values
        response = requests.get(self.get_server_url() + "/users/" + user_object["userid"])
        self.assertEqual(json.loads(response.text), user_object)

    def test_update_userid_already_taken(self):
        """ ensure that an update fails if the userid they want is already taken """

        # create user1
        user_object_1 = self.random_user_object()
        response = requests.post(self.get_server_url() + "/users", data = json.dumps(user_object_1))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # create user2
        user_object_2 = self.random_user_object()
        response = requests.post(self.get_server_url() + "/users", data = json.dumps(user_object_2))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # attempt to update user1 to user2's userid.
        response = requests.put(
            self.get_server_url() + "/users/" + user_object_1["userid"],
            data = json.dumps(user_object_2)
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

        # ensure the user didn't get updated and still has the old values
        response = requests.get(self.get_server_url() + "/users/" + user_object_1["userid"])
        self.assertEqual(json.loads(response.text), user_object_1)
 
    # SPEC:
    # GET /groups/<group name>
    #     Returns a JSON list of userids containing the members of that group. Should
    #     return a 404 if the group doesn't exist.
    def test_fetch_group_members(self):
        """
        create a group with a random number of members and ensure that the member
        list can be accurately fetched
        """
        group_name = self.random_string()
        userids = []
        # create a random number of users in our group
        for _ in range(random.randint(0,25)):
            userids.append(self.create_user_fixed_group(group_name))

        response = requests.get(self.get_server_url() + "/groups/" + group_name)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # ensure we can fetch all the group members
        self.assertEqual(sorted(json.loads(response.text)), sorted(userids))

    def test_fetch_not_found_group(self):
        response = requests.get(self.get_server_url() + "/groups/" + self.random_string())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # SPEC: 
    # POST /groups
    #     Creates a empty group. POSTs to an existing group should be treated as
    #     errors and flagged with the appropriate HTTP status code. The body should contain
    #     a `name` parameter
    def test_create_group(self):
        group_object = { "name": self.random_string() }
        response = requests.post(self.get_server_url() + "/groups", data = json.dumps(group_object))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_group_existing_name(self):
        """ should fail with 409 conflict if you attempt to create an existing group """
        group_object = { "name": self.random_string() }
        response = requests.post(self.get_server_url() + "/groups", data = json.dumps(group_object))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = requests.post(self.get_server_url() + "/groups", data = json.dumps(group_object))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_create_group_malformed_input(self):
        # name must be present
        group_object = { "bogus": "schema" }
        response = requests.post(self.get_server_url() + "/groups", data = json.dumps(group_object))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # name must be a string
        group_object = { "name": 1 }
        response = requests.post(self.get_server_url() + "/groups", data = json.dumps(group_object))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # SPEC: 
    # PUT /groups/<group name>
    #     Updates the membership list for the group. The body of the request should 
    #     be a JSON list describing the group's members.
    def test_update_group_membership(self):
        """
        This test ensure that users and be added and removed from
        group membership
        """
        group_name = self.random_string()
        
        # add some users to our group
        in_group_users = []
        for _ in range(random.randint(5,25)):
            in_group_users.append(self.create_user_fixed_group(group_name))

        # create some users who are not in the group
        not_in_group_users = []
        for _ in range(random.randint(1,3)):
            user_object = self.random_user_object()           
            response = requests.post(self.get_server_url() + "/users", data = json.dumps(user_object))
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            not_in_group_users.append(user_object["userid"])

        # create a new list of users with the following properties:
        #  1) some of the original users are missing
        #  2) there are some users who were not in the original list
        new_membership_set = in_group_users[1:] + not_in_group_users

        # do the update
        response = requests.put(
            self.get_server_url() + "/groups/" + group_name,
            data = json.dumps(new_membership_set)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # the expection is that after this request the group
        # membership will now be missing some original users
        # and have gained new users
        response = requests.get(self.get_server_url() + "/groups/" + group_name)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(sorted(json.loads(response.text)), sorted(new_membership_set))

    def test_group_update_with_notfound_users(self):
        """
        if any of the members in the request body are not found
        the entire request should fail
        """
        group_name = self.random_string()

        # create a user and put them in a group
        userid = self.create_user_fixed_group(group_name)

        # update the group adding a user who doesn't exist
        response = requests.put(
            self.get_server_url() + "/groups/" + group_name,
            data = json.dumps([userid, self.random_string()])
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


    def test_group_update_malformed_input(self):
        # create a user and put them in a group
        group_name = self.random_string()
        userid = self.create_user_fixed_group(group_name)
      
        # attempt to update the group with non-unique input
        response = requests.put(
            self.get_server_url() + "/groups/" + group_name,
            data = json.dumps(["non-unique", "non-unique"])
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # SPEC: 
    # DELETE /groups/<group name>
    #     Deletes a group.
    def test_delete_group(self):
        # create a group
        group_object = { "name": self.random_string() }
        response = requests.post(self.get_server_url() + "/groups", data = json.dumps(group_object))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # fetch the group, ensure that it's found
        response = requests.get(self.get_server_url() + "/groups/" + group_object["name"])
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # delete the group
        response = requests.delete(self.get_server_url() + "/groups/" + group_object["name"])
        self.assertEqual(response.status_code, status.HTTP_200_OK)
   
        # ensure that the group cannot be found anymore
        response = requests.get(self.get_server_url() + "/groups/" + group_object["name"])
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_removed_from_deleted_group(self):
        """ when a group is a deleted, make sure the user group edges are removed """

        group_name = self.random_string()

        # create a user and put them in a group
        userid = self.create_user_fixed_group(group_name)

        # ensure that the user is in the group
        response = requests.get(self.get_server_url() + "/users/" + userid)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(response.text)["groups"], [group_name])

        # delete the group
        response = requests.delete(self.get_server_url() + "/groups/" + group_name)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
   
        # ensure that the user has no groups
        response = requests.get(self.get_server_url() + "/users/" + userid)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(response.text)["groups"], [])

if __name__ == '__main__':
    unittest.main()