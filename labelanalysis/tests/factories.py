import factory

from core.tests.factories import CommitFactory
from labelanalysis.models import LabelAnalysisRequest


class LabelAnalysisRequestFactory(factory.Factory):
    class Meta:
        model = LabelAnalysisRequest

    base_commit = factory.SubFactory(CommitFactory)
    head_commit = factory.SubFactory(CommitFactory)
    state_id = 1
