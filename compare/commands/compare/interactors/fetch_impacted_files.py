import enum
from typing import List, Optional, Union

from codecov.commands.base import BaseInteractor
from services.comparison import Comparison, ComparisonReport, ImpactedFile
from services.report import (
    files_belonging_to_flags,
    files_in_sessions,
    get_sessions_ids,
)
from services.components import commit_components, components_filtered_report


class ImpactedFileParameter(enum.Enum):
    FILE_NAME = "file_name"
    CHANGE_COVERAGE = "change_coverage"
    HEAD_COVERAGE = "head_coverage"
    MISSES_COUNT = "misses_count"
    PATCH_COVERAGE = "patch_coverage"


class FetchImpactedFiles(BaseInteractor):
    def _apply_filters(
        self,
        impacted_files: Optional[List[ImpactedFile]],
        comparison: Comparison,
        filters,
    ):
        parameter = filters.get("ordering", {}).get("parameter")
        direction = filters.get("ordering", {}).get("direction")
        if parameter and direction:
            impacted_files = self.sort_impacted_files(
                impacted_files, parameter, direction
            )
        flags_filter = filters.get("flags", [])
        components_filter = filters.get("components", [])

        if not comparison:
            return impacted_files

        head_commit_report = comparison.head_report
        head_commit = comparison.head_commit

        if components_filter:
            head_commit_components = commit_components(
                commit=head_commit, owner=head_commit.author
            )
            filtered_components = [
                component
                for component in head_commit_components
                if component.name in components_filter
            ]
            head_commit_report = components_filtered_report(
                report=head_commit_report, component=filtered_components
            )

            # don't loop twice over the same report
            if not flags_filter:
                session_ids = get_sessions_ids(commit_report=head_commit_report)
                files_in_specific_sessions = files_in_sessions(
                    commit_report=head_commit_report, session_ids=session_ids
                )
                impacted_files = [
                    file
                    for file in impacted_files
                    if file.head_name in files_in_specific_sessions
                ]

        if flags_filter:
            if set(flags_filter) & set(head_commit_report.flags):
                files = files_belonging_to_flags(
                    commit_report=head_commit_report, flags=flags_filter
                )
                impacted_files = [
                    file for file in impacted_files if file.head_name in files
                ]

        return impacted_files

    def get_attribute(
        self, impacted_file: ImpactedFile, parameter: ImpactedFileParameter
    ):
        if parameter == ImpactedFileParameter.FILE_NAME:
            return impacted_file.file_name
        elif parameter == ImpactedFileParameter.CHANGE_COVERAGE:
            return impacted_file.change_coverage
        elif parameter == ImpactedFileParameter.HEAD_COVERAGE:
            if impacted_file.head_coverage is not None:
                return impacted_file.head_coverage.coverage
        elif parameter == ImpactedFileParameter.MISSES_COUNT:
            if impacted_file.misses_count is not None:
                return impacted_file.misses_count
        elif parameter == ImpactedFileParameter.PATCH_COVERAGE:
            if impacted_file.patch_coverage is not None:
                return impacted_file.patch_coverage.coverage
        else:
            raise ValueError(f"invalid impacted file parameter: {parameter}")

    def sort_impacted_files(self, impacted_files, parameter, direction):
        """
        Sorts the impacted files by any provided parameter and slides items with None values to the end
        """
        # Separate impacted files with None values for the specified parameter value
        files_with_coverage = []
        files_without_coverage = []
        for file in impacted_files:
            if self.get_attribute(file, parameter) is not None:
                files_with_coverage.append(file)
            else:
                files_without_coverage.append(file)

        # Sort impacted_files list based on parameter value
        is_reversed = direction.value == "descending"
        files_with_coverage = sorted(
            files_with_coverage,
            key=lambda x: self.get_attribute(x, parameter),
            reverse=is_reversed,
        )

        # Merge both lists together
        return files_with_coverage + files_without_coverage

    def execute(
        self,
        comparison_report: ComparisonReport,
        comparison: Comparison,
        filters,
    ):
        if filters is None:
            return comparison_report.impacted_files

        has_unintended_changes = filters.get("has_unintended_changes")
        if has_unintended_changes is not None:
            impacted_files = (
                comparison_report.impacted_files_with_unintended_changes
                if has_unintended_changes
                else comparison_report.impacted_files_with_direct_changes
            )
        else:
            impacted_files = comparison_report.impacted_files

        return self._apply_filters(impacted_files, comparison, filters)
