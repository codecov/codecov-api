from datetime import datetime

from ariadne import ObjectType

from codecov.db import sync_to_async
from graphql_api.helpers.connection import queryset_to_connection
from graphql_api.types.enums import (
    OrderingDirection,
    UploadErrorEnum,
    UploadState,
    UploadType,
)

upload_bindable = ObjectType("Upload")
upload_bindable.set_alias("flags", "flag_names")

upload_error_bindable = ObjectType("UploadError")

"""
    Note Uploads are called ReportSession in the model, so I'm keeping the argument
    in line with the code vs product name.
"""


@upload_bindable.field("state")
def resolve_state(upload, info):
    return UploadState(upload.state)


@upload_bindable.field("uploadType")
def resolve_upload_type(upload, info):
    return UploadType(upload.upload_type)


@upload_bindable.field("errors")
async def resolve_errors(report_session, info, **kwargs):
    command = info.context["executor"].get_command("upload")
    queryset = await command.get_upload_errors(report_session)
    result = await queryset_to_connection(
        queryset,
        ordering=("updated_at",),
        ordering_direction=OrderingDirection.ASC,
        **kwargs
    )
    return result


@upload_error_bindable.field("errorCode")
def resolve_error_code(error, info):
    return UploadErrorEnum(error.error_code)


@upload_bindable.field("ciUrl")
@sync_to_async
def resolve_ci_url(upload, info):
    return upload.ci_url


@upload_bindable.field("downloadUrl")
def resolve_download_url(upload, info):
    command = info.context["executor"].get_command("upload")
    return command.get_upload_presigned_url(upload)


@upload_bindable.field("name")
def resolve_name(upload, info):
    return upload.name
