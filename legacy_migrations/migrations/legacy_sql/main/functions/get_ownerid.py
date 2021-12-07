def run_sql(schema_editor):
    schema_editor.execute(
        """
        create or replace function get_ownerid_if_member(service, citext, int) returns int as $$
        select ownerid
        from owners
        where service=$1
            and username=$2::citext
            and array[$3] <@ organizations
            and private_access is true
        limit 1;
        $$ language sql stable strict;


        create or replace function get_ownerid(service, text, citext, text, text) returns int as $$
        declare _ownerid int;
        begin

            select ownerid into _ownerid
            from owners
            where service=$1
                and service_id=$2
            limit 1;

            if not found and $2 is not null then
            insert into owners (service, service_id, username, name, email)
            values ($1, $2, $3::citext, $4, $5)
            returning ownerid into _ownerid;
            end if;

            return _ownerid;
        end;
        $$ language plpgsql;


        create or replace function try_to_auto_activate(int, int) returns boolean as $$
        update owners
        set plan_activated_users = (
            case when coalesce(array_length(plan_activated_users, 1), 0) < plan_user_count  -- we have credits
                then array_append_unique(plan_activated_users, $2)  -- add user
                else plan_activated_users
                end)
        where ownerid=$1
        returning (plan_activated_users @> array[$2]);
        $$ language sql volatile strict;


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


        create or replace function get_teams(service, integer[]) returns jsonb as $$
        with data as (
            select service_id, service, ownerid::text, username, name
            from owners
            where service=$1
            and array[ownerid] <@ $2
        ) select jsonb_agg(data) from data;
        $$ language sql stable strict;


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
