# Generated by Django 4.2.7 on 2024-02-23 19:27

from django.db import migrations, models
import django.db.models.deletion
import psqlextra.backend.migrations.operations.add_default_partition
import psqlextra.backend.migrations.operations.create_partitioned_model
import psqlextra.manager.manager
import psqlextra.models.partitioned
import psqlextra.types


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('reports', '0014_rename_env_test_flags_hash_and_more'),
        ('codecov_auth', '0051_user_customer_intent'),
        ('core', '0047_increment_version'),
    ]

    operations = [
        psqlextra.backend.migrations.operations.create_partitioned_model.PostgresCreatePartitionedModel(
            name='UserMeasurement',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('uploader_used', models.CharField()),
                ('private_repo', models.BooleanField()),
                ('report_type', models.CharField(choices=[('coverage', 'Coverage'), ('test_results', 'Test Results'), ('bundle_analysis', 'Bundle Analysis')], max_length=100, null=True)),
                ('commit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_measurements', to='core.commit')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_measurements', to='codecov_auth.owner')),
                ('repo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_measurements', to='core.repository')),
                ('upload', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_measurements', to='reports.reportsession')),
            ],
            options={
                'db_table': 'user_measurements',
                'indexes': [models.Index(fields=['owner'], name='i_owner'), models.Index(fields=['owner', 'repo'], name='owner_repo'), models.Index(fields=['owner', 'private_repo'], name='owner_private_repo'), models.Index(fields=['owner', 'private_repo', 'report_type'], name='owner_private_repo_report_type')],
            },
            partitioning_options={
                'method': psqlextra.types.PostgresPartitioningMethod['RANGE'],
                'key': ['created_at'],
            },
            bases=(psqlextra.models.partitioned.PostgresPartitionedModel,),
            managers=[
                ('objects', psqlextra.manager.manager.PostgresManager()),
            ],
        ),
        psqlextra.backend.migrations.operations.add_default_partition.PostgresAddDefaultPartition(
            model_name='UserMeasurement',
            name='default',
        ),
    ]
