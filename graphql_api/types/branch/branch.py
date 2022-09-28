from typing import Optional

from ariadne import ObjectType

from core.models import Branch, Commit
from graphql_api.dataloader.commit import CommitLoader

branch_bindable = ObjectType("Branch")


@branch_bindable.field("headSha")
def resolve_head_sha(branch: Branch, info) -> str:
    return branch.head


@branch_bindable.field("head")
def resolve_head_commit(branch: Branch, info) -> Optional[Commit]:
    if branch.head:
        loader = CommitLoader.loader(info, branch.repository_id)
        return loader.load(branch.head)
