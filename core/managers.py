from dateutil import parser

from django.db.models import QuerySet, Subquery, OuterRef, Q, Count, F, FloatField, Avg, Sum
from django.db.models.functions import Cast
from django.contrib.postgres.fields.jsonb import KeyTextTransform


class RepositoryQuerySet(QuerySet):
    def viewable_repos(self, owner):
        """
        Filters queryset so that result only includes repos viewable by the
        given owner.
        """
        return self.filter(
            Q(private=False)
            | Q(author__ownerid=owner.ownerid)
            | Q(repoid__in=owner.permission)
        )

    def exclude_uncovered(self):
        from core.models import Commit
        return self.annotate(
            totals=Subquery(
                Commit.objects.filter(
                    repository_id=OuterRef('repoid'),
                    branch=OuterRef('branch')
                ).order_by('-timestamp').values('totals')[:1]
            )
        ).exclude(totals__isnull=True)

    def with_latest_commit_before(self, before_date, branch_param):
        """
        Annotates queryset with coverage of latest commit value. Primarily useful for
        sorting by coverage via API query parameters.
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
        ).order_by('-timestamp').annotate(
            # Annotate all the database fields to better known named fields
            coverage=Cast(KeyTextTransform("c", "totals"), output_field=FloatField()),
            lines=Cast(KeyTextTransform("n", "totals"), output_field=FloatField()),
            hits=Cast(KeyTextTransform("h", "totals"), output_field=FloatField()),
            misses=Cast(KeyTextTransform("m", "totals"), output_field=FloatField()),
            partials=Cast(KeyTextTransform("p", "totals"), output_field=FloatField()),
            complexity=Cast(KeyTextTransform("C", "totals"), output_field=FloatField())
        )

        # We annotate a bunch of data from the latest commit to the repository to enable two things:
        # - First we add the latest commit id to the repository so we can more easily fetch it in the serializer. This
        # is still very slow since we keep the n+1 problem, but it will be easier to optimize later if the logic is not
        # duplicated between the manager and serializer.
        # - Second, we add all the specific totals fields we want to be able to sort with directly on the repository.
        # This will enabled the ordering using rest framework and will not cause errors due to django trying to access
        # structured fields.
        return self.annotate(
            latest_commitid=Subquery(
                commit_query_set.values("commitid")[:1]
            ),
            coverage=Subquery(
                commit_query_set.values("coverage")[:1],
                output_field=FloatField()
            ),
            lines=Subquery(
                commit_query_set.values("lines")[:1],
                output_field=FloatField() # These have to be float fields so we don't introduce integer math
            ),
            # Useful for calculating weighted coverage change
            prev_lines=Subquery(
                commit_query_set.values("lines")[1:2],
                output_field=FloatField()
            ),
            hits=Subquery(
                commit_query_set.values("hits")[:1],
                output_field=FloatField()
            ),
            # Useful for calculating weighted coverage change
            prev_hits=Subquery(
                commit_query_set.values("hits")[1:2],
                output_field=FloatField()
            ),
            partials=Subquery(
                commit_query_set.values("partials")[:1],
                output_field=FloatField()
            ),
            misses=Subquery(
                commit_query_set.values("misses")[:1],
                output_field=FloatField()
            ),
            complexity=Subquery(
                commit_query_set.values("complexity")[:1],
                output_field=FloatField()
            )
        )

    def with_total_commit_count(self):
        """
        Annotates queryset with total number of commits made to each repository.
        """
        return self.annotate(total_commit_count=Count('commits'))

    def with_latest_coverage_change(self):
        """
        Annotates the queryset with the latest "coverage change" (cov of last commit
        made to default branch, minus cov of second-to-last commit made to default
        branch) of each repository.
        """
        from core.models import Commit
        return self.annotate(
            latest_coverage=Subquery(
                Commit.objects.filter(
                    repository_id=OuterRef('repoid'),
                    branch=OuterRef('branch')
                ).annotate(
                    coverage=Cast(KeyTextTransform("c", "totals"), output_field=FloatField())
                ).order_by('-timestamp').values("coverage")[:1],
                output_field=FloatField()
            ),
            second_latest_coverage=Subquery(
                Commit.objects.filter(
                    repository_id=OuterRef('repoid'),
                    branch=OuterRef('branch')
                ).annotate(
                    coverage=Cast(KeyTextTransform("c", "totals"), output_field=FloatField())
                ).order_by('-timestamp').values("coverage")[1:2],
                output_field=FloatField()
            )
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
            sum_lines=Sum("lines"),
            sum_hits=Sum("hits"),
            sum_partials=Sum("partials"),
            sum_misses=Sum("misses"),
            weighted_coverage=(Sum("hits") / Sum("lines")) * 100,
            average_complexity=Avg("complexity"),
            # Function to get the weighted coverage change is to calculate the weighted coverage for the previous commit
            # minus the weighted coverage from the current commit
            weighted_coverage_change=(Sum("hits") / Sum("lines")) * 100 - (Sum("prev_hits") / Sum("prev_lines")) * 100,
        )
