from django.urls import path

from staticanalysis.views import StaticAnalysisSuiteView

urlpatterns = [
    path(
        "staticanalyses",
        StaticAnalysisSuiteView.as_view(),
        name="staticanalyses-list",
    ),
    path(
        "staticanalyses/<uuid:external_id>/finish",
        StaticAnalysisSuiteView.as_view(),
        name="staticanalyses-finish",
    ),
]
