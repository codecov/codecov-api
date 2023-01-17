class MissingHeadReport:
    message = "Missing head report"


class MissingBaseCommit:
    message = "Invalid base commit"


class MissingHeadCommit:
    message = "Invalid head commit"


class MissingComparison:
    message = "Missing comparison"


class MissingBaseReport:
    message = "Missing base report"


class MissingCoverage:
    def __init__(self, message="Missing coverage"):
        self.message = message


class UnknownPath:
    def __init__(self, message="Unkown path"):
        self.message = message
