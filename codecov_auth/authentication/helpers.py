import re
from typing import NamedTuple

from django.http import HttpRequest


class UploadInfo(NamedTuple):
    service: str
    encoded_slug: str
    commitid: str | None


def get_upload_info_from_request_path(request: HttpRequest) -> UploadInfo | None:
    path_info = request.get_full_path_info()
    # The repo part comes from https://stackoverflow.com/a/22312124
    upload_views_prefix_regex = (
        r"\/upload\/(\w+)\/([\w\.@:_/\-~]+)\/commits(?:\/([a-f0-9]{40}))?"
    )
    match = re.search(upload_views_prefix_regex, path_info)

    if match is None:
        return None

    service = match.group(1)
    encoded_slug = match.group(2)
    commitid = match.group(3)

    return UploadInfo(service, encoded_slug, commitid)
