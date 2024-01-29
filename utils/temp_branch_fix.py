from django.db import connection


def get_or_update_branch_head(
    commits,
    branch,
    repoid,
):
    commit = (
        commits.filter(branch=branch.name, repository_id=repoid)
        .defer("_report")
        .order_by("-timestamp")
        .first()
    )

    if commit is None or commit.commitid == branch.head:
        return branch.head

    # using this raw sql because the current branches table does not allow for updating based on repoid
    # it only updates based on branch name which means if we were to use the django orm to update this
    # branch.head, all branches with the same name as the one we are trying to update would have their head
    # updated to the value of this ones head
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE branches SET head = %s WHERE branches.repoid = %s AND branches.branch = %s",
            [commit.commitid, repoid, branch.name],
        )

    commit_sha = commit.commitid
    return commit_sha
