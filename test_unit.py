# test_unit.py
import pytest
from uuid import uuid4

import main


@pytest.fixture(autouse=True)
def clean_state():
    """
    Перед каждым тестом чистим глобальные структуры,
    чтобы тесты не мешали друг другу.
    """
    main.lessons.clear()
    main.courses.clear()
    main.user_completed_lessons.clear()
    main.user_completed_courses.clear()
    yield
    main.lessons.clear()
    main.courses.clear()
    main.user_completed_lessons.clear()
    main.user_completed_courses.clear()


def test_update_course_completion_marks_course_when_all_lessons_completed():
    """Юнит-тест 1: курс помечается завершённым, если все уроки пройдены."""
    user_id = "user1"
    course_id = uuid4()

    # создаём 2 урока курса
    l1_id = uuid4()
    l2_id = uuid4()
    main.lessons[l1_id] = main.Lesson(
        id=l1_id, course_id=course_id, title="Урок 1", content="...", order=1
    )
    main.lessons[l2_id] = main.Lesson(
        id=l2_id, course_id=course_id, title="Урок 2", content="...", order=2
    )

    # пользователь прошёл оба урока
    main.user_completed_lessons[user_id] = {l1_id, l2_id}

    # вызываем логику
    main.update_course_completion_for_user(user_id, course_id)

    assert course_id in main.user_completed_courses[user_id]


def test_update_course_completion_not_mark_when_not_all_completed():
    """Юнит-тест 2: курс НЕ считается завершённым, если не все уроки пройдены."""
    user_id = "user2"
    course_id = uuid4()

    l1_id = uuid4()
    l2_id = uuid4()
    main.lessons[l1_id] = main.Lesson(
        id=l1_id, course_id=course_id, title="Урок 1", content="...", order=1
    )
    main.lessons[l2_id] = main.Lesson(
        id=l2_id, course_id=course_id, title="Урок 2", content="...", order=2
    )

    # пользователь прошёл только один урок
    main.user_completed_lessons[user_id] = {l1_id}

    main.update_course_completion_for_user(user_id, course_id)

    assert course_id not in main.user_completed_courses.get(user_id, set())


def test_get_course_or_404_returns_course():
    """Юнит-тест 3: get_course_or_404 возвращает курс, если он есть."""
    course_id = uuid4()
    course = main.Course(
        id=course_id,
        title="Тестовый курс",
        description="Описание",
        is_published=True,
    )
    main.courses[course_id] = course

    result = main.get_course_or_404(course_id)

    assert result.id == course_id
    assert result.title == "Тестовый курс"


def test_get_course_or_404_raises_when_not_found():
    """Юнит-тест 4: get_course_or_404 кидает 404, если курса нет."""
    from fastapi import HTTPException

    unknown_id = uuid4()

    with pytest.raises(HTTPException) as exc_info:
        main.get_course_or_404(unknown_id)

    assert exc_info.value.status_code == 404
    assert "Курс не найден" in exc_info.value.detail
