from django.urls import path

from labelanalysis.views import (
    LabelAnalysisRequestCreateView,
    LabelAnalysisRequestDetailView,
)

urlpatterns = [
    path(
        "labels-analysis",
        LabelAnalysisRequestCreateView.as_view(),
        name="create_label_analysis",
    ),
    path(
        "labels-analysis/<uuid:external_id>",
        LabelAnalysisRequestDetailView.as_view(),
        name="view_label_analysis",
    ),
]
