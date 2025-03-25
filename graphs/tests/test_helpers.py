from graphs.helpers.badge import (
    format_bundle_bytes,
    format_coverage_precision,
    get_badge,
    get_bundle_badge,
)


class TestGraphsHelpers(object):
    def test_format_coverage_precision(self):
        coverage = "91.1111"
        precision = "1"

        expected_coverage = "91.1"
        _coverage = format_coverage_precision(coverage, precision)
        assert expected_coverage == _coverage

        precision = "0"
        expected_coverage = "91"
        _coverage = format_coverage_precision(coverage, precision)
        assert expected_coverage == _coverage

        precision = "2"
        expected_coverage = "91.11"
        _coverage = format_coverage_precision(coverage, precision)
        assert expected_coverage == _coverage

    def test_badge(self):
        # Test medium badge
        coverage = 91.1
        precision = 1
        coverage_range = [70, 100]

        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="122" height="20">
                <linearGradient id="b" x2="0" y2="100%">
                    <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                    <stop offset="1" stop-opacity=".1" />
                </linearGradient>
                <mask id="a">
                    <rect width="122" height="20" rx="3" fill="#fff" />
                </mask>
                <g mask="url(#a)">
                    <path fill="#555" d="M0 0h76v20H0z" />
                    <path fill="#a1b90e" d="M76 0h46v20H76z" />
                    <path fill="url(#b)" d="M0 0h122v20H0z" />
                </g>
                <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                    <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                    <text x="46" y="14">codecov</text>
                    <text x="98" y="15" fill="#010101" fill-opacity=".3">91.1%</text>
                    <text x="98" y="14">91.1%</text>
                </g>
                <svg viewBox="140 -8 60 60">
                    <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
                </svg>
            </svg>"""

        _badge = get_badge(coverage, coverage_range, precision)
        _badge = [line.strip() for line in _badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == _badge

        # Test small badge
        coverage = 80
        precision = 0
        coverage_range = [70, 100]

        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="112" height="20">
            <linearGradient id="b" x2="0" y2="100%">
                <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                <stop offset="1" stop-opacity=".1" />
            </linearGradient>
            <mask id="a">
                <rect width="112" height="20" rx="3" fill="#fff" />
            </mask>
            <g mask="url(#a)">
                <path fill="#555" d="M0 0h73v20H0z" />
                <path fill="#efa41b" d="M73 0h39v20H73z" />
                <path fill="url(#b)" d="M0 0h112v20H0z" />
            </g>
            <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                <text x="46" y="14">codecov</text>
                <text x="93" y="15" fill="#010101" fill-opacity=".3">80%</text>
                <text x="93" y="14">80%</text>
            </g>
            <svg viewBox="120 -8 60 60">
                <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
            </svg>
        </svg>"""
        _badge = get_badge(coverage, coverage_range, precision)
        _badge = [line.strip() for line in _badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == _badge

        # Test large badge

        coverage = 60.52
        precision = 2
        coverage_range = [70, 100]

        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="132" height="20">
            <linearGradient id="b" x2="0" y2="100%">
                <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                <stop offset="1" stop-opacity=".1" />
            </linearGradient>
            <mask id="a">
                <rect width="132" height="20" rx="3" fill="#fff" />
            </mask>
            <g mask="url(#a)">
                <path fill="#555" d="M0 0h76v20H0z" />
                <path fill="#e05d44" d="M76 0h56v20H76z" />
                <path fill="url(#b)" d="M0 0h132v20H0z" />
            </g>
            <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                <text x="46" y="14">codecov</text>
                <text x="103" y="15" fill="#010101" fill-opacity=".3">60.52%</text>
                <text x="103" y="14">60.52%</text>
            </g>
            <svg viewBox="156 -8 60 60">
                <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
            </svg>
        </svg>"""

        _badge = get_badge(coverage, coverage_range, precision)
        _badge = [line.strip() for line in _badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == _badge

    def test_unknown_badge(self):
        coverage = None
        precision = 2
        coverage_range = [70, 100]

        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="137" height="20">
                <linearGradient id="b" x2="0" y2="100%">
                    <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                    <stop offset="1" stop-opacity=".1" />
                </linearGradient>
                <mask id="a">
                    <rect width="137" height="20" rx="3" fill="#fff" />
                </mask>
                <g mask="url(#a)">
                    <path fill="#555" d="M0 0h76v20H0z" />
                    <path fill="#9f9f9f" d="M76 0h61v20H76z" />
                    <path fill="url(#b)" d="M0 0h137v20H0z" />
                </g>
                <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                    <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                    <text x="46" y="14">codecov</text>
                    <text x="105.5" y="15" fill="#010101" fill-opacity=".3">unknown</text>
                    <text x="105.5" y="14">unknown</text>
                </g>
                <svg viewBox="161 -8 60 60">
                    <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
                </svg>
            </svg>
            """

        _badge = get_badge(coverage, coverage_range, precision)
        _badge = [line.strip() for line in _badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == _badge

    def test_bundle_badge_small(self):
        bundle_size_bytes = 7
        precision = 2

        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="71" height="20">
              <linearGradient id="CodecovBadgeGradient" x2="0" y2="100%">
                <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                <stop offset="1" stop-opacity=".1" />
              </linearGradient>
              <mask id="CodecovBadgeMask71px">
                <rect width="71" height="20" rx="3" fill="#fff" />
              </mask>
              <g mask="url(#CodecovBadgeMask71px)">
                <path fill="#555" d="M0 0h47v20H0z" />
                <path fill="#2C2433" d="M47 0h24v20H47z" />
                <path fill="url(#CodecovBadgeGradient)" d="M0 0h71v20H0z" />
              </g>
              <g fill="#fff" text-anchor="left" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                <text x="5" y="15" fill="#010101" fill-opacity=".3">bundle</text>
                <text x="5" y="14">bundle</text>
                <text x="52" y="15" fill="#010101" fill-opacity=".3">7B</text>
                <text x="52" y="14">7B</text>
              </g>
            </svg>
            """

        _badge = get_bundle_badge(bundle_size_bytes, precision)
        _badge = [line.strip() for line in _badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == _badge

    def test_bundle_badge_medium(self):
        bundle_size_bytes = 7777777
        precision = 2

        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="99" height="20">
                <linearGradient id="CodecovBadgeGradient" x2="0" y2="100%">
                    <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                    <stop offset="1" stop-opacity=".1" />
                </linearGradient>
                <mask id="CodecovBadgeMask99px">
                    <rect width="99" height="20" rx="3" fill="#fff" />
                </mask>
                <g mask="url(#CodecovBadgeMask99px)">
                    <path fill="#555" d="M0 0h47v20H0z" />
                    <path fill="#2C2433" d="M47 0h52v20H47z" />
                    <path fill="url(#CodecovBadgeGradient)" d="M0 0h99v20H0z" />
                </g>
                <g fill="#fff" text-anchor="left" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                    <text x="5" y="15" fill="#010101" fill-opacity=".3">bundle</text>
                    <text x="5" y="14">bundle</text>
                    <text x="52" y="15" fill="#010101" fill-opacity=".3">7.78MB</text>
                    <text x="52" y="14">7.78MB</text>
                </g>
            </svg>
            """

        _badge = get_bundle_badge(bundle_size_bytes, precision)
        _badge = [line.strip() for line in _badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == _badge

    def test_bundle_badge_large(self):
        bundle_size_bytes = 7777777777777
        precision = 2

        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="120" height="20">
              <linearGradient id="CodecovBadgeGradient" x2="0" y2="100%">
                  <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                  <stop offset="1" stop-opacity=".1" />
              </linearGradient>
              <mask id="CodecovBadgeMask120px">
                  <rect width="120" height="20" rx="3" fill="#fff" />
              </mask>
              <g mask="url(#CodecovBadgeMask120px)">
                  <path fill="#555" d="M0 0h47v20H0z" />
                  <path fill="#2C2433" d="M47 0h73v20H47z" />
                  <path fill="url(#CodecovBadgeGradient)" d="M0 0h120v20H0z" />
              </g>
              <g fill="#fff" text-anchor="left" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                  <text x="5" y="15" fill="#010101" fill-opacity=".3">bundle</text>
                  <text x="5" y="14">bundle</text>
                  <text x="52" y="15" fill="#010101" fill-opacity=".3">7777.78GB</text>
                  <text x="52" y="14">7777.78GB</text>
              </g>
            </svg>
            """

        _badge = get_bundle_badge(bundle_size_bytes, precision)
        _badge = [line.strip() for line in _badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == _badge

    def test_bundle_badge_unknown(self):
        bundle_size_bytes = None
        precision = 2

        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="106" height="20">
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

        _badge = get_bundle_badge(bundle_size_bytes, precision)
        _badge = [line.strip() for line in _badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == _badge

    def test_format_bundle_bytes_0_precision(self):
        bundle_sizes = [
            7,
            77,
            777,
            7777,
            77777,
            777777,
            7777777,
            77777777,
            777777777,
            7777777777,
            77777777777,
            777777777777,
            7777777777777,
        ]

        expected = [
            "7B",
            "77B",
            "777B",
            "8KB",
            "78KB",
            "778KB",
            "8MB",
            "78MB",
            "778MB",
            "8GB",
            "78GB",
            "778GB",
            "7778GB",
        ]

        for i in range(len(bundle_sizes)):
            assert format_bundle_bytes(bundle_sizes[i], 0) == expected[i]

    def test_format_bundle_bytes_1_precision(self):
        bundle_sizes = [
            7,
            77,
            777,
            7777,
            77777,
            777777,
            7777777,
            77777777,
            777777777,
            7777777777,
            77777777777,
            777777777777,
            7777777777777,
        ]

        expected = [
            "7B",
            "77B",
            "777B",
            "7.8KB",
            "77.8KB",
            "777.8KB",
            "7.8MB",
            "77.8MB",
            "777.8MB",
            "7.8GB",
            "77.8GB",
            "777.8GB",
            "7777.8GB",
        ]

        for i in range(len(bundle_sizes)):
            assert format_bundle_bytes(bundle_sizes[i], 1) == expected[i]

    def test_format_bundle_bytes_2_precision(self):
        bundle_sizes = [
            7,
            77,
            777,
            7777,
            77777,
            777777,
            7777777,
            77777777,
            777777777,
            7777777777,
            77777777777,
            777777777777,
            7777777777777,
        ]

        expected = [
            "7B",
            "77B",
            "777B",
            "7.78KB",
            "77.78KB",
            "777.78KB",
            "7.78MB",
            "77.78MB",
            "777.78MB",
            "7.78GB",
            "77.78GB",
            "777.78GB",
            "7777.78GB",
        ]

        for i in range(len(bundle_sizes)):
            assert format_bundle_bytes(bundle_sizes[i], 2) == expected[i]

    def test_format_bundle_strips_zeros(self):
        bundle_sizes = [
            0,
            10,
            100,
            1000,
            10000,
            100000,
            1000000,
            10000000,
            100000000,
            1000000000,
            10000000000,
            100000000000,
            1000000000000,
            1100,
            11100,
            111100,
        ]

        expected = [
            "0B",
            "10B",
            "100B",
            "1KB",
            "10KB",
            "100KB",
            "1MB",
            "10MB",
            "100MB",
            "1GB",
            "10GB",
            "100GB",
            "1000GB",
            "1.1KB",
            "11.1KB",
            "111.1KB",
        ]

        for i in range(len(bundle_sizes)):
            assert format_bundle_bytes(bundle_sizes[i], 2) == expected[i]
