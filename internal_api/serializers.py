import asyncio
import logging

from rest_framework import serializers
from core.models import Pull, Commit, Repository
from codecov_auth.models import Owner

from archive.services import ReportService
from repo_providers.services import RepoProviderService

log = logging.getLogger(__name__)


class AuthorSerializer(serializers.ModelSerializer):

    username = serializers.CharField()
    email = serializers.CharField()
    name = serializers.CharField()

    class Meta:
        model = Owner
        fields = ('username', 'email', 'name')


class PullSerializer(serializers.ModelSerializer):

    state = serializers.CharField()
    title = serializers.CharField()
    base = serializers.CharField()
    compared_to = serializers.CharField()
    head = serializers.CharField()
    diff = serializers.JSONField()
    flare = serializers.JSONField()

    class Meta:
        model = Pull
        fields = '__all__'


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


class ParentlessCommitSerializer(serializers.ModelSerializer):

    commitid = serializers.CharField()
    timestamp = serializers.DateTimeField()
    updatestamp = serializers.DateTimeField()
    ci_passed = serializers.BooleanField()
    author = AuthorSerializer()
    report = serializers.SerializerMethodField()
    src = serializers.SerializerMethodField()
    repository = serializers.SlugRelatedField(
        read_only=True,
        slug_field='repoid'
    )

    def get_report(self, obj):
        report = ReportService().build_report_from_commit(obj)
        return ReportSerializer(instance=report).data

    def get_src(self, obj):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        log.info("Starting loop %s", loop)
        user = self.context.get("user")
        task = RepoProviderService().get_adapter(user, obj.repository).get_commit_diff(obj.commitid)
        return loop.run_until_complete(task)

    class Meta:
        model = Commit
        fields = (
            'src', 'commitid', 'timestamp', 'updatestamp', 'ci_passed', 'report', 'repository', 'author'
        )


class CommitSerializer(ParentlessCommitSerializer):

    parent = ParentlessCommitSerializer(source='parent_commit')

    class Meta:
        model = Commit
        fields = (
            'src', 'commitid', 'timestamp', 'updatestamp', 'ci_passed',
            'report', 'repository', 'parent', 'author'
        )


class RepoSerializer(serializers.ModelSerializer):
    repoid = serializers.CharField()
    service_id = serializers.CharField()
    name = serializers.CharField()
    private = serializers.BooleanField()
    updatestamp = serializers.DateTimeField()

    class Meta:
        model = Repository
        fields = '__all__'
