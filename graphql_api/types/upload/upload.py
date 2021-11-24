from datetime import datetime

from ariadne import ObjectType
from asgiref.sync import sync_to_async

from graphql_api.helpers.connection import queryset_to_connection
from graphql_api.types.enums import OrderingDirection

upload_bindable = ObjectType("Upload")
upload_bindable.set_alias("flags", "flag_names")

upload_error_bindable = ObjectType("UploadError")

"""
    Note Uploads are called ReportSession in the model, so I'm keeping the argument
    in line with the code vs product name.
"""


@upload_bindable.field("errors")
async def resolve_errors(report_session, info, **kwargs):
    command = info.context["executor"].get_command("upload")
    queryset = await command.get_upload_errors(report_session)
    result = await queryset_to_connection(
        queryset,
        ordering="updated_at",
        ordering_direction=OrderingDirection.ASC,
        **kwargs
    )
    return result
