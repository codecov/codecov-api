# v4.4.10
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
    """
    )
