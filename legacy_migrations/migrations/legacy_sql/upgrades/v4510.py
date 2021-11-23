# v4.5.10
def run_sql(schema_editor):
    schema_editor.execute(
        """
        alter table owners add column root_parent_service_id text;
    """
    )
