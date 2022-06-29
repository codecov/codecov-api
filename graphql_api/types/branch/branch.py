from ariadne import ObjectType

from graphql_api.dataloader.commit import CommitLoader

branch_bindable = ObjectType("Branch")


@branch_bindable.field("head")
def resolve_head_commit(branch, info):
    if branch.head:
        loader = CommitLoader.loader(info, branch.repository_id)
        return loader.load(branch.head)
