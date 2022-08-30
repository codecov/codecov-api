from api.public.v2.commit.serializers import CommitSerializer
from api.shared.compare.serializers import (
    ComparisonSerializer as BaseComparisonSerializer,
)


class ComparisonSerializer(BaseComparisonSerializer):
    commit_uploads = CommitSerializer(many=True, source="upload_commits")
