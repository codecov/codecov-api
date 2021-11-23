# v4.4.8
def run_sql(schema_editor):
    schema_editor.execute(
        """
        --- transaction friendly enum column upates. See: https://stackoverflow.com/questions/1771543/adding-a-new-value-to-an-existing-enum-type#7834949 --


        -- rename the old enum	-- rename the old enum
        alter type plans rename to plans__;	-- alter type plans rename to plans__;
        -- create the new enum	-- -- create the new enum
        create type plans as enum('5m', '5y', '25m', '25y', '50m', '50y', '100m', '100y', '250m', '250y', '500m', '500y', '1000m', '1000y', '1m', '1y',	-- create type plans as enum('5m', '5y', '25m', '25y', '50m', '50y', '100m', '100y', '250m', '250y', '500m', '500y', '1000m', '1000y', '1m', '1y',
                                'v4-10m', 'v4-10y', 'v4-20m', 'v4-20y', 'v4-50m', 'v4-50y', 'v4-125m', 'v4-125y', 'v4-300m', 'v4-300y',	--                           'v4-10m', 'v4-10y', 'v4-20m', 'v4-20y', 'v4-50m', 'v4-50y', 'v4-125m', 'v4-125y', 'v4-300m', 'v4-300y',
                                'users', 'users-inappm', 'users-inappy', 'users-free');	--                           'users', 'users-inappm', 'users-inappy', 'users-free');
        -- alter all enum columns
        alter table owners	
        alter column plan type plans using plan::text::plans;


        -- drop the old enum
        drop type plans__;	


        ALTER TABLE ONLY owners ALTER COLUMN plan SET DEFAULT 'users-free';	-- ALTER TABLE ONLY owners ALTER COLUMN plan SET DEFAULT 'users-free';
        ALTER TABLE ONLY owners ALTER COLUMN plan_user_count SET DEFAULT 5;	-- ALTER TABLE ONLY owners ALTER COLUMN plan_user_count SET DEFAULT 5;
        ALTER TABLE ONLY owners ALTER COLUMN plan_auto_activate SET DEFAULT true;	-- ALTER TABLE ONLY owners ALTER COLUMN plan_auto_activate SET DEFAULT true;
    """
    )
