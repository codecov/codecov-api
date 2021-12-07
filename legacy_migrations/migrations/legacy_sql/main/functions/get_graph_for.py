def run_sql(schema_editor):
    schema_editor.execute(
        """
        create or replace function sum_of_file_totals_filtering_sessionids(jsonb, int[]) returns text[] as $$
        -- sum totals for filtered flags
        -- in [<totals list a>, <totals list b>, <totals list c>], [1, 2]
        -- out (<totals list b> + <totals list c>) = <sum totals list>
        with totals as (
            select $1->i as t from unnest($2) as i
        ) select agg_totals(totals.t) from totals;
        $$ language sql immutable;


        create or replace function extract_totals(files jsonb, sessionids int[]) returns jsonb as $$
        -- return {"filename": <totals list>, ...}
        with files as (
            select case
            when sessionids is not null then (select jsonb_agg(row(key, sum_of_file_totals_filtering_sessionids(value->2, sessionids))) from jsonb_each(files))
            else (select jsonb_agg(row(key, value->1)) from jsonb_each(files))
            end as data
        ) select to_jsonb(data) from files;
        $$ language sql immutable;


        create or replace function list_sessionid_by_filtering_flags(sessions jsonb, flags text[]) returns int[] as $$
        -- return session index where flags overlap $1
        with indexes as (
            select (session.key)::int as key
            from jsonb_each(sessions) as session
            where (session.value->>'f')::text is not null
            and flags <@ (select array_agg(trim(f::text, '"')) from jsonb_array_elements((session.value->'f')) f)::text[]
        ) select array_agg(key) from indexes;
        $$ language sql strict immutable;


        create or replace function total_list_to_json(totals text[]) returns jsonb as $$
        select ('{"f":'||totals[1]||','||
                '"n":'||totals[2]||','||
                '"h":'||totals[3]||','||
                '"m":'||totals[4]||','||
                '"p":'||totals[5]||','||
                '"c":'||totals[6]||','||
                '"b":'||totals[7]||','||
                '"d":'||totals[8]||','||
                '"M":'||totals[9]||','||
                '"s":'||totals[10]||'}')::jsonb;
        $$ language sql strict immutable;


        create or replace function sum_session_totals(sessions jsonb, flags text[]) returns jsonb as $$
        -- sum totals for filtered flags
        -- in {"0": {"t": <totals list a>}, "1": {"t": <totals list b>}, "2", {"t": <totals list c>}], [1, 2]
        -- out (<totals list b> + <totals list c>) = <sum totals list>
        with totals as (
            select sessions->(i::text)->'t' as t from unnest(list_sessionid_by_filtering_flags(sessions, flags)) as i
        ) select total_list_to_json(agg_totals(totals.t)) from totals;
        $$ language sql strict immutable;


        create or replace function get_graph_for_flare_pull(int, text, text, text[]) returns jsonb as $$
        with data as (
            select r.repoid, r.service_id, p.head as commitid, r.branch,
                p.flare,
                case when p.flare is null
                        then extract_totals(c.report->'files', list_sessionid_by_filtering_flags(c.report->'sessions', $4))
                        else null
                        end as files_by_total,
                coalesce((r.yaml->'coverage'->'range')::jsonb,
                            (o.yaml->'coverage'->'range')::jsonb) as coverage_range
            from repos r
            inner join owners o using (ownerid)
            inner join pulls p using (repoid)
            inner join commits c on c.repoid = r.repoid and c.commitid = p.head
            where r.repoid = $1
            and p.pullid = $2::int
            and (not r.private or r.image_token = $3)
            limit 1
        ) select to_jsonb(data) from data limit 1;
        $$ language sql stable;


        create or replace function get_graph_for_flare_commit(int, text, text, text[]) returns jsonb as $$
        with data as (
            select r.repoid, r.service_id, c.commitid, r.branch,
                extract_totals(c.report->'files', list_sessionid_by_filtering_flags(c.report->'sessions', $4)) as files_by_total,
                coalesce((r.yaml->'coverage'->'range')::jsonb,
                            (o.yaml->'coverage'->'range')::jsonb) as coverage_range
            from repos r
            inner join owners o using (ownerid)
            inner join commits c using (repoid)
            where r.repoid = $1
            and c.commitid = $2
            and (not r.private or r.image_token = $3)
            limit 1
        ) select to_jsonb(data) from data limit 1;
        $$ language sql stable;


        create or replace function get_graph_for_flare_branch(int, text, text, text[]) returns jsonb as $$
        with data as (
            select r.repoid, r.service_id, c.commitid, r.branch,
                extract_totals(c.report->'files', list_sessionid_by_filtering_flags(c.report->'sessions', $4)) as files_by_total,
                coalesce((r.yaml->'coverage'->'range')::jsonb,
                            (o.yaml->'coverage'->'range')::jsonb) as coverage_range
            from repos r
            inner join owners o using (ownerid)
            inner join branches b using (repoid)
            inner join commits c on c.repoid = r.repoid and c.commitid = b.head
            where r.repoid = $1
            and b.branch = case when $2 is null then r.branch else $2 end
            and (not r.private or r.image_token = $3)
            limit 1
        ) select to_jsonb(data) from data limit 1;
        $$ language sql stable;


        create or replace function get_graph_for_totals_pull(int, text, text, text[]) returns jsonb as $$
        with data as (
            select r.repoid, r.service_id, r.branch,
                p.base as base_commitid,
                case when $4 is null
                        then (select totals from commits where repoid=p.repoid and commitid=p.base limit 1)
                        else (select sum_session_totals(report->'sessions', $4)
                            from commits
                            where repoid=$1
                                and commitid=p.base
                            limit 1)
                        end as base_totals,
                p.head as head_commitid,
                case when $4 is null
                        then (select totals from commits where repoid=p.repoid and commitid=p.head limit 1)
                        else (select sum_session_totals(report->'sessions', $4)
                            from commits
                            where repoid=$1
                                and commitid=p.head
                            limit 1)
                        end as head_totals,
                coalesce((r.yaml->'coverage'->'range')::jsonb,
                            (o.yaml->'coverage'->'range')::jsonb) as coverage_range
            from repos r
            inner join owners o using (ownerid)
            inner join pulls p using (repoid)
            where r.repoid = $1
            and p.pullid = $2::int
            and (not r.private or r.image_token = $3)
            limit 1
        ) select to_jsonb(data) from data limit 1;
        $$ language sql stable;


        create or replace function get_graph_for_totals_commit(int, text, text, text[]) returns jsonb as $$
        with data as (
            select r.repoid, r.service_id, r.branch,
                base.commitid as base_commitid,
                case when $4 is null
                        then base.totals
                        else sum_session_totals(base.report->'sessions', $4)
                        end as base_totals,
                head.commitid as head_commitid,
                case when $4 is null
                        then head.totals
                        else sum_session_totals(head.report->'sessions', $4)
                        end as head_totals,
                coalesce((r.yaml->'coverage'->'range')::jsonb,
                            (o.yaml->'coverage'->'range')::jsonb) as coverage_range
            from repos r
            inner join owners o using (ownerid)
            inner join commits head using (repoid)
            left join commits base on base.repoid = r.repoid
                and base.commitid = head.parent
            where r.repoid = $1
            and head.commitid = $2
            and (not r.private or r.image_token = $3)
            limit 1
        ) select to_jsonb(data) from data limit 1;
        $$ language sql stable;


        create or replace function get_graph_for_totals_branch(int, text, text, text[]) returns jsonb as $$
        with data as (
            select r.repoid, r.service_id, r.branch,
                base.commitid as base_commitid,
                case when $4 is null
                        then base.totals
                        else sum_session_totals(base.report->'sessions', $4)
                        end as base_totals,
                head.commitid as head_commitid,
                case when $4 is null
                        then head.totals
                        else sum_session_totals(head.report->'sessions', $4)
                        end as head_totals,
                coalesce((r.yaml->'coverage'->'range')::jsonb,
                            (o.yaml->'coverage'->'range')::jsonb) as coverage_range
            from repos r
            inner join owners o using (ownerid)
            inner join branches b using (repoid)
            left join commits base on base.repoid = r.repoid
                and base.commitid = b.base
            inner join commits head on head.repoid = r.repoid
                and head.commitid = b.head
            where r.repoid = $1
            and b.branch = case when $2 is null then r.branch else $2 end
            and (not r.private or r.image_token = $3)
            limit 1
        ) select to_jsonb(data) from data limit 1;
        $$ language sql stable;


        create or replace function get_graph_for_commits_pull(int, text, text, text[]) returns jsonb as $$
        with data as (
            select r.repoid, r.service_id, r.branch,
                coalesce((r.yaml->'coverage'->'range')::jsonb,
                            (o.yaml->'coverage'->'range')::jsonb) as coverage_range
            from repos r
            inner join owners o using (ownerid)
            inner join pulls p using (repoid)
            where r.repoid = $1
            and p.pullid = $2::int
            and (not r.private or r.image_token = $3)
            limit 1
        ) select to_jsonb(data) from data limit 1;
        $$ language sql stable;


        create or replace function get_graph_for_commits_branch(int, text, text, text[]) returns jsonb as $$
        with data as (
            select r.repoid, r.service_id, r.branch,
                coalesce((r.yaml->'coverage'->'range')::jsonb,
                            (o.yaml->'coverage'->'range')::jsonb) as coverage_range
            from repos r
            inner join owners o using (ownerid)
            inner join branches b using (repoid)
            where r.repoid = $1
            and b.branch = case when $2 is null then r.branch else $2 end
            and (not r.private or r.image_token = $3)
            limit 1
        ) select to_jsonb(data) from data limit 1;
        $$ language sql stable;
    """
    )
