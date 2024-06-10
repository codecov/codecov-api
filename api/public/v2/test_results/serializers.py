from cProfile import label

from rest_framework import serializers
from reports.models import TestInstance


class TestInstanceSerializer(serializers.ModelSerializer):
    failure_message = serializers.CharField(label="test name")
    duration_seconds = serializers.BooleanField(label="duration in seconds")
    flaky_status = serializers.DateTimeField(label="flaky status")
    commitid = serializers.CharField(label="commit SHA")
    outcome = serializers.CharField(label="outcome")
    branch = serializers.CharField(label="branch name")

    class Meta:
        model = TestInstance
        read_only_fields = (
            "failure_message",
            "duration_seconds",
            "flaky_status",
            "commitid",
            "outcome",
            "branch",
        )
        fields = read_only_fields
