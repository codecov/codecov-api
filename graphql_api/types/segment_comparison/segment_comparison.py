from ariadne import ObjectType

from services.comparison import SegmentComparison

segment_comparison_bindable = ObjectType("SegmentComparison")


@segment_comparison_bindable.field("header")
def resolve_header(segment_comparison: SegmentComparison, info):
    a, b, c, d = segment_comparison.header
    return f"@@ -{a},{b} +{c},{d} @@"


@segment_comparison_bindable.field("lines")
def resolve_lines(segment_comparison: SegmentComparison, info):
    return segment_comparison.lines
