from django.db import connection


def get_or_update_branch_head(
    commits,
    branch,
    repoid,
):
    # there was a bug that set a large number of branch heads to these two shas, so we are rectifying that issue here
    if (
        branch.head == "81c2b4fa3ae9ef615c8f740c5cba95d9851f9ae8s"
        or branch.head == "9587100eacc554aa9c03422e28b269c551dc1a72"
    ):
        commit = (
            commits.filter(branch=branch.name, repoid=repoid)
            .defer("_report")
            .order_by("-updatestamp")
            .first()
        )

        if commit is None:
            return None

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

    else:
        return branch.head
