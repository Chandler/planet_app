import sqlite3
from os import sys

# use as a script:
#   python utils/create_tables.py planet.db

def create_tables(db_name):
    conn = sqlite3.connect(db_name)

    # "userid" comes from the specification
    # if this project were continued I would probably
    # switch it out for uuid "user_id" and a user defined
    # "user_name"
    conn.execute(
        """
        CREATE TABLE users (
            pkey INTEGER PRIMARY KEY,
            userid varchar(200) NOT NULL UNIQUE,
            first_name varchar(200) NOT NULL,
            last_name varchar(200) NOT NULL
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE groups (
            pkey INTEGER PRIMARY KEY,
            name text UNIQUE
        )
        """
    )

    # this join table models group membership
    #
    # using the text fields userid and group_name
    # in the join table would probably not be a great
    # decision in a large application, but for a small
    # app like this it simplifies things
    # and the join table becomes human readable
    conn.execute(
        """
        CREATE TABLE user_group_join (
            pkey INTEGER PRIMARY KEY,
            userid varchar(200) NOT NULL,
            group_name varchar(200) NOT NULL,
            UNIQUE(userid, group_name)
        )
        """
    )

    conn.commit()

if __name__ == '__main__':
    db_name = sys.argv[1]
    create_tables(db_name)

