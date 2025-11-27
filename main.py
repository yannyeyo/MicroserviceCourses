from uuid import uuid4, UUID
from typing import List, Dict, Optional, Set, Tuple

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

app = FastAPI(title="Learning Courses Microservice")
templates = Jinja2Templates(directory="templates")

# =================== Pydantic-модели ===================

class Course(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    is_published: bool = False


class Lesson(BaseModel):
    id: UUID
    course_id: UUID
    title: str
    content: str
    order: int


class AnswerOption(BaseModel):
    id: UUID
    text: str
    is_correct: bool


class Question(BaseModel):
    id: UUID
    text: str
    options: List[AnswerOption]


class Test(BaseModel):
    id: UUID
    lesson_id: UUID
    title: str
    questions: List[Question]


class TestResult(BaseModel):
    test_id: UUID
    user_id: str
    total_questions: int
    correct_answers: int
    score: float  # 0..100


# =================== "БД" в памяти ===================

courses: Dict[UUID, Course] = {}
lessons: Dict[UUID, Lesson] = {}
tests: Dict[UUID, Test] = {}

# уроки, завершённые пользователем
user_completed_lessons: Dict[str, Set[UUID]] = {}
# курсы, завершённые пользователем
user_completed_courses: Dict[str, Set[UUID]] = {}
# сохранённые результаты тестов: (user_id, test_id) -> результат
test_results: Dict[Tuple[str, UUID], TestResult] = {}


def create_demo_data():
    """Создаём демо-курсы, уроки и тесты при запуске."""
    global courses, lessons, tests

    courses.clear()
    lessons.clear()
    tests.clear()
    user_completed_lessons.clear()
    user_completed_courses.clear()
    test_results.clear()

    # --- Курс 1 ---
    c1_id = uuid4()
    courses[c1_id] = Course(
        id=c1_id,
        title="Python для начинающих",
        description="Основы языка Python",
        is_published=True,
    )

    l1_id = uuid4()
    lessons[l1_id] = Lesson(
        id=l1_id,
        course_id=c1_id,
        title="Введение в Python",
        content="Что такое Python, где используется, установка и первый скрипт.",
        order=1,
    )

    l2_id = uuid4()
    lessons[l2_id] = Lesson(
        id=l2_id,
        course_id=c1_id,
        title="Типы данных и переменные",
        content="Числа, строки, списки, словари. Примеры кода.",
        order=2,
    )

    # Тест к уроку 1
    t1_id = uuid4()
    q1_id = uuid4()
    q1_opts = [
        AnswerOption(id=uuid4(), text="Язык программирования", is_correct=True),
        AnswerOption(id=uuid4(), text="ОС Windows", is_correct=False),
        AnswerOption(id=uuid4(), text="База данных", is_correct=False),
    ]
    tests[t1_id] = Test(
        id=t1_id,
        lesson_id=l1_id,
        title="Тест к уроку 'Введение в Python'",
        questions=[
            Question(
                id=q1_id,
                text="Python — это...",
                options=q1_opts,
            )
        ],
    )

    # Тест к уроку 2
    t2_id = uuid4()
    q2_id = uuid4()
    q2_opts = [
        AnswerOption(id=uuid4(), text="int, float, str, list, dict", is_correct=True),
        AnswerOption(id=uuid4(), text="http, tcp, udp", is_correct=False),
        AnswerOption(id=uuid4(), text="ssd, hdd, ram", is_correct=False),
    ]
    tests[t2_id] = Test(
        id=t2_id,
        lesson_id=l2_id,
        title="Тест к уроку 'Типы данных и переменные'",
        questions=[
            Question(
                id=q2_id,
                text="Какие из перечисленных являются типами данных в Python?",
                options=q2_opts,
            )
        ],
    )

    # --- Курс 2 ---
    c2_id = uuid4()
    courses[c2_id] = Course(
        id=c2_id,
        title="Веб-разработка",
        description="Базовые понятия веба",
        is_published=True,
    )

    l3_id = uuid4()
    lessons[l3_id] = Lesson(
        id=l3_id,
        course_id=c2_id,
        title="Как работает веб",
        content="HTTP, браузер, сервер, запрос-ответ.",
        order=1,
    )

    # Тест к уроку 3
    t3_id = uuid4()
    q3_id = uuid4()
    q3_opts = [
        AnswerOption(id=uuid4(), text="HTTP", is_correct=True),
        AnswerOption(id=uuid4(), text="FTP только", is_correct=False),
        AnswerOption(id=uuid4(), text="BIOS", is_correct=False),
    ]
    tests[t3_id] = Test(
        id=t3_id,
        lesson_id=l3_id,
        title="Тест к уроку 'Как работает веб'",
        questions=[
            Question(
                id=q3_id,
                text="Какой протокол чаще всего используется для веб-сайтов?",
                options=q3_opts,
            )
        ],
    )


@app.on_event("startup")
def startup_event():
    create_demo_data()


# =================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===================

def get_course_or_404(course_id: UUID) -> Course:
    course = courses.get(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")
    return course


def get_lesson_or_404(lesson_id: UUID) -> Lesson:
    lesson = lessons.get(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")
    return lesson


def get_test_for_lesson(lesson_id: UUID) -> Test:
    for t in tests.values():
        if t.lesson_id == lesson_id:
            return t
    raise HTTPException(status_code=404, detail="Тест для урока не найден")


def find_test_for_lesson_or_none(lesson_id: UUID) -> Optional[Test]:
    for t in tests.values():
        if t.lesson_id == lesson_id:
            return t
    return None


def update_course_completion_for_user(user_id: str, course_id: UUID):
    """Если ученик прошёл все уроки курса, помечаем курс как завершённый."""
    course_lesson_ids = {l.id for l in lessons.values() if l.course_id == course_id}
    if not course_lesson_ids:
        return

    completed_lessons = user_completed_lessons.get(user_id, set())
    if course_lesson_ids.issubset(completed_lessons):
        user_courses = user_completed_courses.setdefault(user_id, set())
        user_courses.add(course_id)


DEFAULT_USER = "demo_user"


# =================== UI: список и поиск курсов ===================

@app.get("/", response_class=HTMLResponse)
@app.get("/ui/courses", response_class=HTMLResponse)
async def ui_courses(request: Request, q: Optional[str] = None):
    """Список всех курсов + поиск по названию/описанию."""
    query = (q or "").strip().lower()
    if query:
        filtered = [
            c for c in courses.values()
            if query in (c.title or "").lower()
            or query in (c.description or "").lower()
        ]
    else:
        filtered = list(courses.values())

    return templates.TemplateResponse(
        "courses.html",
        {
            "request": request,
            "courses": filtered,
            "title": "Список курсов",
            "q": q or "",
        },
    )


# =================== UI: просмотр курса, завершение курса ===================

@app.get("/ui/courses/{course_id}", response_class=HTMLResponse)
async def ui_course_detail(
    course_id: UUID,
    request: Request,
    user_id: str = DEFAULT_USER,
):
    """Страница курса с уроками."""
    course = get_course_or_404(course_id)
    course_lessons = sorted(
        [l for l in lessons.values() if l.course_id == course_id],
        key=lambda l: l.order,
    )

    completed_courses = user_completed_courses.get(user_id, set())
    is_completed = course_id in completed_courses

    course_lesson_ids = {l.id for l in course_lessons}
    user_completed = user_completed_lessons.get(user_id, set())
    can_complete_course = bool(course_lesson_ids) and course_lesson_ids.issubset(user_completed)

    return templates.TemplateResponse(
        "course_detail.html",
        {
            "request": request,
            "course": course,
            "lessons": course_lessons,
            "user_id": user_id,
            "title": course.title,
            "is_completed": is_completed,
            "can_complete_course": can_complete_course,
        },
    )


@app.post("/ui/courses/{course_id}/complete")
async def ui_complete_course(
    course_id: UUID,
    request: Request,
    user_id: str = DEFAULT_USER,
):
    """Ученик завершает курс, НО только если все уроки уже пройдены."""
    get_course_or_404(course_id)
    update_course_completion_for_user(user_id, course_id)
    return RedirectResponse(
        url=f"/ui/courses/{course_id}?user_id={user_id}",
        status_code=302,
    )


# =================== UI: уроки ===================

@app.get("/ui/lessons/{lesson_id}", response_class=HTMLResponse)
async def ui_lesson_detail(
    lesson_id: UUID,
    request: Request,
    user_id: str = DEFAULT_USER,
):
    """Страница урока."""
    lesson = get_lesson_or_404(lesson_id)
    course = get_course_or_404(lesson.course_id)

    saved_result = None
    try:
        test = get_test_for_lesson(lesson_id)
        key = (user_id, test.id)
        saved_result = test_results.get(key)
    except HTTPException:
        test = None

    return templates.TemplateResponse(
        "lesson_detail.html",
        {
            "request": request,
            "course": course,
            "lesson": lesson,
            "user_id": user_id,
            "title": lesson.title,
            "saved_result": saved_result,
        },
    )


@app.get("/ui/lessons/{lesson_id}/test", response_class=HTMLResponse)
async def ui_lesson_test(
    lesson_id: UUID,
    request: Request,
    user_id: str = DEFAULT_USER,
):
    """Ученик завершает урок и переходит к тесту."""
    lesson = get_lesson_or_404(lesson_id)
    course = get_course_or_404(lesson.course_id)

    completed = user_completed_lessons.setdefault(user_id, set())
    completed.add(lesson_id)

    update_course_completion_for_user(user_id, course.id)

    test = get_test_for_lesson(lesson_id)

    return templates.TemplateResponse(
        "test_detail.html",
        {
            "request": request,
            "course": course,
            "lesson": lesson,
            "test": test,
            "user_id": user_id,
            "title": test.title,
        },
    )


@app.post("/ui/tests/{test_id}/submit", response_class=HTMLResponse)
async def ui_submit_test(test_id: UUID, request: Request):
    """Обработка результатов теста, сохранение и вывод страницы с результатом."""
    form = await request.form()
    user_id = form.get("user_id", DEFAULT_USER)

    test = tests.get(test_id)
    if not test:
        raise HTTPException(status_code=404, detail="Тест не найден")

    answers_by_question: Dict[UUID, UUID] = {}
    for q in test.questions:
        field_name = f"q_{q.id}"
        option_id_str = form.get(field_name)
        if option_id_str:
            try:
                answers_by_question[q.id] = UUID(option_id_str)
            except ValueError:
                continue

    total_questions = len(test.questions)
    correct = 0

    for q in test.questions:
        selected_option_id = answers_by_question.get(q.id)
        if not selected_option_id:
            continue
        option = next((o for o in q.options if o.id == selected_option_id), None)
        if option and option.is_correct:
            correct += 1

    score = (correct / total_questions) * 100 if total_questions > 0 else 0.0

    result = TestResult(
        test_id=test.id,
        user_id=user_id,
        total_questions=total_questions,
        correct_answers=correct,
        score=score,
    )

    test_results[(user_id, test.id)] = result

    lesson = get_lesson_or_404(test.lesson_id)
    course = get_course_or_404(lesson.course_id)

    return templates.TemplateResponse(
        "test_result.html",
        {
            "request": request,
            "course": course,
            "lesson": lesson,
            "result": result,
            "title": "Результат теста",
        },
    )


# =================== UI: создание / редактирование / удаление курса (преподаватель) ===================

@app.get("/ui/teacher/courses/new", response_class=HTMLResponse)
async def ui_new_course(request: Request):
    return templates.TemplateResponse(
        "course_form.html",
        {
            "request": request,
            "title": "Создание курса",
            "mode": "create",
            "course": None,
        },
    )


@app.post("/ui/teacher/courses/new")
async def ui_new_course_post(request: Request):
    form = await request.form()
    title = (form.get("title") or "").strip()
    description = (form.get("description") or "").strip() or None
    is_published = form.get("is_published") == "on"

    if not title:
        return templates.TemplateResponse(
            "course_form.html",
            {
                "request": request,
                "title": "Создание курса",
                "mode": "create",
                "error": "Название курса обязательно",
                "course": None,
            },
        )

    course_id = uuid4()
    courses[course_id] = Course(
        id=course_id,
        title=title,
        description=description,
        is_published=is_published,
    )

    return RedirectResponse(
        url=f"/ui/courses/{course_id}",
        status_code=302,
    )


@app.get("/ui/teacher/courses/{course_id}/edit", response_class=HTMLResponse)
async def ui_edit_course(course_id: UUID, request: Request):
    course = get_course_or_404(course_id)
    return templates.TemplateResponse(
        "course_form.html",
        {
            "request": request,
            "title": "Редактирование курса",
            "mode": "edit",
            "course": course,
        },
    )


@app.post("/ui/teacher/courses/{course_id}/edit")
async def ui_edit_course_post(course_id: UUID, request: Request):
    course = get_course_or_404(course_id)
    form = await request.form()
    title = (form.get("title") or "").strip()
    description = (form.get("description") or "").strip() or None
    is_published = form.get("is_published") == "on"

    if not title:
        return templates.TemplateResponse(
            "course_form.html",
            {
                "request": request,
                "title": "Редактирование курса",
                "mode": "edit",
                "error": "Название курса обязательно",
                "course": course,
            },
        )

    course.title = title
    course.description = description
    course.is_published = is_published
    courses[course_id] = course

    return RedirectResponse(
        url=f"/ui/courses/{course_id}",
        status_code=302,
    )


@app.post("/ui/teacher/courses/{course_id}/delete")
async def ui_delete_course(course_id: UUID, request: Request):
    get_course_or_404(course_id)

    lesson_ids = [l.id for l in lessons.values() if l.course_id == course_id]
    test_ids = [t.id for t in tests.values() if t.lesson_id in lesson_ids]

    for tid in test_ids:
        tests.pop(tid, None)

    keys_to_delete = [key for key in test_results if key[1] in test_ids]
    for key in keys_to_delete:
        del test_results[key]

    for lid in lesson_ids:
        lessons.pop(lid, None)

    courses.pop(course_id, None)

    for _user, lset in user_completed_lessons.items():
        lset.difference_update(lesson_ids)
    for _user, cset in user_completed_courses.items():
        cset.discard(course_id)

    return RedirectResponse(
        url="/ui/courses",
        status_code=302,
    )


# =================== UI: создание урока (преподаватель) ===================

@app.get("/ui/teacher/courses/{course_id}/lessons/new", response_class=HTMLResponse)
async def ui_new_lesson(course_id: UUID, request: Request):
    course = get_course_or_404(course_id)
    course_lessons = [l for l in lessons.values() if l.course_id == course_id]
    default_order = len(course_lessons) + 1

    return templates.TemplateResponse(
        "lesson_form.html",
        {
            "request": request,
            "title": "Создание урока",
            "course": course,
            "default_order": default_order,
            "error": None,
        },
    )


@app.post("/ui/teacher/courses/{course_id}/lessons/new")
async def ui_new_lesson_post(course_id: UUID, request: Request):
    course = get_course_or_404(course_id)
    form = await request.form()
    title = (form.get("title") or "").strip()
    content = (form.get("content") or "").strip()
    order_str = (form.get("order") or "").strip()

    if not title:
        return templates.TemplateResponse(
            "lesson_form.html",
            {
                "request": request,
                "title": "Создание урока",
                "course": course,
                "default_order": order_str or 1,
                "error": "Название урока обязательно",
            },
        )

    try:
        order = int(order_str) if order_str else 1
    except ValueError:
        order = 1

    lesson_id = uuid4()
    lessons[lesson_id] = Lesson(
        id=lesson_id,
        course_id=course_id,
        title=title,
        content=content,
        order=order,
    )

    return RedirectResponse(
        url=f"/ui/courses/{course_id}",
        status_code=302,
    )


# =================== UI: создание/редактирование теста к уроку (преподаватель) ===================

@app.get("/ui/teacher/lessons/{lesson_id}/test/edit", response_class=HTMLResponse)
async def ui_edit_lesson_test(lesson_id: UUID, request: Request):
    lesson = get_lesson_or_404(lesson_id)
    course = get_course_or_404(lesson.course_id)
    existing = find_test_for_lesson_or_none(lesson_id)

    if existing and existing.questions:
        q = existing.questions[0]
        title = existing.title
        question_text = q.text
        opt1 = q.options[0].text if len(q.options) > 0 else ""
        opt2 = q.options[1].text if len(q.options) > 1 else ""
        opt3 = q.options[2].text if len(q.options) > 2 else ""
        correct_num = 1
        for idx, opt in enumerate(q.options, start=1):
            if opt.is_correct:
                correct_num = idx
                break
    else:
        title = ""
        question_text = ""
        opt1 = ""
        opt2 = ""
        opt3 = ""
        correct_num = 1

    return templates.TemplateResponse(
        "test_form.html",
        {
            "request": request,
            "title": "Тест к уроку",
            "course": course,
            "lesson": lesson,
            "test_title": title,
            "question_text": question_text,
            "opt1": opt1,
            "opt2": opt2,
            "opt3": opt3,
            "correct_num": correct_num,
            "error": None,
        },
    )


@app.post("/ui/teacher/lessons/{lesson_id}/test/edit")
async def ui_edit_lesson_test_post(lesson_id: UUID, request: Request):
    lesson = get_lesson_or_404(lesson_id)
    course = get_course_or_404(lesson.course_id)
    existing = find_test_for_lesson_or_none(lesson_id)

    form = await request.form()
    test_title = (form.get("test_title") or "").strip()
    question_text = (form.get("question_text") or "").strip()
    opt1 = (form.get("opt1") or "").strip()
    opt2 = (form.get("opt2") or "").strip()
    opt3 = (form.get("opt3") or "").strip()
    correct_opt = form.get("correct_opt") or "1"

    if not test_title or not question_text:
        return templates.TemplateResponse(
            "test_form.html",
            {
                "request": request,
                "title": "Тест к уроку",
                "course": course,
                "lesson": lesson,
                "test_title": test_title,
                "question_text": question_text,
                "opt1": opt1,
                "opt2": opt2,
                "opt3": opt3,
                "correct_num": int(correct_opt),
                "error": "Название теста и текст вопроса обязательны",
            },
        )

    option_texts = [opt1, opt2, opt3]
    options: List[AnswerOption] = []
    for idx, text in enumerate(option_texts, start=1):
        if text:
            options.append(
                AnswerOption(
                    id=uuid4(),
                    text=text,
                    is_correct=(str(idx) == correct_opt),
                )
            )

    if len(options) < 2:
        return templates.TemplateResponse(
            "test_form.html",
            {
                "request": request,
                "title": "Тест к уроку",
                "course": course,
                "lesson": lesson,
                "test_title": test_title,
                "question_text": question_text,
                "opt1": opt1,
                "opt2": opt2,
                "opt3": opt3,
                "correct_num": int(correct_opt),
                "error": "Нужно минимум два варианта ответа",
            },
        )

    if existing:
        test_id = existing.id
        keys_to_delete = [key for key in test_results if key[1] == test_id]
        for key in keys_to_delete:
            del test_results[key]
    else:
        test_id = uuid4()

    question = Question(
        id=uuid4(),
        text=question_text,
        options=options,
    )

    tests[test_id] = Test(
        id=test_id,
        lesson_id=lesson_id,
        title=test_title,
        questions=[question],
    )

    return RedirectResponse(
        url=f"/ui/lessons/{lesson_id}",
        status_code=302,
    )
