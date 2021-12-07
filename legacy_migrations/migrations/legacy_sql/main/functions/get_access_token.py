def run_sql(schema_editor):
    schema_editor.execute(
        """
        create or replace function get_access_token(int) returns jsonb as $$
        with data as (
            select ownerid, oauth_token, username
            from owners o
            where ownerid = $1
            and oauth_token is not null
            limit 1
        ) select to_jsonb(data) from data;
        $$ language sql stable strict;
    """
    )
