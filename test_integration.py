# test_integration.py
from uuid import uuid4

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_api_list_courses_returns_array():
    """Интеграционный тест 1: список курсов возвращается и это массив."""
    response = client.get("/api/courses")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    # в демо у нас всегда есть хотя бы 1 курс
    assert len(data) >= 1
    assert "title" in data[0]


def test_api_create_course_and_get_by_id():
    """Интеграционный тест 2: создаём курс и получаем его по id."""
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


def test_api_update_course_changes_fields():
    """Интеграционный тест 3: обновление курса через PUT меняет поля."""
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


def test_api_delete_course_removes_it():
    """Интеграционный тест 4: удаление курса через API."""
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
