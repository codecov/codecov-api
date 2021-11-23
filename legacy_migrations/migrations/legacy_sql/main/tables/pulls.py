def run_sql(schema_editor):
    schema_editor.execute(
        """
        create table pulls(
            repoid              int references repos on delete cascade not null,
            pullid              int not null,
            issueid             int,  -- gitlab
            updatestamp         timestamp,
            state               pull_state not null default 'open',
            title               text,
            base                text,
            compared_to         text,
            head                text,
            commentid           text,
            diff                jsonb,
            flare               jsonb, -- only when pull is open
            author              int references owners on delete set null
        );

        create unique index pulls_repoid_pullid on pulls (repoid, pullid);

        create index pulls_repoid_state_open on pulls (repoid) where state = 'open';
    """
    )
