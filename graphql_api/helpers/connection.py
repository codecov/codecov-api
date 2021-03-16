from cursor_pagination import CursorPaginator


def build_connection_graphql(name, type_node):
    template = """
    type {connection_name} {{
      edges: [{edge_name}]
      totalCount: Int!
      pageInfo: PageInfo!
    }}

    type {edge_name} {{
      cursor: String!
      node: {type_node}
    }}
    """
    data = {
        "connection_name": name,
        "edge_name": name + 'Edge',
        "type_node": type_node
    }
    return template.format(**data)


def queryset_to_connection(queryset, ordering, first=None, after=None, last=None, before=None):
    if not first and not after:
        first = 100
    paginator = CursorPaginator(queryset, ordering=ordering)
    page = paginator.page(first=first, after=after, last=last, before=before)
    return {
        "edges": [
            {
                "cursor": paginator.cursor(page[pos]),
                "node": repository,
            } for pos, repository in enumerate(page)
        ],
        "totalCount": queryset.count(),
        "pageInfo": {
            "hasNextPage": page.has_next,
            "hasPreviousPage": page.has_previous,
            "startCursor": paginator.cursor(page[0]) if len(page) > 0 else None,
            "endCursor": paginator.cursor(page[-1]) if len(page) > 0 else None,
        }
    }
