import json
import logging
from typing import List, Optional

from django.utils.functional import cached_property
from shared.profiling import ProfilingSummaryDataAnalyzer

from core.models import Repository
from profiling.models import ProfilingCommit
from services.archive import ArchiveService

log = logging.getLogger(__name__)


class CriticalFile:
    def __init__(self, name):
        self.name = name


class ProfilingSummary:
    def __init__(self, repo: Repository, commit_sha: Optional[str] = None):
        self.repo = repo
        self.commit_sha = commit_sha

    def latest_profiling_commit(self) -> Optional[ProfilingCommit]:
        """
        Get the most recent summarized ProfilingCommit
        """
        filters = {
            "last_summarized_at__isnull": False,
            "repository_id": self.repo.repoid,
        }

        if self.commit_sha is not None:
            filters["commit_sha"] = self.commit_sha

        return ProfilingCommit.objects.filter(**filters).order_by("-id").first()

    def summary_data(
        self, profiling_commit: ProfilingCommit
    ) -> Optional[ProfilingSummaryDataAnalyzer]:
        """
        Get the profiling summary data for a given profiling commit
        """
        if not profiling_commit.last_summarized_at:
            # no summary available yet for this profiling commit
            return None

        archive_service = ArchiveService(self.repo)
        try:
            data = archive_service.read_file(profiling_commit.summarized_location)
            return ProfilingSummaryDataAnalyzer(json.loads(data))
        except:
            log.error(
                "failed to read summarized profiling data from storage", exc_info=True
            )
            return None

    @cached_property
    def critical_files(self) -> List[CriticalFile]:
        """
        Get the most recent critical files
        """
        profiling_commit = self.latest_profiling_commit()
        if profiling_commit:
            summary = self.summary_data(profiling_commit)
            if summary:
                return [
                    CriticalFile(name)
                    for name in summary.get_critical_files_filenames()
                ]
        return []
