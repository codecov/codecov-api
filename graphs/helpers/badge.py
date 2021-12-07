from math import floor

from shared.helpers.color import coverage_to_color

from graphs.badges.badges import large_badge, medium_badge, small_badge, unknown_badge


def get_badge(coverage, coverage_range, precision):
    """
    Returns and SVG string containing coverage badge

    Parameters:
    coverage (str): coverage to be displayed in badge
    coverage_range (array): array containing two values:
        coverage_range[0] (int): coverage low threshold to use red as badge color
        coverage_range[1] (int): coverage high threshold to use green as badge color
    precision: (str): amount of decimals to be displayed in badge
    """
    precision = int(precision)
    if coverage is not None:
        # Get color for badge
        color = coverage_to_color(*coverage_range)(coverage)
        # Use medium badge to fit coverage of 100%
        if float(coverage) == 100:
            badge = medium_badge
        # Use badge size based on precision (0 = small, 1 = medium, 2 = large)
        elif precision == 0:
            badge = small_badge
        elif precision == 1:
            badge = medium_badge
        else:
            badge = large_badge
    else:
        badge = unknown_badge

    return (
        badge.format(color.hex, coverage).strip() if badge != unknown_badge else badge
    )


def format_coverage_precision(coverage, precision):
    """
    Returns coverage as a string formatted with appropriate precision

    Parameters:
    coverage (string): coverage value
    precision (string): amount of decimals to be displayed in coverage
    """
    if coverage is None:
        return None

    precision = int(precision)
    coverage = float(coverage)
    return ("%%.%sf" % precision) % coverage
