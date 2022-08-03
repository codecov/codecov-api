from api.shared.compare.serializers import (
    ComparisonSerializer as BaseComparisonSerializer,
)

from ..commit.serializers import CommitSerializer


class ComparisonSerializer(BaseComparisonSerializer):
    commit_uploads = CommitSerializer(many=True, source="upload_commits")
