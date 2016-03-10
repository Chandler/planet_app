import sqlite3
from collections import namedtuple

# static per-table helpers to perform all the sqlite specific database operations needed
# by planet app. For an application this small, a full scale ORM/Model
# abstration is not needed.

class RecordAlreadyExists(Exception):
    pass

class RequiredRecordNotFound(Exception):
    pass

class RequiredRecordsNotFound(Exception):
    pass

# a named representation of a row in the users table
UserRecord = namedtuple('UserRecord', 'pkey, userid, first_name, last_name')

# a named representation of a row in the groups table
GroupRecord = namedtuple('GroupRecord', 'pkey, name')

def create_sql_list(items):
    """
    creates a param enclosed string literal from a
    list like: ('1', '2', '3') for use in SQL IN statements
    """
    return "(" + ",".join(["'{0}'".format(item) for item in items]) + ")"

class UsersTable(object):
    @staticmethod
    def save(conn, user):
        """ create a user record from an `app.User` object """
        try:
            query = """
                    INSERT INTO users (userid, first_name, last_name) VALUES (?, ?, ?)
                    """
            values = (user.userid, user.first_name, user.last_name)
            conn.execute(query, values)
            conn.commit()
        except sqlite3.IntegrityError:
            raise RecordAlreadyExists

    @staticmethod
    def fetch(conn, userid):
        cursor = conn.cursor()
        query = """
                SELECT * FROM users WHERE userid = ?
                """
        cursor.execute(query, (userid,))
        row = cursor.fetchone()

        if row:
            return UserRecord(
                pkey       = row[0],
                userid     = row[1],
                first_name = row[2],
                last_name  = row[3],
            )
        else:
            return None

    @staticmethod
    def delete(conn, userid):
        cursor = conn.cursor()
        query = """
                DELETE FROM users WHERE userid = ?
                """
        cursor.execute(query, (userid,))
        conn.commit()
        if cursor.rowcount == 0:
            raise RequiredRecordNotFound

        UserGroupJoinTable.delete_user(conn, userid)

    @staticmethod
    def update(conn, original_userid, user):
        """ update a user record from an `app.User` object """
        cursor = conn.cursor()
        query = """
                UPDATE users
                SET userid = ?, first_name = ?, last_name = ?
                WHERE userid = ?
                """
        try:
            cursor.execute(query, (user.userid, user.first_name, user.last_name, original_userid))
            conn.commit()
            if cursor.rowcount == 0:
                raise RequiredRecordNotFound

            # if needed, rewrite existing group mappings to the new userid
            if original_userid != user.userid:
                UserGroupJoinTable.update_userid(
                    conn,
                    new_userid = user.userid,
                    old_userid = original_userid
                )

            # now ensure that any new groups have been created and linked
            GroupsTable.add_user_to_groups(conn, user.userid, user.groups)

            # Lastely, we need to make sure and delete any groups we no longer a part of
            UserGroupJoinTable.prune_stale_groups(conn, user.userid, user.groups)

        except sqlite3.IntegrityError:
            raise RecordAlreadyExists

class GroupsTable(object):
    @staticmethod
    def add_user_to_groups(conn, userid, groups):
        """ 
        user: an `app.User` object
        update: whether or not to check for and delete stale
        group memberships. Needed on update, not on create.
        
        1) create any groups on the user object if they don't already exist
           (it's not an error if they do exist)
        2) add the user to all listed groups
        
        """
        
        if len(groups) > 0:
            # bulk optional insert the groups
            query = """
                INSERT OR IGNORE INTO groups (name) VALUES (?)
            """
            values = [[group_name] for group_name in groups]
            cursor = conn.cursor()
            cursor.executemany(query, values)
            conn.commit()
            
            # now that all groups are created, create join entries to tie
            # the user to all groups
            for group_name in groups:
                UserGroupJoinTable.create_join(conn, userid, group_name)

    @staticmethod
    def fetch(conn, group_name):
        cursor = conn.cursor()
        query = """
                SELECT * FROM groups WHERE name = ?
                """
        cursor.execute(query, (group_name,))
        row = cursor.fetchone()
        if row:
            return GroupRecord(
                pkey = row[0],
                name = row[1]
            )
        else:
            return None

    @staticmethod
    def save(conn, group_name):
        """ create a new empty group """
        try:
            query = """
                    INSERT INTO groups (name) VALUES (?)
                    """
            conn.execute(query, (group_name,))
            conn.commit()
        except sqlite3.IntegrityError:
            raise RecordAlreadyExists

    @staticmethod
    def delete(conn, group_name):
        cursor = conn.cursor()
        query = """
                DELETE FROM groups WHERE name = ?
                """
        cursor.execute(query, (group_name,))
        conn.commit()
        if cursor.rowcount == 0:
            raise RequiredRecordNotFound

        UserGroupJoinTable.delete_group(conn, group_name)

class UserGroupJoinTable(object):
    @staticmethod
    def create_join(conn, userid, group_name):
        query = """
                INSERT OR IGNORE INTO user_group_join (userid, group_name) VALUES (?, ?)
                """
        conn.execute(query, (userid, group_name))
        conn.commit()

    @staticmethod
    def fetch_user_group_names(conn, userid):
        """ return the names of all groups a user is a member of """
        cursor = conn.cursor()

        query = """
                SELECT * FROM user_group_join
                WHERE userid = ? ORDER BY group_name ASC
                """
        group_names = []
        for row in cursor.execute(query, (userid,)):
            group_names.append(row[2])

        return group_names

    @staticmethod
    def update_userid(conn, new_userid, old_userid):
        """ when a user updates their userid, we need to update their group mappings"""
        cursor = conn.cursor()
        query = """
                UPDATE user_group_join
                SET userid = ?
                WHERE userid = ?
                """
        cursor.execute(query, (new_userid, old_userid))
        conn.commit()

    @staticmethod
    def prune_stale_groups(conn, userid, group_names):
        """
         given a list of known good group names, remove the user from any groups not in this list
         this is used when a user's group membership is updated
        """
        cursor = conn.cursor()
        query = """
                DELETE FROM user_group_join
                WHERE userid = '{0}' AND group_name NOT IN {1}
                """.format(userid, create_sql_list(group_names))
        cursor.execute(query)
        conn.commit()

    @staticmethod
    def fetch_members(conn, group_name):
        """ return the userids of all members of the group """
        cursor = conn.cursor()
        query = """
                SELECT userid FROM user_group_join WHERE group_name = ?
                """
        cursor.execute(query, (group_name,))

        userids = [row[0] for row in cursor.fetchall()]

        return userids

    @staticmethod
    def update_members(conn, group_name, members):
        cursor = conn.cursor()

        query = """
                SELECT userid FROM users WHERE userid IN {0}
                """.format(create_sql_list(members))

        cursor.execute(query)

        found_members = [row[0] for row in cursor.fetchall()]
        missing_members = (set(members) - set(found_members))

        if len(missing_members) > 0:
            raise RequiredRecordsNotFound(
                """
                cannot update group membership because the following
                users don't exist {0}
                """.format(",".join(missing_members))
            )

        # create new memberships
        query = """
                INSERT OR IGNORE INTO user_group_join (userid, group_name) VALUES (?, ?)
                """
        values = [[userid, group_name] for userid in members]
        cursor.executemany(query, values)
        conn.commit()

        # delete old memberships
        query = """
                DELETE FROM user_group_join
                WHERE group_name = '{0}' AND userid NOT IN {1}
                """.format(group_name, create_sql_list(members))
        cursor.execute(query)
        conn.commit()

    @staticmethod
    def delete_group(conn, group_name):
        """ delete all join records for a group """
        cursor = conn.cursor()
        query = """
                DELETE FROM user_group_join WHERE group_name = ?
                """
        cursor.execute(query, (group_name,))
        conn.commit()

    @staticmethod
    def delete_user(conn, userid):
        """ delete all join records belonging to a user """
        cursor = conn.cursor()
        query = """
                DELETE FROM user_group_join WHERE userid = ?
                """
        cursor.execute(query, (userid,))
        conn.commit()
