# v4.4.7
def run_sql(schema_editor):
    schema_editor.execute(
        """
        drop trigger repo_yaml_update on repos;
        drop trigger owner_yaml_updated on owners;

        create trigger repo_yaml_update after update on repos
        for each row
        when (
            ((new.yaml->'codecov'->>'bot')::text is distinct from (old.yaml->'codecov'->>'bot')::text)
            or ((new.yaml->'codecov'->>'branch')::text is distinct from (old.yaml->'codecov'->>'branch')::text)
        )
        execute procedure repo_yaml_update();


        create trigger owner_yaml_updated before update on owners
        for each row
        when (
            ((new.yaml->'codecov'->>'bot')::text is distinct from (old.yaml->'codecov'->>'bot')::text)
            or ((new.yaml->'codecov'->>'branch')::text is distinct from (old.yaml->'codecov'->>'branch')::text)
        )
        execute procedure owner_yaml_updated();
    """
    )
