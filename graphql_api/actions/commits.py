from django.db.models import QuerySet

from core.models import Commit, Pull
from reports.models import ReportSession


def pull_commits(pull: Pull) -> QuerySet[Commit]:
    subquery = (
        Commit.objects.filter(
            pullid=pull.pullid,
            repository_id=pull.repository_id,
        )
        # Can't use `exclude(deleted=True)` here since that results in a
        # `not (deleted and deleted is not null)` condition.
        # We need `deleted is not true` in order for the query to use the right index.
        .filter(deleted__isnot=True)
    )

    return Commit.objects.filter(id__in=subquery).defer("report")


def commit_uploads(commit: Commit) -> QuerySet[ReportSession]:
    if not commit.commitreport:
        return ReportSession.objects.none()

    sessions = commit.commitreport.sessions.prefetch_related("flags")

    # sessions w/ flags and type uploaded
    flags_uploaded = sessions.exclude(flags__id=None).filter(upload_type="uploaded")

    # carry forward flags that do not have an equivalent uploaded flag
    flags_carried_forward = (
        sessions.exclude(flags__id=None)
        .filter(upload_type="carriedforward")
        .exclude(flags__id__in=flags_uploaded.values_list("flags__id", flat=True))
    )

    # sessions w/o flags
    flagless = sessions.filter(flags__id=None)

    # combined sessions
    return flags_uploaded.union(flags_carried_forward).union(flagless).order_by("id")
