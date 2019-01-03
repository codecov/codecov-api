from rest_framework import serializers
from core.models import Pull, Commit, Repository
from archive.services import get_session_report


class PullSerializer(serializers.Serializer):

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


class CommitSerializer(serializers.Serializer):

    commitid = serializers.CharField()
    timestamp = serializers.DateTimeField()
    updatestamp = serializers.DateTimeField()
    ci_passed = serializers.BooleanField()
    totals = serializers.JSONField()
    report = serializers.JSONField()
    repository = serializers.SlugRelatedField(
        read_only=True,
        slug_field='repoid'
    )
    sessions = serializers.SerializerMethodField()

    def get_sessions(self, obj):
        res = []
        for sess in obj.sessions:
            sess['content'] = get_session_report(sess)
            del sess['a']
            res.append(sess)
        return res

    class Meta:
        model = Commit
        fields = '__all__'


class CommitSessionSerializer(serializers.Serializer):
    pass


class RepoSerializer(serializers.Serializer):
    repoid = serializers.CharField()
    service_id = serializers.CharField()
    name = serializers.CharField()
    private = serializers.BooleanField()
    updatestamp = serializers.DateTimeField()

    class Meta:
        model = Repository
        fields = '__all__'
