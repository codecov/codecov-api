def run_sql(schema_editor):
    schema_editor.execute(
        """
        create or replace function get_commitid_from_short(int, text) returns text as $$
            select commitid
            from commits
            where repoid = $1
                and commitid like $2||'%%';
            $$ language sql immutable;


            -- pull
            create or replace function get_tip_of_pull(int, int) returns text as $$
            select head
            from pulls
            where repoid = $1
                and pullid = $2
            limit 1;
            $$ language sql stable;


            -- tips
            create or replace function get_tip(int, text) returns text as $$
            select case when char_length($2) = 40 then $2
                    else coalesce((select head from branches where repoid=$1 and branch=$2 limit 1),
                                (select commitid from commits where repoid=$1 and commitid like $2||'%%' limit 1)) end
            limit 1;
            $$ language sql stable;


            -- branch
            create or replace function get_tip_of_branch(int, text) returns text as $$
            select head
            from branches
            where repoid = $1
                and branch = $2
            limit 1;
            $$ language sql stable;


            create or replace function get_commit_totals(int, text) returns jsonb as $$
            select totals
            from commits
            where repoid = $1
                and commitid = $2
            limit 1;
            $$ language sql stable;


            create or replace function get_commit_totals(int, text, text) returns jsonb as $$
            select report->'files'->$3->1
            from commits
            where repoid = $1
                and commitid = $2
            limit 1;
            $$ language sql stable;


            create or replace function get_commit(repoid integer, _commitid text) returns jsonb as $$
            with d as (
                select timestamp, commitid, branch, pullid::text, parent,
                    ci_passed, updatestamp, message, deleted, totals,
                    get_author(author) as author, state, merged,
                    get_commit_totals($1, c.parent) as parent_totals, notified,
                    report
                from commits c
                where c.repoid = $1
                and commitid = (case when char_length(_commitid) < 40 then get_commitid_from_short($1, _commitid) else _commitid end)
                limit 1
            ) select to_jsonb(d) from d;
            $$ language sql stable;


            create or replace function get_commit_minimum(int, text) returns jsonb as $$
            with d as (
                select timestamp, commitid, ci_passed, message,
                    get_author(author) as author, totals
                from commits
                where repoid = $1
                and commitid = $2
                limit 1
            ) select to_jsonb(d) from d;
            $$ language sql stable;


            create or replace function get_commit_on_branch(int, text) returns jsonb as $$
            select get_commit($1, head)
            from branches
            where repoid = $1 and branch = $2
            limit 1;
            $$ language sql stable;


            create or replace function find_parent_commit(_repoid int,
                                                        _this_commitid text,
                                                        _this_timestamp timestamp,
                                                        _parent_commitids text[],
                                                        _branch text,
                                                        _pullid int) returns text as $$
            declare commitid_ text default null;
            begin
                if array_length(_parent_commitids, 1) > 0 then
                -- first: find a direct decendant
                select commitid into commitid_
                from commits
                where repoid = _repoid
                    and array[commitid] <@ _parent_commitids
                limit 1;
                end if;

                if commitid_ is null then
                -- second: find latest on branch
                select commitid into commitid_
                from commits
                where repoid = _repoid
                    and branch = _branch
                    and pullid is not distinct from _pullid
                    and commitid != _this_commitid
                    and ci_passed
                    and deleted is not true
                    and timestamp < _this_timestamp
                order by timestamp desc
                limit 1;

                if commitid_ is null then
                    -- third: use pull base
                    select base into commitid_
                    from pulls
                    where repoid = _repoid
                    and pullid = _pullid
                    limit 1;
                end if;
                end if;

                return commitid_;
            end;
            $$ language plpgsql stable;
    """
    )
