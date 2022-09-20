from django.urls import path

from staticanalysis.views import StaticAnalysisSuiteView

urlpatterns = [
    path("analyses", StaticAnalysisSuiteView.as_view(), name="static_analysis_upload"),
]
