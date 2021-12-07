# v4.4.2
def run_sql(schema_editor):
    schema_editor.execute(
        """
        ---- Column Updates -----
        alter table owners add column avatar_url text;


        ---- Function Changes -----

        -- get_ownerid.sql
        create or replace function get_owner(service, citext) returns jsonb as $$
        with data as (
            select service_id, service, ownerid::text, username, avatar_url, 
                updatestamp, plan, name, integration_id, free,
                plan_activated_users, plan_auto_activate, plan_user_count
            from owners
            where service=$1
            and username=$2::citext
            limit 1
        ) select to_jsonb(data)
            from data
            limit 1;
        $$ language sql stable strict;

        -- get_ownerid.sql
        create or replace function get_or_create_owner(service, text, text, text) returns int as $$
        declare _ownerid int;
        begin
            update owners
            set username = $3, avatar_url = $4
            where service = $1
            and service_id = $2
            returning ownerid into _ownerid;

            if not found then
            insert into owners (service, service_id, username, avatar_url)
                values ($1, $2, $3, $4)
                returning ownerid into _ownerid;
            end if;

            return _ownerid;

        end;
        $$ language plpgsql volatile;

        -- get_user.sql
        create or replace function get_user(int) returns jsonb as $$
        with data as (
            select ownerid::text, private_access, staff, service, service_id,
                username, organizations, avatar_url,
                oauth_token, plan, permission,
                free, email, name, createstamp
            from owners
            where ownerid=$1
            limit 1
        ) select to_jsonb(data) from data;
        $$ language sql stable;

        -- get_user.sql
        create or replace function get_users(int[]) returns jsonb as $$
        with data as (
            select service, service_id::text, ownerid::text, username, name, email, avatar_url 
            from owners
            where array[ownerid] <@ $1
            limit array_length($1, 1)
        ) select jsonb_agg(data)
            from data
            limit array_length($1, 1);
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
                updatestamp = now()
            where service = $1
                and service_id = (_team.d->>'id')::text
            returning ownerid into _ownerid;

            if not found then
                insert into owners (service, service_id, username, name, email, avatar_url)
                values ($1, (_team.d->>'id')::text, (_team.d->>'username')::citext, (_team.d->>'name')::text, (_team.d->>'email')::text, (_team.d->>'avatar_url')::text)
                returning ownerid into _ownerid;
            end if;

            select array_append(ownerids, _ownerid) into ownerids;

            end loop;

            return ownerids;

        end;
        $$ language plpgsql volatile strict;
    """
    )
