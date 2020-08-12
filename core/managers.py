from django.db.models import QuerySet, Subquery, OuterRef, Q, Count, F, FloatField
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

    def with_current_coverage(self):
        """
        Annotates queryset with coverage of latest commit value. Primarily useful for
        sorting by coverage via API query parameters.
        """
        from core.models import Commit
        return self.annotate(
            coverage=Subquery(
                Commit.objects.filter(
                    repository_id=OuterRef('repoid'),
                    branch=OuterRef('branch')
                ).order_by('-timestamp').values('totals__c')[:1]
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
