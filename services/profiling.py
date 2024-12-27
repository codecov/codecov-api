import json
import logging
from typing import List, Optional

import regex
import shared.reports.api_report_service as report_service
from django.utils.functional import cached_property
from shared.api_archive.archive import ArchiveService
from shared.profiling import ProfilingSummaryDataAnalyzer
from shared.yaml import UserYaml

from core.models import Commit, Repository
from profiling.models import ProfilingCommit

log = logging.getLogger(__name__)


class CriticalFile:
    def __init__(self, name: str) -> None:
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
        except Exception:
            log.error(
                "failed to read summarized profiling data from storage", exc_info=True
            )
            return None

    def _get_critical_files_from_yaml(
        self, profiling_commit: Optional[ProfilingCommit] = None
    ) -> List[str]:
        """
        Get a list of files present in the commit report that are also marked as critical in the repo yaml (under profiling.critical_files_paths)
        """
        # We need a reference to some commit. Preference given to self.commit_sha
        if (
            profiling_commit is None or profiling_commit.commit_sha is None
        ) and self.commit_sha is None:
            return []
        repo_yaml = UserYaml.get_final_yaml(
            owner_yaml=self.repo.author.yaml,
            repo_yaml=self.repo.yaml,
            ownerid=self.repo.author.ownerid,
        )
        if not repo_yaml.get("profiling") or not repo_yaml["profiling"].get(
            "critical_files_paths"
        ):
            return []

        commit_sha = None
        if self.commit_sha:
            commit_sha = self.commit_sha
        elif profiling_commit:
            commit_sha = profiling_commit.commit_sha

        commit = Commit.objects.get(commitid=commit_sha)
        report = report_service.build_report_from_commit(commit)
        if report is None:
            return []
        critical_files_paths = repo_yaml["profiling"]["critical_files_paths"]
        compiled_files_paths = [regex.compile(path) for path in critical_files_paths]
        user_defined_critical_files = [
            file
            for file in report.files
            if any(
                (
                    regex.match(regex_patt, file, timeout=2)
                    for regex_patt in compiled_files_paths
                )
            )
        ]
        return user_defined_critical_files

    @cached_property
    def critical_files(self) -> List[CriticalFile]:
        """
        Get the most recent critical files.
        Critical files comes from 2 sources:
            1. critical files from summary_data (e.g. actually detected by impact analysis)
            2. critical files that match paths defined in the user YAML
        """
        profiling_commit = self.latest_profiling_commit()
        if profiling_commit:
            summary = self.summary_data(profiling_commit)
            critical_files_from_profiling = set()
            if summary:
                critical_files_from_profiling = set(
                    summary.get_critical_files_filenames()
                )
            critical_files_from_yaml = set(
                self._get_critical_files_from_yaml(profiling_commit)
            )
            all_critical_files = list(
                critical_files_from_profiling | critical_files_from_yaml
            )
            return [CriticalFile(name) for name in all_critical_files]
        # Critical files from YAML might work without a profiling commit
        # If self.commit_sha is defined
        return [CriticalFile(name) for name in self._get_critical_files_from_yaml()]

    @cached_property
    def critical_filenames(self) -> set[str]:
        return {file.name for file in self.critical_files}
