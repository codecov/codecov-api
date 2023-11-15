from logging import Filter

from pythonjsonlogger.jsonlogger import JsonFormatter, merge_record_extra
from sentry_sdk import Hub


class BaseLogger(JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(BaseLogger, self).add_fields(log_record, record, message_dict)


class CustomLocalJsonFormatter(BaseLogger):
    def jsonify_log_record(self, log_record):
        """Returns a json string of the log record."""
        levelname = log_record.pop("levelname")
        message = log_record.pop("message")
        exc_info = log_record.pop("exc_info", "")
        content = super().jsonify_log_record(log_record)
        if exc_info:
            return f"{levelname}: {message} --- {content}\n{exc_info}"
        return f"{levelname}: {message} --- {content}"


class CustomDatadogJsonFormatter(BaseLogger):
    def add_fields(self, log_record, record, message_dict):
        super(CustomDatadogJsonFormatter, self).add_fields(
            log_record, record, message_dict
        )
        if not log_record.get("logger.name") and log_record.get("name"):
            log_record["logger.name"] = log_record.get("name")
        if not log_record.get("logger.thread_name") and log_record.get("threadName"):
            log_record["logger.thread_name"] = log_record.get("threadName")
        if log_record.get("level"):
            log_record["level"] = log_record["level"].upper()
        else:
            log_record["level"] = record.levelname

        span = Hub.current.scope.span
        if span and span.trace_id:
            log_record["sentry_trace_id"] = span.trace_id


class CustomGunicornLogFormatter(JsonFormatter):
    rename_fields = {
        "levelname": "level",
        "r": "request",
        "a": "useragent",
        "f": "referer",  # the biggest concern in my mind: should this be correctly spelled historically (one r) or correctly spelled linguistically (two r)
        "b": "response_length",
        "h": "remote_address",
        "t": "request_time",
        "s": "status_code",
    }

    def add_fields(self, log_record, record, message_dict):
        super(CustomGunicornLogFormatter, self).add_fields(
            log_record, record, message_dict
        )
        for field in self._required_fields:
            if field in self.rename_fields:
                log_record[self.rename_fields[field]] = record.args.get(field)
                del log_record[field]
            else:
                log_record[field] = record.args.get(field)


class HealthCheckFilter(Filter):
    def filter(self, record):
        # Ignore /health/ requests, unless it's not a 200.
        return (
            ("GET /health/" not in record.getMessage())
            if record.args.get("s") != "200"
            else True
        )
