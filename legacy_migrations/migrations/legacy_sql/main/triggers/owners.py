def run_sql(schema_editor):
    schema_editor.execute(
        """
        create or replace function owner_yaml_updated() returns trigger as $$
        begin
            if (new.yaml->'codecov'->'bot')::citext is distinct from 'null' then
            new.bot = coalesce(
                get_ownerid_if_member(
                new.service,
                (new.yaml->'codecov'->>'bot')::citext,
                new.ownerid
                ),
                old.bot
            );
            else
                new.bot = null;
            end if;

            -- update repo branches
            update repos r
            set branch = coalesce((r.yaml->'codecov'->>'branch'), (new.yaml->'codecov'->>'branch'), branch)
            where ownerid = new.ownerid;

            return new;
        end;
        $$ language plpgsql;

        create trigger owner_yaml_updated before update on owners
        for each row
        when (
            ((new.yaml->'codecov'->>'bot')::text is distinct from (old.yaml->'codecov'->>'bot')::text)
            or ((new.yaml->'codecov'->>'branch')::text is distinct from (old.yaml->'codecov'->>'branch')::text)
        )
        execute procedure owner_yaml_updated();


        create or replace function owner_cache_state_update() returns trigger as $$
        declare _ownerid int;
        begin
            -- update cache of number of repos
            for _ownerid in (select unnest from unnest(new.organizations)) loop
            update owners o
                set cache=update_json(cache, 'stats', update_json(cache->'stats', 'users', (select count(*)
                                                                                            from owners
                                                                                            where organizations @> array[_ownerid])::int))
                where ownerid=_ownerid;
            end loop;
            return null;
        end;
        $$ language plpgsql;

        create trigger owner_cache_state_update after update on owners
        for each row
        when (new.organizations is distinct from old.organizations)
        execute procedure owner_cache_state_update();

        create trigger owner_cache_state_insert after insert on owners
        for each row
        execute procedure owner_cache_state_update();

        -- clear the user sessions when the token is set to null, requiring login
        create or replace function owner_token_clered() returns trigger as $$
        begin
            delete from sessions where ownerid=new.ownerid and type='login';
            return new;
        end;
        $$ language plpgsql;

        create trigger owner_token_clered after update on owners
        for each row
        when (new.oauth_token is distinct from old.oauth_token and new.oauth_token is null)
        execute procedure owner_token_clered();


        create or replace function owners_before_insert_or_update() returns trigger as $$
        begin
            -- user has changed name or deleted and invalidate sessions
            with _owners as (update owners
                            set username = null
                            where service = new.service
                            and username = new.username::citext
                            returning ownerid)
            delete from sessions where ownerid in (select ownerid from _owners);
            return new;
        end;
        $$ language plpgsql;

        create trigger owners_before_insert before insert on owners
        for each row
        execute procedure owners_before_insert_or_update();

        create trigger owners_before_update before update on owners
        for each row
        when (new.username is not null and new.username is distinct from old.username)
        execute procedure owners_before_insert_or_update();
    """
    )
