from jsonschema import validate
import json

class User(object):
    """
    Represents the logical User object that is exposed on the API.
    This user contains more info than what is present in the the `users` table,
    it also contains a list of the user's groups.
    """

    # a typed schema for the JSON version of this User object.
    # This can be used to validate the structure of a user provided
    # json object.
    json_schema = {
        "type": "object",
        "properties": {
            "first_name": {"type": "string"},
            "last_name":  {"type": "string"},
            "userid":     {"type": "string"},
            "groups": {
                "type": "array",
                "items": {"type": "string"},
                "uniqueItems": True,
                "minItems": 0
            },
        },
        "required": [
            "first_name",
            "last_name",
            "userid",
            "groups"
        ]
    }

    def __init__(self, userid, first_name, last_name, groups):
        self.userid     = userid
        self.first_name = first_name
        self.last_name  = last_name
        self.groups     = groups
    
    @classmethod
    def from_user_record(cls, user_record, group_names):
        """
        Construct a User object from a record from the users table
        along with a list of group names
        """
        return cls(
            userid     = user_record.userid,
            first_name = user_record.first_name,
            last_name  = user_record.last_name,
            groups     = group_names
        )

    @classmethod
    def from_json(cls, json_user):
        """
        Construct a User object from a Json object, usually user provided.
        Throws if the json does not conform to the typed json schema
        """
        validate(json_user, cls.json_schema)

        return cls(
            userid     = json_user["userid"],
            first_name = json_user["first_name"],
            last_name  = json_user["last_name"],
            groups     = json_user["groups"]
        )

    def to_json(self):
        json_user = json.dumps(self.__dict__)
        
        # as a sanity check validate that the serialized form
        # of this object conforms to the typed schema
        validate(json.loads(json_user), self.json_schema)
        
        return json_user
