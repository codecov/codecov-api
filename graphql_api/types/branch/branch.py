from typing import Optional

from ariadne import ObjectType

from core.models import Branch, Commit
from graphql_api.dataloader.commit import CommitLoader
from utils.temp_branch_fix import get_or_update_branch_head

branch_bindable = ObjectType("Branch")


@branch_bindable.field("headSha")
def resolve_head_sha(branch: Branch, info) -> str:
    head = get_or_update_branch_head(Commit.objects, branch, branch.repository_id)
    return head


@branch_bindable.field("head")
def resolve_head_commit(branch: Branch, info) -> Optional[Commit]:
    head = get_or_update_branch_head(Commit.objects, branch, branch.repository_id)
    if head:
        loader = CommitLoader.loader(info, branch.repository_id)
        return loader.load(head)
