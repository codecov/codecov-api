import asyncio
import logging

from rest_framework import serializers

from services.archive import ReportService
from services.repo_providers import RepoProviderService
from core.models import Repository, Commit
from internal_api.owner.serializers import OwnerSerializer

log = logging.getLogger(__name__)


class CommitRepoSerializer(serializers.ModelSerializer):
    repoid = serializers.IntegerField()
    name = serializers.CharField()
    updatestamp = serializers.DateTimeField()

    class Meta:
        model = Repository
        fields = ('repoid', 'name', 'updatestamp')


class CommitSerializer(serializers.ModelSerializer):
    author = OwnerSerializer()
    repository = CommitRepoSerializer()

    class Meta:
        model = Commit
        fields = (
            'commitid',
            'message',
            'timestamp',
            'ci_passed',
            'author',
            'repository',
            'branch',
            'totals',
            'state',
        )


class CommitWithReportSerializer(CommitSerializer):
    report = serializers.SerializerMethodField()

    def get_report(self, obj):
        report = ReportService().build_report_from_commit(obj)
        return ReportSerializer(instance=report).data

    class Meta:
        model = Commit
        fields = ('report', 'commitid', 'timestamp',
                  'ci_passed', 'repository', 'author', 'message')


class CommitWithFileLevelReportSerializer(CommitSerializer):
    report = serializers.SerializerMethodField()

    def get_report(self, obj):
        report = ReportService().build_report_from_commit(obj)
        return ReportWithoutLinesSerializer(instance=report).data

    class Meta:
        model = Commit
        fields = ('report', 'commitid', 'timestamp',
                  'ci_passed', 'repository', 'author', 'message')


class CommitWithSrcSerializer(CommitWithReportSerializer):
    src = serializers.SerializerMethodField()

    def get_src(self, obj):
        loop = asyncio.get_event_loop()
        user = self.context.get("user")
        task = RepoProviderService().get_adapter(
            user, obj.repository).get_commit_diff(obj.commitid)
        return loop.run_until_complete(task)

    class Meta:
        model = Commit
        fields = ('src', 'report', 'commitid', 'timestamp', 'ci_passed',
                  'repository', 'branch', 'author', 'totals', 'message')


class CommitWithParentSerializer(CommitWithSrcSerializer):
    parent = CommitWithSrcSerializer(source='parent_commit')

    class Meta:
        model = Commit
        fields = ('src', 'commitid', 'timestamp', 'ci_passed',
                  'report', 'repository', 'parent', 'author')


class ReportFileWithoutLinesSerializer(serializers.Serializer):
    name = serializers.CharField()
    totals = serializers.JSONField(source='totals._asdict')


class ReportFileSerializer(ReportFileWithoutLinesSerializer):
    lines = serializers.SerializerMethodField()

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


class ReportWithoutLinesSerializer(serializers.Serializer):
    totals = serializers.JSONField(source='totals._asdict')
    files = ReportFileWithoutLinesSerializer(source='file_reports', many=True)


class FlagSerializer(serializers.Serializer):
    report = ReportSerializer()
    name = serializers.CharField()
