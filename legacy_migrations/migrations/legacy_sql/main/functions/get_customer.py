def run_sql(schema_editor):
    schema_editor.execute(
        """
        create or replace function get_gitlab_root_group(int) returns jsonb as $$
        /* get root group by following parent_service_id to highest level */
        with recursive tree as (
            select o.service_id,
            o.parent_service_id,
            o.ownerid,
            1 as depth
            from owners o
            where o.ownerid = $1
            and o.service = 'gitlab'
            and o.parent_service_id is not null

            union all

            select o.service_id,
            o.parent_service_id,
            o.ownerid,
            depth + 1 as depth
            from tree t
            join owners o
            on o.service_id = t.parent_service_id
            /* avoid infinite loop in case of cycling (2 > 5 > 3 > 2 > 5...) up to Gitlab max subgroup depth of 20 */
            where depth <= 20
        ), data as (
            select t.ownerid,
            t.service_id
            from tree t
            where t.parent_service_id is null
        )
        select to_jsonb(data) from data limit 1;
        $$ language sql stable strict;

        create or replace function get_gitlab_repos_activated(int, text) returns int as $$
        declare _repos_activated int;
        declare _decendents_owner_ids int[];
        begin
            /* get array of owner ids for all subgroups under this group */
            select array(
            with recursive tree as (
                /* seed the recursive query */
                select ownerid,
                service_id,
                array[]::text[] as ancestors_service_id,
                1 as depth
                from owners
                where parent_service_id is null
                and service = 'gitlab'
                and ownerid = $1

                union all

                /* find the descendents */
                select owners.ownerid,
                owners.service_id,
                tree.ancestors_service_id || owners.parent_service_id,
                depth + 1 as depth
                from owners, tree
                where owners.parent_service_id = tree.service_id
                /* avoid infinite loop in case of cycling (2 > 5 > 3 > 2 > 5...) up to Gitlab max subgroup depth of 20 */
                and depth <= 20
            )
            select ownerid
                from tree
                where $2 = any(tree.ancestors_service_id)
            ) into _decendents_owner_ids;

            /* get count of all repos that are active and private owned by this gitlab group and all of its subgroups */
            select count(*) into _repos_activated
            from repos
            where ownerid in (select unnest(array_append(_decendents_owner_ids, $1)))
            and private
            and activated;

            return _repos_activated;
        end;
        $$ language plpgsql stable;

        create or replace function get_repos_activated(int) returns int as $$
        declare _repos_activated int;
        declare _service text;
        declare _service_id text;
        begin
            select o.service, o.service_id into _service, _service_id
            from owners o where o.ownerid = $1;
            
            if _service = 'gitlab' then
            select get_gitlab_repos_activated($1, _service_id) into _repos_activated;
            else
            select count(*) into _repos_activated
                from repos
                where ownerid=$1
                and private
                and activated;
            end if;

            return _repos_activated;
        end;
        $$ language plpgsql stable;

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
                t.student,
                t.student_created_at,
                t.student_updated_at,
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
