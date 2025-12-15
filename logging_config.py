# common/logging_config.py
import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Форматер, который пишет логи в JSON для Loki."""

    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": self.service_name,
            "message": record.getMessage(),
        }

        # добавляем стандартные поля, если они есть
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        # всё, что передали через extra=...
        for key, value in record.__dict__.items():
            if key.startswith("_"):
                continue
            if key in log_record:
                continue
            # отфильтруем стандартные поля LogRecord
            if key in {
                "name", "msg", "args", "levelname", "levelno",
                "pathname", "filename", "module", "exc_info",
                "exc_text", "stack_info", "lineno", "funcName",
                "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process"
            }:
                continue
            log_record[key] = value

        return json.dumps(log_record, ensure_ascii=False)


def setup_logging(service_name: str) -> logging.Logger:
    """
    Создаёт логгер сервиса с JSON-форматом и выводом в stdout.
    Loki + Promtail будут забирать логи из stdout контейнера.
    """
    logger = logging.getLogger(service_name)

    if logger.handlers:
        # уже настроен
        return logger

    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter(service_name))

    logger.addHandler(handler)
    logger.propagate = False

    # чуть заглушим болтливые сторонние библиотеки
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    return logger
