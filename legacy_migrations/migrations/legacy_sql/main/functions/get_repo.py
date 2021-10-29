def run_sql(schema_editor):
    schema_editor.execute(
        """
        -- used for app/tasks
        create or replace function get_repo(int) returns jsonb as $$
        with d as (select o.service, o.username, o.service_id as owner_service_id, r.ownerid::text,
                            r.name, r.repoid::text, r.service_id, r.updatestamp,
                            r.branch, r.private, hookid, image_token, b.username as bot_username,
                            r.yaml, o.yaml as org_yaml, r.using_integration, o.plan,
                            (r.cache->>'yaml') as _yaml_location,
                            case when r.using_integration then o.integration_id else null end as integration_id,
                            get_access_token(coalesce(r.bot, o.bot, o.ownerid)) as token,
                            case when private and activated is not true and forkid is not null
                            then (select rr.activated from repos rr where rr.repoid = r.forkid limit 1)
                            else activated end as activated
                    from repos r
                    inner join owners o using (ownerid)
                    left join owners b ON (r.bot=b.ownerid)
                    where r.repoid = $1
                    limit 1) select to_jsonb(d) from d;
        $$ language sql stable strict;


        -- used for app/handlers
        create or replace function get_repo(int, citext) returns jsonb as $$
        with repo as (
            select r.yaml, r.name, "language", repoid::text, r.private, r.deleted, r.active, r.cache, b.username as bot_username,
                r.branch, r.service_id, r.updatestamp, upload_token, image_token, hookid, using_integration,
                case when private and activated is not true and forkid is not null
                    then (select rr.activated from repos rr where rr.repoid = r.forkid limit 1)
                    else activated end as activated
            from repos r
            left join owners b ON (r.bot=b.ownerid)
            where r.ownerid = $1 and r.name = $2::citext
            limit 1
        ) select to_jsonb(repo) from repo;
        $$ language sql stable;


        -- used for app/handlers/upload
        create or replace function get_repo_by_token(uuid) returns jsonb as $$
        with d as (
            select get_repo(r.repoid) as repo, o.service
            from repos r
            inner join owners o using (ownerid)
            where r.upload_token = $1
            limit 1
        ) select to_jsonb(d) from d limit 1;
        $$ language sql stable;


        -- used for app/handlers/teams
        create or replace function get_repos(int, int default 0, int default 5) returns jsonb as $$
        with _repos as (
            select private, cache, name, updatestamp, upload_token, branch,
                language, repoid::text, get_repo(forkid) as fork, yaml,
                case when private and activated is not true and forkid is not null
                    then (select rr.activated from repos rr where rr.repoid = r.forkid limit 1)
                    else activated end as activated
            from repos r
            where ownerid = $1
            and active
            offset $2
            limit $3
        ) select coalesce(jsonb_agg(_repos), '[]'::jsonb) from _repos;
        $$ language sql stable;


        create or replace function get_repoid(service, citext, citext) returns int as $$
        select repoid
        from repos r
        inner join owners o using (ownerid)
        where o.service = $1
            and o.username = $2::citext
            and r.name = $3::citext
        limit 1
        $$ language sql stable;
    """
    )
