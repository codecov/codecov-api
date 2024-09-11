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
    failure_rate = serializers.FloatField(
        source="test.failure_rate", read_only=True, label="failure rate"
    )
    commits_where_fail = serializers.ListField(
        source="test.commits_where_fail",
        read_only=True,
        label="commits where test failed",
    )

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
