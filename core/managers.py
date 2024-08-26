import datetime

from dateutil import parser
from django.db.models import (
    Avg,
    Count,
    F,
    FloatField,
    IntegerField,
    Manager,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Sum,
    Value,
)
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast, Coalesce
from django.utils import timezone


class RepositoryQuerySet(QuerySet):
    def viewable_repos(self, owner):
        """
        Filters queryset so that result only includes repos viewable by the
        given owner.
        """
        filters = Q(private=False)

        if owner is not None:
            filters = filters | Q(author__ownerid=owner.ownerid)
            if owner.permission:
                filters = filters | Q(repoid__in=owner.permission)

        filters &= ~Q(deleted=True)

        return self.filter(filters).exclude(name=None)

    def exclude_uncovered(self):
        """
        Excludes repositories with no latest-commit val. Requires calling
        'with_latest_commit_totals_before' on queryset first.
        """
        return self.exclude(latest_commit_totals__isnull=True)

    def with_recent_coverage(self) -> QuerySet:
        """
        Annotates queryset with recent commit totals from latest commit
        that is more than an hour old.  This ensures that the coverage totals
        are not changing as the most recent commit is uploading coverage
        reports.
        """
        from core.models import Commit

        timestamp = timezone.now() - timezone.timedelta(hours=1)

        commits_queryset = Commit.objects.filter(
            repository_id=OuterRef("pk"),
            state=Commit.CommitStates.COMPLETE,
            branch=OuterRef("branch"),
            timestamp__lte=timestamp,
        ).order_by("-timestamp")

        coverage = Cast(
            KeyTextTransform("c", "recent_commit_totals"),
            output_field=FloatField(),
        )
        hits = Cast(
            KeyTextTransform("h", "recent_commit_totals"),
            output_field=IntegerField(),
        )
        misses = Cast(
            KeyTextTransform("m", "recent_commit_totals"),
            output_field=IntegerField(),
        )
        lines = Cast(
            KeyTextTransform("n", "recent_commit_totals"),
            output_field=IntegerField(),
        )

        return self.annotate(
            recent_commit_totals=Subquery(commits_queryset.values("totals")[:1]),
            coverage_sha=Subquery(commits_queryset.values("commitid")[:1]),
            recent_coverage=coverage,
            coverage=Coalesce(
                coverage,
                Value(-1),
                output_field=FloatField(),
            ),
            hits=hits,
            misses=misses,
            lines=lines,
        )

    def with_latest_commit_totals_before(
        self, before_date, branch, include_previous_totals=False
    ):
        """
        Annotates queryset with coverage of latest commit totals before cerain date.
        """
        from core.models import Commit

        # Parsing the date given in parameters so we receive a datetime rather than a string
        timestamp = parser.parse(before_date)

        commit_query_set = Commit.objects.filter(
            repository_id=OuterRef("repoid"),
            state=Commit.CommitStates.COMPLETE,
            branch=branch or OuterRef("branch"),
            # The __date cast function will case the datetime based timestamp on the commit to a date object that only
            # contains the year, month and day. This allows us to filter through a daily granularity rather than
            # a second granularity since this is the level of granularity we get from other parts of the API.
            timestamp__date__lte=timestamp,
        ).order_by("-timestamp")

        queryset = self.annotate(
            latest_commit_totals=Subquery(commit_query_set.values("totals")[:1])
        )

        if include_previous_totals:
            queryset = queryset.annotate(
                prev_commit_totals=Subquery(commit_query_set.values("totals")[1:2])
            )
        return queryset

    def with_latest_coverage_change(self):
        """
        Annotates the queryset with the latest "coverage change" (cov of last commit
        made to default branch, minus cov of second-to-last commit made to default
        branch) of each repository. Depends on having called "with_latest_commit_totals_before" with
        "include_previous_totals=True".
        """
        from core.models import Commit  # noqa: F401

        return self.annotate(
            latest_coverage=Cast(
                KeyTextTransform("c", "latest_commit_totals"), output_field=FloatField()
            ),
            second_latest_coverage=Cast(
                KeyTextTransform("c", "prev_commit_totals"), output_field=FloatField()
            ),
        ).annotate(
            latest_coverage_change=F("latest_coverage") - F("second_latest_coverage")
        )

    def get_aggregated_coverage(self):
        """
        Adds group_bys in the queryset to aggregate the repository coverage totals together to access
        statistics on an organization repositories. Requires `with_latest_coverage_change` and
        `with_latest_commit_before` to have been executed beforehand.

        Does not return a queryset and instead returns the aggregated values, fetched from the database.
        """

        return self.aggregate(
            repo_count=Count("repoid"),
            sum_hits=Sum(
                Cast(
                    KeyTextTransform("h", "latest_commit_totals"),
                    output_field=FloatField(),
                )
            ),
            sum_lines=Sum(
                Cast(
                    KeyTextTransform("n", "latest_commit_totals"),
                    output_field=FloatField(),
                )
            ),
            sum_partials=Sum(
                Cast(
                    KeyTextTransform("p", "latest_commit_totals"),
                    output_field=FloatField(),
                )
            ),
            sum_misses=Sum(
                Cast(
                    KeyTextTransform("m", "latest_commit_totals"),
                    output_field=FloatField(),
                )
            ),
            average_complexity=Avg(
                Cast(
                    KeyTextTransform("C", "latest_commit_totals"),
                    output_field=FloatField(),
                )
            ),
            weighted_coverage=(
                Sum(
                    Cast(
                        KeyTextTransform("h", "latest_commit_totals"),
                        output_field=FloatField(),
                    )
                )
                / Sum(
                    Cast(
                        KeyTextTransform("n", "latest_commit_totals"),
                        output_field=FloatField(),
                    )
                )
                * 100
            ),
            # Function to get the weighted coverage change is to calculate the weighted coverage for the previous commit
            # minus the weighted coverage from the current commit
            weighted_coverage_change=(
                Sum(
                    Cast(
                        KeyTextTransform("h", "latest_commit_totals"),
                        output_field=FloatField(),
                    )
                )
                / Sum(
                    Cast(
                        KeyTextTransform("n", "latest_commit_totals"),
                        output_field=FloatField(),
                    )
                )
                * 100
            )
            - (
                Sum(
                    Cast(
                        KeyTextTransform("h", "prev_commit_totals"),
                        output_field=FloatField(),
                    )
                )
                / Sum(
                    Cast(
                        KeyTextTransform("n", "prev_commit_totals"),
                        output_field=FloatField(),
                    )
                )
                * 100
            ),
        )

    def with_latest_commit_at(self):
        """
        Annotates queryset with latest commit based on a Repository. We annotate:
        - true_latest_commit_at as the real value from the table
        - latest_commit_at as the true_coverage except NULL are transformed to 1/1/1900
        This make sure when we order the repo with no commit appears last.
        """
        from core.models import Commit

        latest_commit_at = Subquery(
            Commit.objects.filter(repository_id=OuterRef("pk"))
            .order_by("-timestamp")
            .values("timestamp")[:1]
        )
        return self.annotate(
            true_latest_commit_at=latest_commit_at,
            latest_commit_at=Coalesce(
                latest_commit_at, Value(datetime.datetime(1900, 1, 1))
            ),
        )

    def with_oldest_commit_at(self):
        """
        Annotates the queryset with the oldest commit timestamp.
        """
        from core.models import Commit

        commits = Commit.objects.filter(repository_id=OuterRef("pk")).order_by(
            "timestamp"
        )
        return self.annotate(
            oldest_commit_at=Subquery(commits.values("timestamp")[:1]),
        )

    def get_or_create_from_git_repo(self, git_repo, owner):
        from codecov_auth.models import Owner

        repo, created = self.get_or_create(
            author=owner,
            service_id=git_repo.get("service_id") or git_repo.get("id"),
            private=git_repo["private"],
            branch=git_repo.get("branch") or git_repo.get("default_branch") or "main",
            name=git_repo["name"],
        )

        # If this is a fork, create the forked repo and save it to the new repo.
        # Depending on the source of this data, 'fork' may either be a boolean or a dict
        # containing data of the fork. In the case it is a boolean, the forked repo's data
        # is contained in the 'parent' field.
        fork = git_repo.get("fork")
        if fork:
            if isinstance(fork, dict):
                git_repo_fork = git_repo["fork"]["repo"]
                git_repo_fork_owner = git_repo["fork"]["owner"]

            elif isinstance(fork, bool):
                # This is supposed to indicate that the repo json comes
                # in the form of a github API repo
                # (https://docs.github.com/en/rest/reference/repos#get-a-repository)
                # but sometimes this will unexpectedly be missing the 'parent' field,
                # which contains information about a fork's parent. So we check again
                # below.
                parent = git_repo.get("parent")
                if parent:
                    git_repo_fork_owner = {
                        "service_id": parent["owner"]["id"],
                        "username": parent["owner"]["login"],
                    }
                    git_repo_fork = {
                        "service_id": parent["id"],
                        "private": parent["private"],
                        "language": parent["language"],
                        "branch": parent["default_branch"],
                        "name": parent["name"],
                    }
                else:
                    # If the parent data doesn't exist, there is nothing else to do.
                    return repo, created

            fork_owner, _ = Owner.objects.get_or_create(
                service=owner.service,
                username=git_repo_fork_owner["username"],
                service_id=git_repo_fork_owner["service_id"],
                defaults={"createstamp": timezone.now()},
            )
            fork, _ = self.get_or_create(
                author=fork_owner,
                service_id=git_repo_fork["service_id"],
                private=git_repo_fork["private"],
                branch=git_repo_fork.get("branch")
                or git_repo_fork.get("default_branch"),
                name=git_repo_fork["name"],
            )
            repo.fork = fork
            repo.save()

        return repo, created


# We cannot use `QuerySet.as_manager()` since it relies on the `inspect` module and will
# not play nicely with Cython (which we use for self-hosted):
# https://cython.readthedocs.io/en/latest/src/userguide/limitations.html#inspect-support
class RepositoryManager(Manager):
    def get_queryset(self):
        return RepositoryQuerySet(self.model, using=self._db)

    def viewable_repos(self, *args, **kwargs):
        return self.get_queryset().viewable_repos(*args, **kwargs)

    def get_or_create_from_git_repo(self, *args, **kwargs):
        return self.get_queryset().get_or_create_from_git_repo(*args, **kwargs)
