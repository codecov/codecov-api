def run_sql(schema_editor):
    schema_editor.execute(
        """        
        create table repos(
            repoid                  serial primary key,
            ownerid                 int references owners on delete cascade not null,
            service_id              text not null,
            name                    citext,
            private                 boolean not null,
            branch                  text default 'master' not null,
            upload_token            uuid unique default uuid_generate_v4(),
            image_token             text default random_string(10),
            updatestamp             timestamptz,
            language                languages,
            active                  boolean,
            deleted                 boolean default false not null,
            activated               boolean default false,
            bot                     int references owners on delete set null,
            yaml                    jsonb,
            cache                   jsonb,  -- {"totals": {}, "trends": [], "commit": {}, "yaml": ""}
            hookid                  text,
            using_integration       boolean  -- using github integration
        );

        create unique index repos_slug on repos (ownerid, name);

        create unique index repos_service_ids on repos (ownerid, service_id);

        alter table repos add column forkid int references repos;
    """
    )
