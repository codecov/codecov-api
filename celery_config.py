from utils.config import get_config


broker_url = get_config('services', 'celery_broker') or get_config('services', 'redis_url')
result_backend = get_config('services', 'redis_url')

task_default_queue = 'new_tasks'
