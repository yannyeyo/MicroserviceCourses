# common/observability.py
import time
import logging
from typing import Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST


# --------- Prometheus метрики ---------

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "method", "path", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["service", "method", "path"],
    # можно подправить корзины, если нужно
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

HTTP_ERRORS_TOTAL = Counter(
    "http_errors_total",
    "Total unhandled exceptions",
    ["service"],
)


class HTTPLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware, которая:
    - логирует каждый запрос в JSON-формате;
    - обновляет Prometheus-метрики.
    """

    def __init__(self, app: FastAPI, service_name: str, logger: logging.Logger):
        super().__init__(app)
        self.service_name = service_name
        self.logger = logger

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        start_time = time.perf_counter()
        method = request.method
        path = request.url.path

        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            # считаем необработанные ошибки
            HTTP_ERRORS_TOTAL.labels(service=self.service_name).inc()
            self.logger.exception(
                "Unhandled exception",
                extra={"path": path, "method": method},
            )
            raise
        finally:
            elapsed = time.perf_counter() - start_time

            # метрики
            HTTP_REQUESTS_TOTAL.labels(
                service=self.service_name,
                method=method,
                path=path,
                status=str(status_code),
            ).inc()

            HTTP_REQUEST_DURATION_SECONDS.labels(
                service=self.service_name,
                method=method,
                path=path,
            ).observe(elapsed)

            # лог
            self.logger.info(
                "HTTP request",
                extra={
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": round(elapsed * 1000, 2),
                },
            )


def setup_metrics_endpoint(app: FastAPI) -> None:
    """
    Регистрирует эндпоинт /metrics для Prometheus.
    """

    @app.get("/metrics")
    async def metrics() -> Response:  # type: ignore[no-redef]
        data = generate_latest()
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)
