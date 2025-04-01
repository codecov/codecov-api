from graphql import GraphQLResolveInfo
from graphql.language import (
    FragmentDefinitionNode,
    OperationDefinitionNode,
    parse,
)

from graphql_api.helpers.requested_fields import selected_fields


def parse_into_resolveinfo(source: str) -> GraphQLResolveInfo:
    document = parse(source)

    operation: OperationDefinitionNode | None = None
    fragments: dict[str, FragmentDefinitionNode] = {}

    for definition in document.definitions:
        if isinstance(definition, OperationDefinitionNode):
            operation = definition
        elif isinstance(definition, FragmentDefinitionNode):
            fragments[definition.name.value] = definition

    assert operation
    root_fields = [operation]

    return GraphQLResolveInfo(
        "__root__",
        root_fields,  # list[FieldNode]
        None,
        None,
        None,
        None,
        fragments,  # dict[str, FragmentDefinitionNode]
        None,
        None,
        None,
        None,
        None,
    )


QUERY_CoverageForFile = """
query CoverageForFile(
  $owner: String!
  $repo: String!
  $ref: String!
  $path: String!
  $flags: [String]
  $components: [String]
) {
  owner(username: $owner) {
    repository(name: $repo) {
      __typename
      ... on Repository {
        commit(id: $ref) {
          ...CoverageForFile
        }
        branch(name: $ref) {
          name
          head {
            ...CoverageForFile
          }
        }
      }
      ... on NotFoundError {
        message
      }
      ... on OwnerNotActivatedError {
        message
      }
    }
  }
}

fragment CoverageForFile on Commit {
  commitid
  coverageAnalytics {
    flagNames
    components {
      id
      name
    }
    coverageFile(path: $path, flags: $flags, components: $components) {
      hashedPath
      content
      coverage {
        line
        coverage
      }
      totals {
        percentCovered # Absolute coverage of the commit
      }
    }
  }
}
"""

QUERY_GetRepoConfigurationStatus = """
query GetRepoConfigurationStatus($owner: String!, $repo: String!) {
  owner(username: $owner) {
    plan {
      isTeamPlan
    }
    repository(name:$repo) {
      __typename
      ... on Repository {
        coverageEnabled
        bundleAnalysisEnabled
        testAnalyticsEnabled
        yaml
        languages
        coverageAnalytics {
          flagsCount
          componentsCount
        }
      }
      ... on NotFoundError {
        message
      }
      ... on OwnerNotActivatedError {
        message
      }
    }
  }
}
"""

QUERY_ReposForOwner = """
query ReposForOwner(
  $filters: RepositorySetFilters!
  $owner: String!
  $ordering: RepositoryOrdering!
  $direction: OrderingDirection!
  $after: String
  $first: Int
) {
  owner(username: $owner) {
    repositories(
      filters: $filters
      ordering: $ordering
      orderingDirection: $direction
      first: $first
      after: $after
    ) {
      edges {
        node {
          name
          active
          activated
          private
          coverageAnalytics {
            percentCovered
            lines
          }
          updatedAt
          latestCommitAt
          author {
            username
          }
          coverageEnabled
          bundleAnalysisEnabled
          repositoryConfig {
            indicationRange {
              upperRange
              lowerRange
            }
          }
        }
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
}
"""


def test_requested_fields():
    info = parse_into_resolveinfo(QUERY_CoverageForFile)
    fields = selected_fields(info)

    assert "owner.repository.branch.name" in fields
    assert "owner.repository.branch.head.commitid" in fields
    assert (
        "owner.repository.branch.head.coverageAnalytics.coverageFile.totals.percentCovered"
        in fields
    )

    assert "owner.repository.oldestCommitAt" not in fields
    assert "owner.repository.coverageAnalytics.percentCovered" not in fields
    assert "owner.repository.coverageAnalytics.commitSha" not in fields

    info = parse_into_resolveinfo(QUERY_GetRepoConfigurationStatus)
    fields = selected_fields(info)

    assert "owner.repository.coverageAnalytics" in fields
    assert "owner.repository.oldestCommitAt" not in fields
    assert "owner.repository.coverageAnalytics.percentCovered" not in fields

    info = parse_into_resolveinfo(QUERY_ReposForOwner)
    fields = selected_fields(info)

    assert "owner.repositories.edges.node.latestCommitAt" in fields
    assert "owner.repositories.edges.node.oldestCommitAt" not in fields
    assert "owner.repositories.edges.node.coverageAnalytics" in fields
    assert "owner.repositories.edges.node.coverageAnalytics.percentCovered" in fields
