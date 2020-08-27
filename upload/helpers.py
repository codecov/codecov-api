from cerberus import Validator
from rest_framework.exceptions import ValidationError

from .constants import ci


def parse_params(data):
    """
    This function will validate the input request parameters and do some additional parsing/tranformation of the params.
    """

    # filter out empty values from the data; this makes parsing and setting defaults a bit easier
    non_empty_data = {
        key: value for key, value in data.items() if value not in [None, ""]
    }

    params_schema = {
        "version": {"type": "string", "required": True, "allowed": ["v2", "v4"]},
        # commit SHA
        "commit": {
            "type": "string",
            "required": True,
            "regex": r"^\d+:\w{12}|\w{40}$",
            "coerce": lambda value: value.lower(),
        },
        "slug": {"type": "string", "regex": r"^[\w\-\.\~\/]+\/[\w\-\.]{1,255}$"},
        # owner username, we set this by splitting the value of "slug" on "/" if provided
        "owner": {
            "type": "string",
            "nullable": True,
            "default_setter": (
                lambda document: document.get("slug")
                .rsplit("/", 1)[0]
                .replace(
                    "/", ":"
                )  # we use ':' as separator for gitlab subgroups internally
                if document.get("slug")
                and len(document.get("slug").rsplit("/", 1)) == 2
                else None
            ),
        },
        # repo name, we set this by parsing the value of "slug" if provided
        "repo": {
            "type": "string",
            "nullable": True,
            "default_setter": (
                lambda document: document.get("slug").rsplit("/", 1)[1]
                if document.get("slug")
                and len(document.get("slug").rsplit("/", 1)) == 2
                else None
            ),
        },
        # repository upload token
        "token": {
            "type": "string",
            "regex": r"^[0-9a-f]{8}(-?[0-9a-f]{4}){3}-?[0-9a-f]{12}$",
        },
        # name of the CI service used, must be a name in the list of CI services we support
        "service": {
            "type": "string",
            "allowed": list(ci.keys()),
            "coerce": (
                lambda value: "travis" if value == "travis-org" else value,
            ),  # if "travis-org" was passed as the service rename it to "travis" before validating
        },
        # pull request number
        # if a value is passed to the "pull_request" field and not to "pr", we'll use that to set the value of this field
        "pr": {
            "type": "string",
            "regex": r"^(\d+|false|null|undefined|true)$",
            "nullable": True,
            "default_setter": (lambda document: document.get("pull_request")),
            "coerce": (
                lambda value: None if value in ["false", "null", "undefined"] else value
            ),
        },
        # pull request number
        # "deprecated" in the sense that if a value is passed to this field, we'll use it to set "pr" and use that field instead
        "pull_request": {  # pull request number
            "type": "string",
            "regex": r"^(\d+|false|null|undefined|true)$",
            "nullable": True,
            "coerce": (
                lambda value: None
                if value in ["false", "null", "undefined", "true"]
                else value
            ),
        },
        "build_url": {"type": "string", "regex": r"^https?\:\/\/(.{,100})",},
        "flags": {"type": "string", "regex": r"^[\w\.\-\,]+$",},
        # if prefixed with "origin/" or "refs/heads", the prefix will be removed
        "branch": {
            "type": "string",
            "coerce": (
                lambda value: value[7:]
                if value[:7] == "origin/"
                else value[11:]
                if value[:11] == "refs/heads/"
                else value,
            ),
        },
        "tag": {"type": "string"},
        # if a value is passed to "travis_job_id" and not to "job", we'll use that to set the value of this field
        "job": {
            "type": "string",
            "nullable": True,
            "default_setter": (lambda document: document.get("travis_job_id")),
        },
        # "deprecated" in the sense that if a value is passed to this field, we'll use it to set "job" and use that field instead
        "travis_job_id": {"type": "string", "nullable": True, "empty": True},
        "build": {
            "type": "string",
            "nullable": True,
            "coerce": (
                lambda value: None
                if value in ["null", "undefined", "none", "nil"]
                else value
            ),
        },
        "name": {"type": "string"},
        "package": {"type": "string"},
        "s3": {"type": "integer"},
        "yaml": {"type": "string"},
        "url": {"type": "string"},
        "root": {"type": "string",},  # deprecated
    }

    v = Validator(params_schema, allow_unknown=True)
    if not v.validate(non_empty_data):
        raise ValidationError(v.errors)

    # return validated data, including coerced values
    return v.document
