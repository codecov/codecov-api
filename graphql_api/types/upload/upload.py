from typing import Optional

from ariadne import ObjectType
from asgiref.sync import sync_to_async
from django.urls import reverse
from graphql import GraphQLResolveInfo
from shared.django_apps.utils.services import get_short_service_name

from graphql_api.helpers.connection import queryset_to_connection_sync
from graphql_api.types.enums import (
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
def resolve_state(upload: ReportSession, info: GraphQLResolveInfo) -> UploadState:
    if not upload.state:
        return UploadState.ERROR
    return UploadState(upload.state)


@upload_bindable.field("id")
def resolve_id(upload: ReportSession, info: GraphQLResolveInfo) -> Optional[int]:
    return upload.order_number


@upload_bindable.field("uploadType")
def resolve_upload_type(upload: ReportSession, info: GraphQLResolveInfo) -> UploadType:
    return UploadType(upload.upload_type)


@upload_bindable.field("errors")
@sync_to_async
def resolve_errors(report_session: ReportSession, info: GraphQLResolveInfo, **kwargs):
    return queryset_to_connection_sync(list(report_session.errors.all()))


@upload_error_bindable.field("errorCode")
def resolve_error_code(error, info: GraphQLResolveInfo) -> UploadErrorEnum:
    return UploadErrorEnum(error.error_code)


@upload_bindable.field("ciUrl")
@sync_to_async
def resolve_ci_url(upload: ReportSession, info: GraphQLResolveInfo):
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
