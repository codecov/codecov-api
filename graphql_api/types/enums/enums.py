import enum


class OrderingParameter(enum.Enum):
    NAME = "name"
    COVERAGE = "coverage"
    HITS = "hits"
    MISSES = "misses"
    PARTIALS = "partials"
    LINES = "lines"


class DisplayType(enum.Enum):
    LIST = "list"
    TREE = "tree"


class RepositoryOrdering(enum.Enum):
    COMMIT_DATE = "latest_commit_at"
    COVERAGE = "coverage"
    ID = "repoid"
    NAME = "name"


class OrderingDirection(enum.Enum):
    ASC = "ascending"
    DESC = "descending"


class CoverageLine(enum.Enum):
    H = "hit"
    M = "miss"
    P = "partial"


class TypeProjectOnboarding(enum.Enum):
    PERSONAL = "PERSONAL"
    YOUR_ORG = "YOUR_ORG"
    OPEN_SOURCE = "OPEN_SOURCE"
    EDUCATIONAL = "EDUCATIONAL"


class GoalOnboarding(enum.Enum):
    STARTING_WITH_TESTS = "STARTING_WITH_TESTS"
    IMPROVE_COVERAGE = "IMPROVE_COVERAGE"
    MAINTAIN_COVERAGE = "MAINTAIN_COVERAGE"
    TEAM_REQUIREMENTS = "TEAM_REQUIREMENTS"
    OTHER = "OTHER"


class PullRequestState(enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"


class UploadState(enum.Enum):
    STARTED = "started"
    UPLOADED = "uploaded"
    PROCESSED = "processed"
    ERROR = "error"
    COMPLETE = "complete"


class UploadType(enum.Enum):
    UPLOADED = "uploaded"
    CARRIEDFORWARD = "carriedforward"


class UploadErrorEnum(enum.Enum):
    FILE_NOT_IN_STORAGE = "file_not_in_storage"
    REPORT_EXPIRED = "report_expired"
    REPORT_EMPTY = "report_empty"


class LoginProvider(enum.Enum):
    GITHUB = "github"
    GITHUB_ENTERPRISE = "github_enterprise"
    GITLAB = "gitlab"
    GITLAB_ENTERPRISE = "gitlab_enterprise"
    BITBUCKET = "bitbucket"
    BITBUCKET_SERVER = "bitbucket_server"
