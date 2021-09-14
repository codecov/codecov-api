import math
from fractions import Fraction
from ariadne import ObjectType
from asgiref.sync import sync_to_async
from shared.utils.merge import LineType, line_type

file_bindable = ObjectType("File")


@file_bindable.field("content")
def resolve_content(data, info):
    command = info.context["executor"].get_command("commit")
    return command.get_file_content(data.get("commit"), data.get("path"))


@file_bindable.field("coverage")
def resolve_content(data, info):
    file_report = data.get("file_report")

    if not file_report:
        return []

    return [
        {
            "line": line_report[0],
            "coverage": line_type(line_report[1].coverage),
        }
        for line_report in file_report.lines
    ]


@file_bindable.field("totals")
def resolve_content(data, info):
    file_report = data.get("file_report")
    return file_report.totals if file_report else None
