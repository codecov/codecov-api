from ariadne import ObjectType

from compare.models import FlagComparison

flag_comparison_bindable = ObjectType("FlagComparison")


@flag_comparison_bindable.field("name")
def resolve_name(flag_comparison: FlagComparison, info) -> str:
    return flag_comparison.repositoryflag.flag_name


@flag_comparison_bindable.field("patchTotals")
def resolve_patch_totals(flag_comparison: FlagComparison, info) -> float:
    return flag_comparison.patch_totals


@flag_comparison_bindable.field("headTotals")
def resolve_headTotals(flag_comparison: FlagComparison, info) -> float:
    return flag_comparison.head_totals


@flag_comparison_bindable.field("baseTotals")
def resolve_headTotals(flag_comparison: FlagComparison, info) -> float:
    return flag_comparison.base_totals
