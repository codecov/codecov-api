import asyncio
import logging

from rest_framework import serializers
# from core.models import Pull, Commit, Repository, Branch
# from codecov_auth.models import Owner

from archive.services import ReportService
from repo_providers.services import RepoProviderService

# log = logging.getLogger(__name__)


# class NestedAuthorSerializer(serializers.ModelSerializer):
#     username = serializers.CharField()
#     email = serializers.CharField()
#     name = serializers.CharField()

#     class Meta:
#         model = Owner
#         fields = ('username', 'email', 'name')


# class RepoSerializer(serializers.ModelSerializer):
#     repoid = serializers.CharField()
#     service_id = serializers.CharField()
#     name = serializers.CharField()
#     private = serializers.BooleanField()
#     updatestamp = serializers.DateTimeField()
#     author = NestedAuthorSerializer()

#     class Meta:
#         model = Repository
#         fields = '__all__'


class ReportFileSerializer(serializers.Serializer):
    name = serializers.CharField()
    lines = serializers.SerializerMethodField()
    totals = serializers.JSONField(source='totals._asdict')

    def get_lines(self, obj):
        return list(self.get_lines_iterator(obj))

    def get_lines_iterator(self, obj):
        for line_number, line in obj.lines:
            coverage, line_type, sessions, messages, complexity = line
            sessions = [list(s) for s in sessions]
            yield (line_number, coverage, line_type, sessions, messages, complexity)


class ReportSerializer(serializers.Serializer):
    totals = serializers.JSONField(source='totals._asdict')
    files = ReportFileSerializer(source='file_reports', many=True)








