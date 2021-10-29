# v4.5.2
def run_sql(schema_editor):
    schema_editor.execute(
        """
        ALTER TABLE commits ADD COLUMN id bigint;
        COMMIT;
        -- EOF
        CREATE SEQUENCE commits_id_seq OWNED BY commits.id;
        COMMIT;
        -- EOF
        ALTER TABLE commits ALTER COLUMN id SET DEFAULT nextval('commits_id_seq');
        COMMIT;
    """
    )
