from rest_framework import serializers


class LicenseSerializer(serializers.Serializer):
    trial = serializers.BooleanField(source="is_trial")
    url = serializers.CharField()
    users = serializers.IntegerField(source="number_allowed_users")
    repos = serializers.IntegerField(source="number_allowed_repos")
    expires_at = serializers.DateTimeField(source="expires")
    pr_billing = serializers.BooleanField(source="is_pr_billing")
