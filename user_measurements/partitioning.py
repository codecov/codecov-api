from dateutil.relativedelta import relativedelta

from psqlextra.partitioning import (
    PostgresPartitioningManager,
    PostgresCurrentTimePartitioningStrategy,
    PostgresTimePartitionSize,
)
from psqlextra.partitioning.config import PostgresPartitioningConfig
from user_measurements.models import UserMeasurement

manager = PostgresPartitioningManager([
    # 3 partitions ahead, each partition is one month
    # delete partitions older than 6 months
    # partitions will be named `[table_name]_[year]_[3-letter month name]`.
    PostgresPartitioningConfig(
        model=UserMeasurement,
        strategy=PostgresCurrentTimePartitioningStrategy(
            size=PostgresTimePartitionSize(months=1),
            count=3,
            max_age=relativedelta(months=6),
        ),
    ),
])