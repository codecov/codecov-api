def run_sql(schema_editor):
    schema_editor.execute(
        """        
        create table sessions(
            sessionid               serial primary key,
            token                   uuid unique default uuid_generate_v4() not null,
            name                    text,
            ownerid                 int references owners on delete cascade not null,
            type                    sessiontype not null,
            lastseen                timestamptz,
            useragent               text,
            ip                      text
        );
    """
    )
