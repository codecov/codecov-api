def run_sql(schema_editor):
    schema_editor.execute(
        """
        create or replace function verify_session(text, text, uuid, sessiontype) returns jsonb as $$
        -- try any members
        update sessions
        set lastseen = now(),
            ip = $1,
            useragent = $2
        where token = $3
            and type = $4
        returning get_user(ownerid);
        $$ language sql volatile;
    """
    )
