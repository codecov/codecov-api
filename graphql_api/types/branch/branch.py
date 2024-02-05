from typing import Optional

from ariadne import ObjectType

from codecov.db import sync_to_async
from core.models import Branch, Commit
from graphql_api.dataloader.commit import CommitLoader
from utils.temp_branch_fix import get_or_update_branch_head

branch_bindable = ObjectType("Branch")


@branch_bindable.field("headSha")
@sync_to_async
def resolve_head_sha(branch: Branch, info) -> str:
    head = get_or_update_branch_head(Commit.objects, branch, branch.repository_id)
    return head


@branch_bindable.field("head")
async def resolve_head_commit(branch: Branch, info) -> Optional[Commit]:
    head = await sync_to_async(get_or_update_branch_head)(
        Commit.objects, branch, branch.repository_id
    )
    if head:
        loader = CommitLoader.loader(info, branch.repository_id)
        return await loader.load(head)
