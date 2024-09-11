from typing import Optional

from ariadne import ObjectType
from django.urls import reverse
from shared.django_apps.utils.services import get_short_service_name

from codecov.db import sync_to_async
from graphql_api.helpers.connection import queryset_to_connection
from graphql_api.types.enums import (
    OrderingDirection,
    UploadErrorEnum,
    UploadState,
    UploadType,
)
from reports.models import ReportSession

upload_bindable = ObjectType("Upload")
upload_bindable.set_alias("flags", "flag_names")

upload_error_bindable = ObjectType("UploadError")

"""
    Note Uploads are called ReportSession in the model, so I'm keeping the argument
    in line with the code vs product name.
"""


@upload_bindable.field("state")
def resolve_state(upload, info):
    if not upload.state:
        return UploadState.ERROR
    return UploadState(upload.state)


@upload_bindable.field("id")
def resolve_id(upload: ReportSession, info) -> Optional[int]:
    return upload.order_number


@upload_bindable.field("uploadType")
def resolve_upload_type(upload, info) -> UploadType:
    return UploadType(upload.upload_type)


@upload_bindable.field("errors")
async def resolve_errors(report_session, info, **kwargs):
    command = info.context["executor"].get_command("upload")
    queryset = await command.get_upload_errors(report_session)
    result = await queryset_to_connection(
        queryset,
        ordering=("updated_at",),
        ordering_direction=OrderingDirection.ASC,
        **kwargs,
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
@sync_to_async
def resolve_download_url(upload: ReportSession, info) -> str:
    request = info.context["request"]
    repository = upload.report.commit.repository
    download_url = (
        reverse(
            "upload-download",
            kwargs={
                "service": get_short_service_name(repository.author.service),
                "owner_username": repository.author.username,
                "repo_name": repository.name,
            },
        )
        + f"?path={upload.storage_path}"
    )
    download_absolute_uri = request.build_absolute_uri(download_url)
    return download_absolute_uri.replace("http", "https", 1)


@upload_bindable.field("name")
def resolve_name(upload, info):
    return upload.name
