def run_sql(schema_editor):
    schema_editor.execute(
        """
        create table commits(
            commitid                text not null,
            id                      bigserial primary key,
            timestamp               timestamp not null,
            repoid                  int references repos on delete cascade not null,
            branch                  text,
            pullid                  int,
            author                  int references owners on delete set null,
            ci_passed               boolean,
            updatestamp             timestamp,
            message                 text,
            state                   commit_state,
            merged                  boolean,
            deleted                 boolean,
            notified                boolean,
            version                 smallint,  -- will be removed after migrations
            parent                  text,
            totals                  jsonb,
            report                  jsonb
        );

        create unique index commits_repoid_commitid on commits (repoid, commitid);

        create index commits_repoid_timestamp_desc on commits (repoid, timestamp desc);

        create index commits_on_pull on commits (repoid, pullid) where deleted is not true;
    """
    )
