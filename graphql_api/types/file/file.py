import hashlib
import math
from fractions import Fraction

from ariadne import ObjectType
from shared.utils.merge import LineType, line_type

from codecov.db import sync_to_async
from graphql_api.types.enums import CoverageLine

file_bindable = ObjectType("File")


@file_bindable.field("content")
def resolve_content(data, info):
    command = info.context["executor"].get_command("commit")
    return command.get_file_content(data.get("commit"), data.get("path"))


def get_coverage_type(line_report):
    # Get the coverage type from the line_report
    coverage = line_type(line_report.coverage)
    # Convert the LineType enum from shared to the GraphQL one
    return {
        LineType.hit: CoverageLine.H,
        LineType.miss: CoverageLine.M,
        LineType.partial: CoverageLine.P,
    }.get(coverage)


@file_bindable.field("coverage")
def resolve_content(data, info):
    file_report = data.get("file_report")

    if not file_report:
        return []

    return [
        {"line": line_report[0], "coverage": get_coverage_type(line_report[1])}
        for line_report in file_report.lines
    ]


@file_bindable.field("totals")
def resolve_content(data, info):
    file_report = data.get("file_report")
    return file_report.totals if file_report else None


@file_bindable.field("isCriticalFile")
@sync_to_async
def resolve_is_critical_file(data, info):
    critical_filenames = info.context["profiling_summary"].critical_filenames
    return data.get("path") in critical_filenames


@file_bindable.field("hashedPath")
def resolve_hashed_path(data, info):
    path = data.get("path")
    encoded_path = path.encode()
    md5_path = hashlib.md5(encoded_path)

    return md5_path.hexdigest()
