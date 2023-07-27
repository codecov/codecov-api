from typing import Optional

from django.db.models import Prefetch, Q, QuerySet
from django.db.models.functions import Lower, Substr

from core.models import Commit, Pull, Repository
from reports.models import CommitReport, ReportSession


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

    return Commit.objects.filter(id__in=subquery).defer("_report")


def commit_uploads(commit: Commit) -> QuerySet[ReportSession]:
    if not commit.commitreport:
        return ReportSession.objects.none()

    sessions = commit.commitreport.sessions.prefetch_related("flags")

    # # sessions w/ flags and type 'uploaded'
    # uploaded = sessions.filter(upload_type="uploaded")

    # # carry forward flags that do not have an equivalent uploaded flag
    # carried_forward = sessions.filter(upload_type="carriedforward").exclude(
    #     uploadflagmembership__flag_id__in=uploaded.values_list( <------------ FIXME: looks like `flag_id__in` is causing a seq scan in prod
    #         "uploadflagmembership__flag_id", flat=True
    #     )
    # )

    # return (uploaded.prefetch_related("flags")).union(
    #     carried_forward.prefetch_related("flags")
    # )

    return sessions


def repo_commits(
    repository: Repository, filters: Optional[dict] = None
) -> QuerySet[Commit]:
    # prefetch the CommitReport with the ReportLevelTotals and ReportDetails
    prefetch = Prefetch(
        "reports",
        queryset=CommitReport.objects.filter(code=None)
        .select_related("reportleveltotals", "reportdetails")
        .defer("reportdetails___files_array"),
    )

    # We don't select the `report` column here b/c it can be many MBs of JSON
    # and can cause performance issues
    queryset = repository.commits.defer("_report").prefetch_related(prefetch).all()

    # queryset filtering
    filters = filters or {}

    hide_failed_ci = filters.get("hide_failed_ci")
    if hide_failed_ci is True:
        queryset = queryset.filter(ci_passed=True)

    branch_name = filters.get("branch_name")
    if branch_name:
        queryset = queryset.filter(branch=branch_name)

    pull_id = filters.get("pull_id")
    if pull_id:
        queryset = queryset.filter(pullid=pull_id)

    search = filters.get("search")
    if search:
        # search against long sha, short sha and commit message substring
        queryset = queryset.annotate(short_sha=Substr(Lower("commitid"), 1, 7)).filter(
            Q(commitid=search.lower())
            | Q(short_sha=search.lower())
            | Q(message__icontains=search)
        )

    states = filters.get("states")
    if states:
        queryset = queryset.filter(state__in=states)

    # We need `deleted is not true` in order for the query to use the right index.
    queryset = queryset.filter(deleted__isnot=True)
    return queryset
