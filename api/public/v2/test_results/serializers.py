from django.db.models import Count, Q
from rest_framework import serializers

from reports.models import TestInstance


class TestInstanceSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(label="id")
    name = serializers.CharField(source="test.name", read_only=True, label="test name")
    test_id = serializers.CharField(label="test id")
    failure_message = serializers.CharField(label="test name")
    duration_seconds = serializers.FloatField(label="duration in seconds")
    commitid = serializers.CharField(label="commit SHA")
    outcome = serializers.CharField(label="outcome")
    branch = serializers.CharField(label="branch name")
    repoid = serializers.IntegerField(label="repo id")
    failure_rate = serializers.SerializerMethodField(label="failure rate")
    commits_where_fail = serializers.ListField(
        source="test.commits_where_fail",
        read_only=True,
        label="commits where test failed",
    )

    def get_failure_rate(self, obj):
        """Calculate the failure rate for a test.
        The failure rate is calculated as:
        number of failed test runs / total number of test runs
        Returns:
            float: A value between 0.0 and 1.0 representing the failure rate
                  0.0 means no failures
                  1.0 means all runs failed
        """
        stats = TestInstance.objects.filter(test=obj.test).aggregate(
            total=Count("id"),
            failures=Count("id", filter=Q(outcome=TestInstance.Outcome.FAILURE.value)),
        )

        total_runs = stats["total"]
        if total_runs == 0:
            return 0.0

        return stats["failures"] / total_runs

    class Meta:
        model = TestInstance
        read_only_fields = (
            "id",
            "test_id",
            "failure_message",
            "duration_seconds",
            "commitid",
            "outcome",
            "branch",
            "repoid",
            "failure_rate",
            "name",
            "commits_where_fail",
        )
        fields = read_only_fields
