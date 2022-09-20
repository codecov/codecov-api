from rest_framework import serializers

from api.public.v2.owner.serializers import OwnerSerializer
from api.shared.commit.serializers import CommitTotalsSerializer
from core.models import Pull, PullStates


class PullSerializer(serializers.ModelSerializer):
    pullid = serializers.IntegerField(label="pull ID number")
    title = serializers.CharField(label="title of the pull")
    base_totals = CommitTotalsSerializer(label="coverage totals of base commit")
    head_totals = CommitTotalsSerializer(label="coverage totals of head commit")
    updatestamp = serializers.DateTimeField(label="last updated timestamp")
    state = serializers.ChoiceField(
        label="state of the pull", choices=PullStates.choices
    )
    ci_passed = serializers.BooleanField(
        label="indicates whether the CI process passed for the head commit of this pull"
    )
    author = OwnerSerializer(label="pull author")

    class Meta:
        model = Pull
        read_only_fields = (
            "pullid",
            "title",
            "base_totals",
            "head_totals",
            "updatestamp",
            "state",
            "ci_passed",
            "author",
        )
        fields = read_only_fields
