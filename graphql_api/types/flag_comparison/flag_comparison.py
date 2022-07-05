from ariadne import ObjectType
from asgiref.sync import sync_to_async

from compare.models import FlagComparison

flag_comparison_bindable = ObjectType("FlagComparison")


@flag_comparison_bindable.field("name")
@sync_to_async
def resolve_name(flag_comparison: FlagComparison, info) -> str:
    return flag_comparison.repositoryflag.flag_name


@flag_comparison_bindable.field("patchTotals")
def resolve_patch_totals(flag_comparison: FlagComparison, info) -> float:
    return flag_comparison.patch_totals


@flag_comparison_bindable.field("headTotals")
def resolve_headTotals(flag_comparison: FlagComparison, info) -> float:
    return flag_comparison.coverage_totals
