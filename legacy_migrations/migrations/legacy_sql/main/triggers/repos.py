def run_sql(schema_editor):
    schema_editor.execute(
        """
        create or replace function repo_yaml_update() returns trigger as $$
        declare _service service;
        declare _branch text;
        begin
            select service, (yaml->'codecov'->>'branch') into _service, _branch
            from owners
            where ownerid=new.ownerid
            limit 1;

            -- update repo bot and branch
            update repos
            set bot = case when (yaml->'codecov'->>'bot') is not null
                            then coalesce(get_ownerid_if_member(_service, (yaml->'codecov'->>'bot')::citext, ownerid), bot)
                            else null end,
                branch = coalesce((yaml->'codecov'->>'branch'), _branch, branch)
            where repoid=new.repoid;
            return null;
        end;
        $$ language plpgsql;

        create trigger repo_yaml_update after update on repos
        for each row
        when (
            ((new.yaml->'codecov'->>'bot')::text is distinct from (old.yaml->'codecov'->>'bot')::text)
            or ((new.yaml->'codecov'->>'branch')::text is distinct from (old.yaml->'codecov'->>'branch')::text)
        )
        execute procedure repo_yaml_update();


        create or replace function repo_cache_state_update() returns trigger as $$
        begin
            -- update cache of number of repos
            update owners o
            set cache=update_json(cache, 'stats', update_json(cache->'stats', 'repos', (select count(*) from repos r where r.ownerid=o.ownerid and active)::int)),
                updatestamp=now()
            where ownerid=new.ownerid;
            return null;
        end;
        $$ language plpgsql;

        create trigger repo_cache_state_update after update on repos
        for each row
        when (new.active is distinct from old.active)
        execute procedure repo_cache_state_update();


        create or replace function repos_before_insert_or_update() returns trigger as $$
        begin
            -- repo name changed or deleted
            update repos
            set name = null,
                deleted = true,
                active = false,
                activated = false
            where ownerid = new.ownerid
            and name = new.name;
            return new;
        end;
        $$ language plpgsql;

        create trigger repos_before_insert before insert on repos
        for each row
        execute procedure repos_before_insert_or_update();

        create trigger repos_before_update before update on repos
        for each row
        when (new.name is not null and new.name is distinct from old.name)
        execute procedure repos_before_insert_or_update();
    """
    )
