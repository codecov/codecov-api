from shared.helpers.color import coverage_to_color

from graphs.badges.badges import large_badge, medium_badge, small_badge, unknown_badge


def get_badge(coverage: str | None, coverage_range: list[int], precision: str):
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


def format_coverage_precision(coverage: float | None, precision: int):
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


def get_bundle_badge(bundle_size_bytes: int | None, precision: int):
    if bundle_size_bytes is None:
        # Returns text 'unknown' instead of bundle size
        return """<svg xmlns="http://www.w3.org/2000/svg" width="106" height="20">
    <linearGradient id="CodecovBadgeGradient" x2="0" y2="100%">
        <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
        <stop offset="1" stop-opacity=".1" />
    </linearGradient>
    <mask id="CodecovBadgeMask106px">
        <rect width="106" height="20" rx="3" fill="#fff" />
    </mask>
    <g mask="url(#CodecovBadgeMask106px)">
        <path fill="#555" d="M0 0h47v20H0z" />
        <path fill="#2C2433" d="M47 0h59v20H47z" />
        <path fill="url(#CodecovBadgeGradient)" d="M0 0h106v20H0z" />
    </g>
    <g fill="#fff" text-anchor="left" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
        <text x="5" y="15" fill="#010101" fill-opacity=".3">bundle</text>
        <text x="5" y="14">bundle</text>
        <text x="52" y="15" fill="#010101" fill-opacity=".3">unknown</text>
        <text x="52" y="14">unknown</text>
    </g>
</svg>
"""

    bundle_size_string = format_bundle_bytes(bundle_size_bytes, precision)
    char_width = 7  # approximate, looks good on all reasonable inputs
    width_in_pixels = len(bundle_size_string) * char_width
    static_width = 57  # width of static elements in the svg (text + margins)

    width = static_width + width_in_pixels

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="20">
    <linearGradient id="CodecovBadgeGradient" x2="0" y2="100%">
        <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
        <stop offset="1" stop-opacity=".1" />
    </linearGradient>
    <mask id="CodecovBadgeMask{width}px">
        <rect width="{width}" height="20" rx="3" fill="#fff" />
    </mask>
    <g mask="url(#CodecovBadgeMask{width}px)">
        <path fill="#555" d="M0 0h47v20H0z" />
        <path fill="#2C2433" d="M47 0h{width_in_pixels + 10}v20H47z" />
        <path fill="url(#CodecovBadgeGradient)" d="M0 0h{width}v20H0z" />
    </g>
    <g fill="#fff" text-anchor="left" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
        <text x="5" y="15" fill="#010101" fill-opacity=".3">bundle</text>
        <text x="5" y="14">bundle</text>
        <text x="52" y="15" fill="#010101" fill-opacity=".3">{bundle_size_string}</text>
        <text x="52" y="14">{bundle_size_string}</text>
    </g>
</svg>
"""


def format_bundle_bytes(bytes: int, precision: int):
    precision = min(abs(precision), 2)  # allow at most 2 decimal places
    kilobyte = 10**3
    megabyte = 10**6
    gigabyte = 10**9

    def remove_trailing_zeros(n: str):
        return (n.rstrip("0") if "." in n else n).rstrip(".")

    if bytes < kilobyte:
        return f"{bytes}B"
    elif bytes < megabyte:
        return f"{remove_trailing_zeros(str(round(bytes / kilobyte, precision)))}KB"
    elif bytes < gigabyte:
        return f"{remove_trailing_zeros(str(round(bytes / megabyte, precision)))}MB"
    else:
        return f"{remove_trailing_zeros(str(round(bytes / gigabyte, precision)))}GB"
