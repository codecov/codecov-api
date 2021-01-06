from dateutil import parser

from django.db.models import QuerySet, Subquery, OuterRef, Q, Count, F, FloatField, Avg, Sum, IntegerField
from django.contrib.postgres.fields import JSONField
from django.db.models.functions import Cast
from django.contrib.postgres.fields.jsonb import KeyTextTransform


class RepositoryQuerySet(QuerySet):
    def viewable_repos(self, owner):
        """
        Filters queryset so that result only includes repos viewable by the
        given owner.
        """
        if owner.is_authenticated:
            return self.filter(
                Q(private=False)
                | Q(author__ownerid=owner.ownerid)
                | Q(repoid__in=owner.permission)
            )
        return self.filter(private=False)

    def exclude_uncovered(self):
        from core.models import Commit
        return self.annotate(
            latest_commit_totals=Subquery(
                Commit.objects.filter(
                    repository_id=OuterRef('repoid'),
                    branch=OuterRef('branch')
                ).order_by('-timestamp').values('totals')[:1]
            )
        ).exclude(latest_commit_totals__isnull=True)

    def with_latest_commit_totals_before(
        self,
        before_date,
        branch_param,
        include_previous_totals=False
    ):
        """
        Annotates queryset with coverage of latest commit totals before cerain date.
        """
        from core.models import Commit

        # Parsing the date given in parameters so we receive a datetime rather than a string
        timestamp = parser.parse(before_date)

        commit_query_set = Commit.objects.filter(
            repository_id=OuterRef('repoid'),
            state=Commit.CommitStates.COMPLETE,
            branch=branch_param or OuterRef("branch"),
            # The __date cast function will case the datetime based timestamp on the commit to a date object that only
            # contains the year, month and day. This allows us to filter through a daily granularity rather than
            # a second granularity since this is the level of granularity we get from other parts of the API.
            timestamp__date__lte=timestamp
        ).order_by('-timestamp')

        queryset = self.annotate(
            latest_commit_totals=Subquery(
                commit_query_set.values("totals")[:1]
            )
        )

        if include_previous_totals:
            queryset = queryset.annotate(
                prev_commit_totals=Subquery(
                    commit_query_set.values("totals")[1:2]
                )
            )
        return queryset

    def with_latest_coverage_change(self):
        """
        Annotates the queryset with the latest "coverage change" (cov of last commit
        made to default branch, minus cov of second-to-last commit made to default
        branch) of each repository. Depends on having called "with_latest_commit_totals_before" with 
        "include_previous_totals=True".
        """
        from core.models import Commit
        return self.annotate(
            latest_coverage=Cast(KeyTextTransform("c", "latest_commit_totals"), output_field=FloatField()),
            second_latest_coverage=Cast(KeyTextTransform("c", "prev_commit_totals"), output_field=FloatField())
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
            sum_hits=Sum(Cast(KeyTextTransform("h", "latest_commit_totals"), output_field=FloatField())),
            sum_lines=Sum(Cast(KeyTextTransform("n", "latest_commit_totals"), output_field=FloatField())),
            sum_partials=Sum(Cast(KeyTextTransform("p", "latest_commit_totals"), output_field=FloatField())),
            sum_misses=Sum(Cast(KeyTextTransform("m", "latest_commit_totals"), output_field=FloatField())),
            average_complexity=Avg(Cast(KeyTextTransform("C", "latest_commit_totals"), output_field=FloatField())),
            weighted_coverage=(
                Sum(Cast(KeyTextTransform("h", "latest_commit_totals"), output_field=FloatField()))
                /
                Sum(Cast(KeyTextTransform("n", "latest_commit_totals"), output_field=FloatField())) * 100
            ),
            # Function to get the weighted coverage change is to calculate the weighted coverage for the previous commit
            # minus the weighted coverage from the current commit
            weighted_coverage_change=(
                Sum(Cast(KeyTextTransform("h", "latest_commit_totals"), output_field=FloatField()))
                /
                Sum(Cast(KeyTextTransform("n", "latest_commit_totals"), output_field=FloatField())) * 100
            ) - (
            Sum(Cast(KeyTextTransform("h", "prev_commit_totals"), output_field=FloatField()))
            /
            Sum(Cast(KeyTextTransform("n", "prev_commit_totals"), output_field=FloatField()))  * 100
            )
        )

    def get_or_create_from_git_repo(self, git_repo, owner):
        from codecov_auth.models import Owner
        repo, created = self.get_or_create(
            author=owner,
            service_id=git_repo.get('service_id') or git_repo.get("id"),
            private=git_repo['private'],
            branch=git_repo.get('branch') or git_repo.get("default_branch") or "master",
            name=git_repo['name']
        )

        # If this is a fork, create the forked repo and save it to the new repo
        if git_repo.get('fork'):
            git_repo_fork = git_repo['fork']['repo']
            git_repo_fork_owner = git_repo['fork']['owner']

            fork_owner, _ = Owner.objects.get_or_create(
                service=owner.service,
                username=git_repo_fork_owner['username'],
                service_id=git_repo_fork_owner['service_id']
            )
            fork, _ = self.get_or_create(
                author=fork_owner,
                service_id=git_repo_fork['service_id'],
                private=git_repo_fork['private'],
                branch=git_repo_fork.get('branch') or git_repo_fork.get("default_branch"),
                name=git_repo_fork['name']
            )
            repo.fork = fork
            repo.save()

        return repo, created
