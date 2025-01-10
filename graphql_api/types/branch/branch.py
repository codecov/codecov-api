from typing import Optional

from ariadne import ObjectType
from graphql import GraphQLResolveInfo

from core.models import Branch, Commit
from graphql_api.dataloader.commit import CommitLoader

branch_bindable = ObjectType("Branch")


@branch_bindable.field("headSha")
def resolve_head_sha(branch: Branch, info: GraphQLResolveInfo) -> str:
    head = branch.head
    return head


@branch_bindable.field("head")
async def resolve_head_commit(
    branch: Branch, info: GraphQLResolveInfo
) -> Optional[Commit]:
    head = branch.head
    if head:
        loader = CommitLoader.loader(info, branch.repository_id)
        return await loader.load(head)
