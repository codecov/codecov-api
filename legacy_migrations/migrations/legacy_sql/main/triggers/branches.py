def run_sql(schema_editor):
    schema_editor.execute(
        """
        create or replace function branches_update() returns trigger as $$
        declare _ownerid int;
        begin
            -- update repos cache if main branch
            update repos
            set updatestamp = now(),
                cache = update_json(cache::jsonb, 'commit', get_commit_minimum(new.repoid, new.head)::jsonb)
            where repoid = new.repoid
                and branch = new.branch
            returning ownerid into _ownerid;

            if found then
            -- default branch updated, so we can update the owners timestamp
            -- to refresh the team list
            update owners
            set updatestamp=now()
            where ownerid=_ownerid;
            end if;

            return null;
        end;
        $$ language plpgsql;

        create trigger branch_update after update on branches
        for each row
        when (new.head is distinct from old.head)
        execute procedure branches_update();
    """
    )
