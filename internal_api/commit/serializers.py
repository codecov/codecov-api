from rest_framework import serializers
from .models import Commit
from internal_api.repo.models import Repository
from codecov_auth.models import Owner


class CommitAuthorSerializer(serializers.ModelSerializer):
    username = serializers.CharField()
    email = serializers.CharField()
    name = serializers.CharField()

    class Meta:
        model = Owner
        fields = ('username', 'email', 'name')

class CommitRepoSerializer(serializers.ModelSerializer):
    repoid = serializers.CharField()
    service_id = serializers.CharField()
    name = serializers.CharField()
    private = serializers.BooleanField()
    updatestamp = serializers.DateTimeField()

    class Meta:
        model = Repository
        fields = '__all__'

class ShortParentlessCommitSerializer(serializers.ModelSerializer):
    commitid = serializers.CharField()
    timestamp = serializers.DateTimeField()
    updatestamp = serializers.DateTimeField()
    ci_passed = serializers.BooleanField()
    author = CommitAuthorSerializer()
    repository = CommitRepoSerializer()
    branch = serializers.CharField()
    totals = serializers.JSONField()

    class Meta:
        model = Commit
        fields = (
            'commitid', 'timestamp', 'updatestamp', 'ci_passed', 'repository', 'author', 'message', 'branch', 'totals'
        )

class ParentlessCommitSerializer(ShortParentlessCommitSerializer):
    # report = serializers.SerializerMethodField()
    src = serializers.SerializerMethodField()

    # def get_report(self, obj):
    #     log.info("Prep - Doiing report")
    #     report = ReportService().build_report_from_commit(obj)
    #     return ReportSerializer(instance=report).data

    def get_src(self, obj):
        loop = asyncio.get_event_loop()
        user = self.context.get("user")
        task = RepoProviderService().get_adapter(user, obj.repository).get_commit_diff(obj.commitid)
        return loop.run_until_complete(task)

    class Meta:
        model = Commit
        fields = (
            'src', 'commitid', 'timestamp', 'updatestamp', 'ci_passed', 'repository', 'author', 'message'
        )


class CommitSerializer(ParentlessCommitSerializer):
    parent = ParentlessCommitSerializer(source='parent_commit')

    class Meta:
        model = Commit
        fields = (
            'src', 'commitid', 'timestamp', 'updatestamp', 'ci_passed',
            'report', 'repository', 'parent', 'author'
        )

