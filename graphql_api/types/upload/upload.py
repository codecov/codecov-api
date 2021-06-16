from ariadne import ObjectType
from asgiref.sync import sync_to_async
from datetime import datetime

from utils.services import get_short_service_name

upload_bindable = ObjectType("Upload")


@upload_bindable.field("state")
def resolve_session_type(upload_with_commit, info):
    return upload_with_commit["upload"].state


@upload_bindable.field("provider")
def resolve_session_type(upload_with_commit, info):
    return upload_with_commit["upload"].provider


@upload_bindable.field("sessionType")
def resolve_session_type(upload_with_commit, info):
    return upload_with_commit["upload"].session_type.value


@upload_bindable.field("createdAt")
def resolve_state(upload_with_commit, info):
    if upload_with_commit["upload"]:
        return datetime.utcfromtimestamp(upload_with_commit["upload"].time)


@upload_bindable.field("downloadUrl")
@sync_to_async
def resolve_download_url(upload_with_commit, info):
    upload = upload_with_commit["upload"]
    commit = upload_with_commit["commit"]
    repository = commit.repository
    owner = repository.author
    short_service = get_short_service_name(owner.service)
    prefix = f"/api/{short_service}/{owner.username}/{repository.name}/download/build"
    return f"{prefix}?path={upload.archive}"


@upload_bindable.field("ciUrl")
def resolve_ci_url(upload, info):
    upload = upload_with_commit["upload"]
    commit = upload_with_commit["commit"]
    repository = commit.repository
    owner = repository.author
    short_service = get_short_service_name(owner.service)
    if not upload.provider:
        return
    data = {
        "service_short": short_service,
        "owner": owner,
        "repo": repository,
        "commit": commit.commitid,
        "session": {"build": upload.build, "job": upload.job},
    }
    return ci[provider]["build_url"].format(**data)
