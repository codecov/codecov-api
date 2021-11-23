def run_sql(schema_editor):
    schema_editor.execute(
        """  
        create table branches(
            repoid              int references repos on delete cascade not null,
            updatestamp         timestamptz not null,
            branch              text not null,
            base                text,
            head                text not null,
            authors             int[]
        );

        create index branches_repoid on branches (repoid);

        create unique index branches_repoid_branch on branches (repoid, branch);
    """
    )
