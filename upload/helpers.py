from cerberus import Validator
from rest_framework.exceptions import ValidationError

# TODO
def validate_params(data):

    params_schema = {
        "version": {"type": "string", "required": True, "allowed": ["v2", "v4"]}
    }

    v = Validator(params_schema)
    if not v.validate(data):
        raise ValidationError(v.errors)
