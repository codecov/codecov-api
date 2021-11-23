def run_sql(schema_editor):
    schema_editor.execute(
        """
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


        create or replace function get_username(int) returns citext as $$
        select username from owners where ownerid=$1 limit 1;
        $$ language sql stable strict;


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
    """
    )
