import enum


class RepositoryOrdering(enum.Enum):
    COMMIT_DATE = "updatestamp"
    COVERAGE = "coverage"
    NAME = "name"


class OrderingDirection(enum.Enum):
    ASC = "ascending"
    DESC = "descending"
