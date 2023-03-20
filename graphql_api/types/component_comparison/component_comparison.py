from ariadne import ObjectType
from shared.reports.types import ReportTotals

from codecov.db import sync_to_async
from services.components import ComponentComparison

component_comparison_bindable = ObjectType("ComponentComparison")


@component_comparison_bindable.field("id")
def resolve_id(component_comparison: ComponentComparison, info) -> str:
    return component_comparison.component.component_id


@component_comparison_bindable.field("name")
def resolve_name(component_comparison: ComponentComparison, info) -> str:
    return component_comparison.component.get_display_name()


@component_comparison_bindable.field("baseTotals")
def resolve_base_totals(
    component_comparison: ComponentComparison, info
) -> ReportTotals:
    return component_comparison.base_totals


@component_comparison_bindable.field("headTotals")
def resolve_head_totals(
    component_comparison: ComponentComparison, info
) -> ReportTotals:
    return component_comparison.head_totals


@component_comparison_bindable.field("patchTotals")
@sync_to_async
def resolve_patch_totals(
    component_comparison: ComponentComparison, info
) -> ReportTotals:
    return component_comparison.patch_totals
