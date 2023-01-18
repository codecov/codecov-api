import enum

from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor
from services.comparison import ComparisonReport, ImpactedFile, ImpactedFileParameter


class FetchImpactedFiles(BaseInteractor):
    def _apply_filters(self, impacted_files, filters):
        parameter = filters.get("ordering", {}).get("parameter")
        direction = filters.get("ordering", {}).get("direction")
        if parameter and direction:
            impacted_files = self.sort_impacted_files(
                impacted_files, parameter, direction
            )
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
        elif parameter == ImpactedFileParameter.MISSES_IN_COMPARISON:
            if impacted_file.misses_in_comparison is not None:
                return impacted_file.misses_in_comparison
        elif parameter == ImpactedFileParameter.PATCH_COVERAGE:
            if impacted_file.patch_coverage is not None:
                return impacted_file.patch_coverage.coverage
        else:
            raise ValueError(f"invalid impacted file parameter: {parameter}")

    """
    Sorts the impacted files by any provided parameter and slides items with None values to the end
    """

    def sort_impacted_files(self, impacted_files, parameter, direction):
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

    def execute(self, comparison, filters):
        comparison_report = ComparisonReport(comparison)

        if filters is None:
            return comparison_report.impacted_files

        has_unintended_changes = filters.get("has_unintended_changes")
        impacted_files = (
            comparison_report.impacted_files_with_unintended_change
            if has_unintended_changes
            else comparison_report.impacted_files
        )

        return self._apply_filters(impacted_files, filters)
