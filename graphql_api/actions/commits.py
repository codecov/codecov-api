from django.db.models import Case, QuerySet, Value, When

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

    # just the sessions with flags
    flags_qs = (
        commit.commitreport.sessions.prefetch_related("flags")
        .exclude(flags__id=None)
        # if >1 sessions share a flag name, this selects just the session
        # with upload_type=uploaded (discarding carriedforward rows)
        .distinct("flags")
        .order_by("flags", "-upload_type")
    )

    # just the sessions w/o flags
    nonflags_qs = commit.commitreport.sessions.prefetch_related("flags").filter(
        flags__id=None
    )

    # combined sessions
    return nonflags_qs.union(flags_qs)
