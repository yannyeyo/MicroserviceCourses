# test_integration.py
from uuid import uuid4

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)

def _get_metric_value(text: str, metric_name: str, labels: dict) -> float:
    """
    Находит значение метрики Prometheus по имени и набору labels.
    Если не найдена — возвращает 0.0.
    """
    for line in text.splitlines():
        if not line.startswith(metric_name):
            continue
        if all(f'{k}="{v}"' in line for k, v in labels.items()):
            # формат строки: http_requests_total{...} 3.0
            try:
                return float(line.split()[-1])
            except ValueError:
                return 0.0
    return 0.0

#   Интеграционный тест 1: список курсов возвращается и это массив.
def test_api_list_courses_returns_array():
    response = client.get("/api/courses")
    assert response.status_code == 200

    data = response.json()
    # важно, что это именно список (может быть пустым)
    assert isinstance(data, list)

#   Интеграционный тест 2: создаём курс и получаем его по id.
def test_api_create_course_and_get_by_id():
    payload = {
        "title": "API курс интеграционный",
        "description": "Проверка создания и получения курса",
        "is_published": True
    }

    # создаём курс
    create_resp = client.post("/api/courses", json=payload)
    assert create_resp.status_code == 201
    created = create_resp.json()
    course_id = created["id"]

    # получаем по id
    get_resp = client.get(f"/api/courses/{course_id}")
    assert get_resp.status_code == 200
    got = get_resp.json()

    assert got["id"] == course_id
    assert got["title"] == payload["title"]
    assert got["description"] == payload["description"]
    assert got["is_published"] is True

#   Интеграционный тест 3: обновление курса через PUT меняет поля.
def test_api_update_course_changes_fields():
    # сначала создаём курс
    create_resp = client.post(
        "/api/courses",
        json={
            "title": "Старое название",
            "description": "Старое описание",
            "is_published": False
        },
    )
    assert create_resp.status_code == 201
    course_id = create_resp.json()["id"]

    # обновляем
    update_payload = {
        "title": "Новое название",
        "description": "Новое описание",
        "is_published": True
    }
    update_resp = client.put(f"/api/courses/{course_id}", json=update_payload)
    assert update_resp.status_code == 200

    updated = update_resp.json()
    assert updated["title"] == "Новое название"
    assert updated["description"] == "Новое описание"
    assert updated["is_published"] is True

#   Интеграционный тест 4: удаление курса через API.
def test_api_delete_course_removes_it():
    # создаём курс
    create_resp = client.post(
        "/api/courses",
        json={
            "title": "Курс на удаление",
            "description": "Этот курс будет удалён",
            "is_published": False
        },
    )
    assert create_resp.status_code == 201
    course_id = create_resp.json()["id"]

    # удаляем
    del_resp = client.delete(f"/api/courses/{course_id}")
    assert del_resp.status_code == 204

    # проверяем, что теперь 404
    get_resp = client.get(f"/api/courses/{course_id}")
    assert get_resp.status_code == 404

# Метрики доступны по /metrics и содержат наши http_* метрики
def test_metrics_endpoint_exists_and_contains_http_metrics():
    resp = client.get("/metrics")
    assert resp.status_code == 200

    body = resp.text
    # проверяем, что есть нужные метрики
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body

#  Значение http_requests_total для GET /api/courses увеличивается осле нескольких запросов
def test_http_requests_total_increases_after_requests():

    # Считаем текущее значение
    before_resp = client.get("/metrics")
    before = _get_metric_value(
        before_resp.text,
        "http_requests_total",
        {
            "service": "course-service",
            "method": "GET",
            "path": "/api/courses",
            "status": "200",
        },
    )

    # Делаем несколько запросов к /api/courses
    N = 3
    for _ in range(N):
        r = client.get("/api/courses")
        assert r.status_code == 200

    # Смотрим метрики ещё раз
    after_resp = client.get("/metrics")
    after = _get_metric_value(
        after_resp.text,
        "http_requests_total",
        {
            "service": "course-service",
            "method": "GET",
            "path": "/api/courses",
            "status": "200",
        },
    )

    # Значение должно увеличиться хотя бы на N
    # (другие тесты тоже могут что-то добавить, поэтому >=)
    assert after >= before + N
