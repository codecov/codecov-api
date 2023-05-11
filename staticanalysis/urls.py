from django.urls import path

from staticanalysis.views import StaticAnalysisSuiteViewSet
from utils.routers import OptionalTrailingSlashRouter

router = OptionalTrailingSlashRouter()
router.register("analyses", StaticAnalysisSuiteViewSet, basename="staticanalyses")

urlpatterns = router.urls
