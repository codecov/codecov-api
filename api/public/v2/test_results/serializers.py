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
        test_instances = TestInstance.objects.filter(test=obj.test)
        total_runs = test_instances.count()
        if total_runs == 0:
            return 0.0
        fail_count = test_instances.filter(outcome=TestInstance.Outcome.FAILURE.value).count()
        return fail_count / total_runs

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
