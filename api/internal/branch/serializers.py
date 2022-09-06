from rest_framework import serializers

from core.models import Branch


class BranchSerializer(serializers.ModelSerializer):
    name = serializers.CharField()
    most_recent_commiter = serializers.CharField()
    updatestamp = serializers.DateTimeField()

    class Meta:
        model = Branch
        fields = ("name", "most_recent_commiter", "updatestamp")
