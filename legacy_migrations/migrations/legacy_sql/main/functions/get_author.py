def run_sql(schema_editor):
    schema_editor.execute(
        """
        create or replace function get_author(int) returns jsonb as $$
        with data as (
            select service, service_id, username, email, name
            from owners
            where ownerid=$1
            limit 1
        ) select to_jsonb(data) from data;
        $$ language sql stable strict;
    """
    )
