# v4.4.6
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

        create or replace function get_customer(int) returns jsonb as $$
        with data as (
            select t.stripe_customer_id,
                t.stripe_subscription_id,
                t.ownerid::text,
                t.service,
                t.service_id,
                t.plan_user_count,
                t.plan_provider,
                t.plan_auto_activate,
                t.plan_activated_users,
                t.plan,
                t.email,
                t.free,
                t.did_trial,
                t.invoice_details,
                t.yaml,
                b.username as bot_username,
                get_users(t.admins) as admins,
                get_repos_activated($1::int) as repos_activated
            from owners t
            LEFT JOIN owners b ON (b.ownerid = t.bot)
            where t.ownerid = $1
            limit 1
        ) select to_jsonb(data) from data limit 1;
        $$ language sql stable strict;
    """
    )
