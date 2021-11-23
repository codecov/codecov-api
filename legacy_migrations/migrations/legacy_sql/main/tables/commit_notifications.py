def run_sql(schema_editor):
    schema_editor.execute(
        """
        create table commit_notifications(
            id                    bigserial primary key,
            commit_id             bigint references commits(id) on delete cascade not null,
            notification_type     notifications not null,
            decoration_type       decorations,
            created_at            timestamp,
            updated_at            timestamp,
            state                 commit_notification_state,
            CONSTRAINT commit_notifications_commit_id_notification_type UNIQUE(commit_id, notification_type)
        );

        create index commit_notifications_commit_id on commit_notifications (commit_id);
    """
    )
