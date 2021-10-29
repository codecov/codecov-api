def run_sql(schema_editor):
    schema_editor.execute(
        """          
        create or replace function pulls_drop_flare() returns trigger as $$
        begin
            new.flare = null;
            return new;
        end;
        $$ language plpgsql;


        create trigger pulls_before_update_drop_flare before update on pulls
        for each row
        when (new.state != 'open'::pull_state)
        execute procedure pulls_drop_flare();
    """
    )
