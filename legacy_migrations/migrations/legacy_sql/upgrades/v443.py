# v4.4.3
def run_sql(schema_editor):
    schema_editor.execute(
        """
        ---- Table Changes -----
        alter table owners add column parent_service_id text;


        ----- Functions Created -----

        -- get_customer.sql
        create or replace function get_gitlab_root_group(int) returns jsonb as $$
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
            where depth <= 20
        ), data as (
            select t.ownerid,
            t.service_id
            from tree t
            where t.parent_service_id is null
        )
        select to_jsonb(data) from data limit 1;
        $$ language sql stable strict;

        -- get_customer.sql
        create or replace function get_gitlab_repos_activated(int, text) returns int as $$
        declare _repos_activated int;
        declare _decendents_owner_ids int[];
        begin
            select array(
            with recursive tree as (
                select ownerid, 
                service_id, 
                array[]::text[] as ancestors_service_id,
                1 as depth
                from owners 
                where parent_service_id is null 
                and service = 'gitlab' 
                and ownerid = $1
                union all
                select owners.ownerid, 
                owners.service_id, 
                tree.ancestors_service_id || owners.parent_service_id,
                depth + 1 as depth
                from owners, tree
                where owners.parent_service_id = tree.service_id
                and depth <= 20
            )
            select ownerid 
                from tree 
                where $2 = any(tree.ancestors_service_id)
            ) into _decendents_owner_ids;

            select count(*) into _repos_activated
            from repos
            where ownerid in (select unnest(array_append(_decendents_owner_ids, $1)))
            and private
            and activated;

            return _repos_activated;
        end;
        $$ language plpgsql stable;

        -- get_customer.sql
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


        ---- Functions Modified -----

        drop function if exists get_or_create_owner(service, text, text, text); -- signature change

        -- get_customer.sql
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
                t.plan, t.email,
                t.free, t.did_trial,
                t.invoice_details,
                get_users(t.admins) as admins,
                get_repos_activated($1) as repos_activated
            from owners t
            where t.ownerid = $1
            limit 1
        ) select to_jsonb(data) from data limit 1;
        $$ language sql stable strict;

        -- refresh_repos.sql
        create or replace function refresh_teams(service, jsonb) returns int[] as $$
        declare ownerids int[];
        declare _ownerid int;
        declare _team record;
        begin
            for _team in select d from jsonb_array_elements($2) d loop
            update owners o
            set username = (_team.d->>'username')::citext,
                name = (_team.d->>'name')::text,
                email = (_team.d->>'email')::text,
                avatar_url = (_team.d->>'avatar_url')::text,
                parent_service_id = (_team.d->>'parent_id')::text,
                updatestamp = now()
            where service = $1
                and service_id = (_team.d->>'id')::text
            returning ownerid into _ownerid;

            if not found then
                insert into owners (service, service_id, username, name, email, avatar_url, parent_service_id)
                values ($1, 
                        (_team.d->>'id')::text, 
                        (_team.d->>'username')::citext, 
                        (_team.d->>'name')::text, 
                        (_team.d->>'email')::text, 
                        (_team.d->>'avatar_url')::text, 
                        (_team.d->>'parent_id')::text
                )
                returning ownerid into _ownerid;
            end if;

            select array_append(ownerids, _ownerid) into ownerids;

            end loop;

            return ownerids;

        end;
        $$ language plpgsql volatile strict;

        -- get_ownerid.sql
        create or replace function get_or_create_owner(service, text, text, text, text) returns int as $$
        declare _ownerid int;
        begin
            update owners
            set username = $3, avatar_url = $4, parent_service_id = $5
            where service = $1
            and service_id = $2
            returning ownerid into _ownerid;

            if not found then
            insert into owners (service, service_id, username, avatar_url, parent_service_id)
                values ($1, $2, $3, $4, $5)
                returning ownerid into _ownerid;
            end if;

            return _ownerid;

        end;
        $$ language plpgsql volatile;
    """
    )
