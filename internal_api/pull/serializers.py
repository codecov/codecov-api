from rest_framework import serializers

from core.models import Pull, Commit
from codecov_auth.models import Owner
from internal_api.owner.serializers import OwnerSerializer
from internal_api.serializers import TotalsSerializer


class PullSerializer(serializers.ModelSerializer):
    most_recent_commiter = serializers.CharField()
    base_totals = TotalsSerializer()
    head_totals = TotalsSerializer()
    ci_passed = serializers.BooleanField()

    class Meta:
        model = Pull
        fields = (
            'pullid',
            'title',
            'most_recent_commiter',
            'base_totals',
            'head_totals',
            'updatestamp',
            'state',
            'ci_passed'
        )


class PullDetailSerializer(PullSerializer):
    author = OwnerSerializer()

    class Meta:
        model = Pull
        fields = PullSerializer.Meta.fields + ('author',)
