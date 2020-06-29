def apply_default_filters(queryset):
    """
    By default we only want to include commits with meaningful coverage values when representing charts,
    so exclude from consideration commits where CI failed, commits that are still pending, etc.
    """
    return queryset.filter(
        state="complete", deleted=False, ci_passed=True, totals__isnull=False
    )


def apply_simple_filters(queryset, data):
    """
    Apply any coverage chart filtering parameters that can be construed as a simple queryset.filter call.
    """
    queryset = queryset.filter(
        repository__author__username=data.get("organization"),
        repository__name__in=data.get("repositories", []),
    )

    # Optional filters
    if data.get("branch"):
        queryset = queryset.filter(branch=data.get("branch"))
    if data.get("start_date"):
        queryset = queryset.filter(timestamp__gte=data.get("start_date"))
    if data.get("end_date"):
        queryset = queryset.filter(timestamp__lte=data.get("end_date"))
    return queryset
