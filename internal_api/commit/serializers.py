import asyncio
import logging

from dataclasses import astuple, asdict

from rest_framework import serializers

from services.archive import ReportService
from services.repo_providers import RepoProviderService
from core.models import Repository, Commit
from internal_api.owner.serializers import OwnerSerializer
from internal_api.serializers import TotalsSerializer

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
    totals = TotalsSerializer()

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
    totals = TotalsSerializer()

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
    totals = TotalsSerializer()

    class Meta:
        model = Commit
        fields = ('src', 'commitid', 'timestamp', 'ci_passed',
                  'report', 'repository', 'parent', 'author', 'totals')


class ReportTotalsSerializer(serializers.Serializer):
    files = serializers.IntegerField()
    lines = serializers.IntegerField()
    hits = serializers.IntegerField()
    misses = serializers.IntegerField()
    partials = serializers.IntegerField()
    coverage = serializers.CharField()
    branches = serializers.IntegerField()
    methods = serializers.IntegerField()
    messages = serializers.IntegerField()
    sessions = serializers.IntegerField()
    complexity = serializers.IntegerField()
    complexity_total = serializers.IntegerField()
    diff = serializers.JSONField()


class ReportFileWithoutLinesSerializer(serializers.Serializer):
    name = serializers.CharField()
    totals = ReportTotalsSerializer()


class ReportFileSerializer(ReportFileWithoutLinesSerializer):
    lines = serializers.SerializerMethodField()

    def get_lines(self, obj):
        return list(self.get_lines_iterator(obj))

    def get_lines_iterator(self, obj):
        for line_number, line in obj.lines:
            sessions = [[s.id, s.coverage, s.branches, s.partials, s.complexity] for s in line.sessions]
            yield (line_number, line.coverage, line.type, sessions, line.messages, line.complexity)


class ReportSerializer(serializers.Serializer):
    totals = serializers.SerializerMethodField()
    files = ReportFileSerializer(source='file_reports', many=True)
    totals = ReportTotalsSerializer()


class ReportWithoutLinesSerializer(serializers.Serializer):
    totals = serializers.SerializerMethodField()
    files = ReportFileWithoutLinesSerializer(source='file_reports', many=True)
    totals = ReportTotalsSerializer()


class FlagSerializer(serializers.Serializer):
    report = ReportSerializer()
    name = serializers.CharField()
