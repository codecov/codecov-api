from django.urls import path

from labelanalysis.views import LabelAnalysisRequestView

urlpatterns = [
    path(
        "labels-analysis",
        LabelAnalysisRequestView.as_view(),
        name="create_label_analysis",
    ),
    path(
        "labels-analysis/<uuid:external_id>",
        LabelAnalysisRequestView.as_view(),
        name="view_label_analysis",
    ),
]
