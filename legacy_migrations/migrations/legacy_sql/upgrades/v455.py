# v4.5.5
def run_sql(schema_editor):
    schema_editor.execute(
        """
        ALTER TABLE "reports_uploaderror" RENAME COLUMN "report_session_id" TO "upload_id";
        ALTER TABLE "reports_uploadflagmembership" RENAME COLUMN "report_session_id" TO "upload_id";
        ALTER TABLE "reports_sessionleveltotals" RENAME COLUMN "report_session_id" TO "upload_id";

        ALTER TABLE "reports_upload" ADD COLUMN "upload_extras" jsonb NOT NULL;
        ALTER TABLE "reports_upload" ADD COLUMN "upload_type" varchar(100) NOT NULL;

        ALTER TABLE "reports_sessionleveltotals" RENAME TO "reports_uploadleveltotals";
    """
    )
