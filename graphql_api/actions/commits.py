from collections import defaultdict
from typing import Optional

from django.db.models import Count, Prefetch, Q, QuerySet
from django.db.models.functions import Lower, Substr
from graphql import GraphQLResolveInfo

from core.models import Commit, Pull, Repository
from graphql_api.types.enums import CommitStatus
from reports.models import CommitReport


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


def load_commit_statuses(
    commit_ids: list[int],
) -> dict[int, dict[CommitReport.ReportType, str]]:
    qs = (
        CommitReport.objects.filter(commit__in=commit_ids)
        .values_list("commit_id", "report_type", "sessions__state")
        .annotate(sessions_count=Count("sessions"))
    )

    grouped: dict[tuple[int, CommitReport.ReportType], dict[str, int]] = defaultdict(
        dict
    )
    for id, report_type, state, count in qs:
        # The above query generates a `LEFT OUTER JOIN` with a proper `GROUP BY`.
        # However, it is also yielding rows with a `NULL` state in case a report does not have any uploads.
        if not report_type or not state:
            continue
        grouped[(id, report_type)][state] = count

    results: dict[int, dict[CommitReport.ReportType, str]] = {
        id: {} for id in commit_ids
    }
    for (id, report_type), states in grouped.items():
        status = CommitStatus.COMPLETED.value
        if states.get("error", 0) > 0:
            status = CommitStatus.ERROR.value
        elif states.get("uploaded", 0) > 0:
            status = CommitStatus.PENDING.value

        results[id][report_type] = status

    return results


def commit_status(
    info: GraphQLResolveInfo, commit: Commit, report_type: CommitReport.ReportType
) -> str | None:
    commit_statuses = info.context.setdefault("commit_statuses", {})
    commit_status = commit_statuses.get(commit.id)
    if commit_status is None:
        updated_statuses = load_commit_statuses([commit.id])
        commit_statuses.update(updated_statuses)
        commit_status = updated_statuses[commit.id]

    return commit_status.get(report_type)


def repo_commits(
    repository: Repository, filters: Optional[dict] = None
) -> QuerySet[Commit]:
    # prefetch the CommitReport with the ReportLevelTotals
    prefetch = Prefetch(
        "reports",
        queryset=CommitReport.objects.coverage_reports()
        .filter(code=None)
        .select_related("reportleveltotals"),
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

    coverage_status = filters.get("coverage_status")

    if coverage_status:
        # FIXME(swatinem):
        # This filter here is insane, it resolves *all* the results in the unbounded queryset,
        # just to check the status, and to then add it as another restricting filter.
        # I’m pretty sure this will completely break the server if anyone actually uses this filter, lol.
        commit_ids = [commit.id for commit in queryset]
        commit_statuses = load_commit_statuses(commit_ids)

        to_be_included = [
            id
            for id, statuses in commit_statuses.items()
            if statuses.get(CommitReport.ReportType.COVERAGE) in coverage_status
        ]
        queryset = queryset.filter(id__in=to_be_included)

    # We need `deleted is not true` in order for the query to use the right index.
    queryset = queryset.filter(deleted__isnot=True)
    return queryset
