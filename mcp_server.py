import asyncio
import re
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP
from canvas_client import CanvasClient
from token_manager import token_manager

mcp = FastMCP(
    name="canvas-lms-espol",
    description="Servidor MCP para Canvas LMS de la ESPOL",
    streamable_http_path="/",
)


async def _client(canvas_token: str) -> CanvasClient:
    active_token = await token_manager.get_active_token(canvas_token)
    return CanvasClient(active_token)


@mcp.tool()
def get_current_datetime() -> str:
    """
    Retorna la fecha y hora actual del servidor en zona horaria UTC y en hora de Ecuador (UTC-5).

    Úsala SIEMPRE antes de responder preguntas que mencionen "hoy", "mañana", "esta semana",
    "próximos días" o cualquier referencia temporal relativa.
    """
    now_utc = datetime.now(timezone.utc)
    # Ecuador es UTC-5
    from datetime import timedelta
    now_ec = now_utc - timedelta(hours=5)
    return (
        f"Fecha y hora actual:\n"
        f"- UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"- Ecuador (UTC-5): {now_ec.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"- Fecha de hoy (Ecuador): {now_ec.strftime('%Y-%m-%d')}\n"
        f"- ISO para filtros: inicio del día = {now_ec.strftime('%Y-%m-%d')}T00:00:00, "
        f"fin del día = {now_ec.strftime('%Y-%m-%d')}T23:59:59"
    )


@mcp.tool()
async def get_current_user(canvas_token: str) -> str:
    """
    Obtiene el perfil del usuario actualmente autenticado.

    Args:
        canvas_token: Token de autenticación Canvas del usuario (variable api-aula).
    """
    async with (await _client(canvas_token)) as canvas:
        u = await canvas.get_current_user()
    name = u.get("name", "Desconocido")
    login = u.get("login_id") or u.get("primary_email") or "no disponible"
    uid = u.get("id", "?")
    return f"El usuario autenticado es **{name}** (ID: {uid}, login: {login})."


@mcp.tool()
async def get_courses(canvas_token: str, enrollment_type: str = "") -> str:
    """
    Lista los cursos del usuario autenticado.

    Args:
        canvas_token: Token de autenticación Canvas del usuario (variable api-aula).
        enrollment_type: Filtrar por tipo de matrícula. Valores: student, teacher, ta, observer, designer. Dejar vacío para todos.
    """
    async with (await _client(canvas_token)) as canvas:
        courses = await canvas.get_courses(enrollment_type or None)
    if not courses:
        return "No se encontraron cursos para este usuario."
    lines = [f"Se encontraron {len(courses)} curso(s):\n"]
    for c in courses:
        name = c.get("name") or c.get("course_code") or "Sin nombre"
        lines.append(f"- **{name}** (ID: {c.get('id')})")
    return "\n".join(lines)


@mcp.tool()
async def get_course(canvas_token: str, course_id: int) -> str:
    """
    Obtiene el detalle de un curso.

    Args:
        canvas_token: Token de autenticación Canvas del usuario (variable api-aula).
        course_id: ID numérico del curso.
    """
    async with (await _client(canvas_token)) as canvas:
        c = await canvas.get_course(course_id)
    name = c.get("name") or c.get("course_code") or "Sin nombre"
    code = c.get("course_code", "N/A")
    start = c.get("start_at") or "no especificada"
    end = c.get("end_at") or "no especificada"
    workflow = c.get("workflow_state", "desconocido")
    return (
        f"**{name}**\n"
        f"- Código: {code}\n"
        f"- Estado: {workflow}\n"
        f"- Inicio: {start}\n"
        f"- Fin: {end}"
    )


@mcp.tool()
async def get_assignments(
    canvas_token: str,
    course_ids: list[int] | None = None,
    days_ahead: int | None = 7,
    per_page: int = 20
):
    """
    📚 Obtiene tareas pendientes de cursos activos.

    Si no se especifican cursos, se consultarán automáticamente los cursos activos del usuario.
    ES PREFERIBLE MANDAR NONE PARA OBTENER LAS TAREAS DE TODOS LOS CURSOS PORQUE ES MAS EFICIENTE.

    Args:
        canvas_token: Token de autenticación Canvas del usuario (variable api-aula).
    """
    async with (await _client(canvas_token)) as canvas:
        return await canvas.get_assignments(
            course_ids=course_ids,
            days_ahead=days_ahead,
            per_page=per_page
        )


@mcp.tool()
async def get_assignment(canvas_token: str, course_id: int, assignment_id: int) -> str:
    """
    Obtiene el detalle de una asignación específica.

    Args:
        canvas_token: Token de autenticación Canvas del usuario (variable api-aula).
        course_id: ID del curso.
        assignment_id: ID de la asignación.
    """
    async with (await _client(canvas_token)) as canvas:
        a = await canvas.get_assignment(course_id, assignment_id)
    due = a.get("due_at") or "sin fecha límite"
    pts = a.get("points_possible")
    pts_str = f"{pts} puntos" if pts is not None else "sin puntaje definido"
    desc = a.get("description") or "sin descripción"
    desc = re.sub(r"<[^>]+>", " ", desc).strip()
    desc = desc[:300] + "..." if len(desc) > 300 else desc
    return (
        f"**{a.get('name')}** (ID: {a.get('id')})\n"
        f"- Fecha límite: {due}\n"
        f"- Puntaje: {pts_str}\n"
        f"- Descripción: {desc}"
    )


@mcp.tool()
async def get_submissions(canvas_token: str, course_id: int, assignment_id: int) -> str:
    """
    Lista las entregas de los estudiantes para una asignación.

    Args:
        canvas_token: Token de autenticación Canvas del usuario (variable api-aula).
        course_id: ID del curso.
        assignment_id: ID de la asignación.
    """
    async with (await _client(canvas_token)) as canvas:
        subs = await canvas.get_submissions(course_id, assignment_id)
    if not subs:
        return "No hay entregas registradas para esta asignación."
    total = len(subs)
    submitted = sum(1 for s in subs if s.get("workflow_state") not in ("unsubmitted", None))
    lines = [f"**{submitted} de {total}** estudiante(s) han entregado:\n"]
    for s in subs:
        user = s.get("user", {})
        nombre = user.get("name", f"ID {s.get('user_id')}")
        state = s.get("workflow_state", "desconocido")
        score = s.get("score")
        score_str = f"Nota: {score}" if score is not None else "sin calificar"
        lines.append(f"- {nombre} — Estado: {state} — {score_str}")
    return "\n".join(lines)


@mcp.tool()
async def get_students(canvas_token: str, course_id: int) -> str:
    """
    Lista los estudiantes matriculados en un curso.

    Args:
        canvas_token: Token de autenticación Canvas del usuario (variable api-aula).
        course_id: ID del curso.
    """
    async with (await _client(canvas_token)) as canvas:
        students = await canvas.get_students(course_id)
    if not students:
        return "No se encontraron estudiantes matriculados en este curso."
    lines = [f"El curso tiene **{len(students)}** estudiante(s) matriculado(s):\n"]
    for s in students:
        lines.append(f"- {s.get('name', 'Sin nombre')} (ID: {s.get('id')})")
    return "\n".join(lines)


@mcp.tool()
async def get_enrollments(canvas_token: str, course_id: int) -> str:
    """
    Lista todas las matrículas de un curso (estudiantes, profesores, etc).

    Args:
        canvas_token: Token de autenticación Canvas del usuario (variable api-aula).
        course_id: ID del curso.
    """
    async with (await _client(canvas_token)) as canvas:
        enrollments = await canvas.get_enrollments(course_id)
    if not enrollments:
        return "No se encontraron matrículas para este curso."
    lines = [f"El curso tiene **{len(enrollments)}** matrícula(s):\n"]
    for e in enrollments:
        nombre = e.get("user", {}).get("name", f"ID {e.get('user_id')}")
        role = e.get("type", "desconocido")
        lines.append(f"- {nombre} — Rol: {role}")
    return "\n".join(lines)


@mcp.tool()
async def get_modules(canvas_token: str, course_id: int) -> str:
    """
    Lista los módulos de contenido de un curso.

    Args:
        canvas_token: Token de autenticación Canvas del usuario (variable api-aula).
        course_id: ID del curso.
    """
    async with (await _client(canvas_token)) as canvas:
        modules = await canvas.get_modules(course_id)
    if not modules:
        return "Este curso no tiene módulos de contenido."
    lines = [f"El curso tiene **{len(modules)}** módulo(s):\n"]
    for m in modules:
        items = m.get("items_count", "?")
        state = "publicado" if m.get("published") else "no publicado"
        lines.append(f"- **{m.get('name')}** (ID: {m.get('id')}) — {items} ítem(s) — {state}")
    return "\n".join(lines)


@mcp.tool()
async def get_announcements(
    canvas_token: str,
    course_ids: list[int] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    latest_only: bool = False,
    active_only: bool = True,
    per_page: int = 20
) -> str:
    """
    📢 Obtiene novedades académicas de Canvas LMS.

    La respuesta mezcla anuncios, tareas próximas y quizzes próximos en una sola línea
    temporal ordenada cronológicamente. Cada elemento incluye un campo type:
    announcement | assignment

    IMPORTANTE: Las tareas también deben mostrarse al usuario como parte de las novedades.

    IMPORTANTE: Si el usuario pregunta por "hoy", "mañana" o cualquier fecha relativa,
    llama PRIMERO a get_current_datetime para conocer la fecha real antes de usar este tool.

    Args:
        canvas_token: Token de autenticación Canvas del usuario (variable api-aula).
        start_date: Fecha de inicio en formato ISO (YYYY-MM-DD o YYYY-MM-DDTHH:MM:SS). Opcional.
        end_date: Fecha de fin en formato ISO. Opcional.
    """
    DEFAULT_DAYS_AHEAD = 7
    days_ahead = DEFAULT_DAYS_AHEAD
    if start_date and end_date:
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        days_ahead = max((end - start).days, 1)

    async with (await _client(canvas_token)) as canvas:
        active_courses = await canvas.get_active_course_ids()
        ann_response, assignments_response = await asyncio.gather(
            canvas.get_announcements(
                course_ids=course_ids,
                active_courses=active_courses,
                start_date=start_date,
                end_date=end_date,
                latest_only=latest_only,
                active_only=active_only,
                per_page=per_page,
            ),
            canvas.get_assignments(
                course_ids=course_ids,
                active_courses=active_courses,
                days_ahead=days_ahead,
                per_page=per_page,
            ),
        )

    combined = []
    combined_courses = [*ann_response["course_names"], *assignments_response["course_names"]]
    for a in ann_response["announcements"]:
        combined.append({
            "type": "announcement",
            "course_id": a.get("context_code"),
            "title": a.get("title"),
            "message": a.get("message"),
            "date": a.get("posted_at") or a.get("created_at"),
        })
    for a in assignments_response["assignments"]:
        combined.append({
            "type": "assignment",
            "course_id": a.get("course_id"),
            "title": a.get("name"),
            "message": a.get("description"),
            "date": a.get("due_at"),
            "points": a.get("points_possible"),
        })
    combined.sort(
        key=lambda x: (
            x.get("date") is None,
            x.get("date") or "9999-12-31T23:59:59Z",
        )
    )
    return {
        "updates": combined,
        "course_names": combined_courses,
    }


@mcp.tool()
async def get_discussions(canvas_token: str, course_id: int) -> str:
    """
    Lista los foros de discusión de un curso.

    Args:
        canvas_token: Token de autenticación Canvas del usuario (variable api-aula).
        course_id: ID del curso.
    """
    async with (await _client(canvas_token)) as canvas:
        discussions = await canvas.get_discussions(course_id)
    if not discussions:
        return "Este curso no tiene foros de discusión."
    lines = [f"El curso tiene **{len(discussions)}** foro(s) de discusión:\n"]
    for d in discussions:
        replies = d.get("discussion_subentry_count", 0)
        state = "publicado" if d.get("published") else "no publicado"
        lines.append(f"- **{d.get('title')}** (ID: {d.get('id')}) — {replies} respuesta(s) — {state}")
    return "\n".join(lines)


@mcp.tool()
async def get_student_grades(canvas_token: str, course_id: int, student_id: int) -> str:
    """
    Obtiene las notas de un estudiante en un curso.

    Args:
        canvas_token: Token de autenticación Canvas del usuario (variable api-aula).
        course_id: ID del curso.
        student_id: ID del estudiante.
    """
    async with (await _client(canvas_token)) as canvas:
        enrollments = await canvas.get_grades(course_id, student_id)
    if not enrollments:
        return "No se encontraron calificaciones para este estudiante en el curso."
    lines = []
    for e in enrollments:
        nombre = e.get("user", {}).get("name", f"ID {student_id}")
        grades = e.get("grades", {})
        current = grades.get("current_score", "N/A")
        final = grades.get("final_score", "N/A")
        current_grade = grades.get("current_grade", "")
        lines.append(
            f"**{nombre}**\n"
            f"- Nota actual: {current} {f'({current_grade})' if current_grade else ''}\n"
            f"- Nota final: {final}"
        )
    return "\n\n".join(lines)


@mcp.tool()
async def get_quizzes(canvas_token: str, course_id: int) -> str:
    """
    Lista los cuestionarios/quizzes de un curso.

    Args:
        canvas_token: Token de autenticación Canvas del usuario (variable api-aula).
        course_id: ID del curso.
    """
    async with (await _client(canvas_token)) as canvas:
        quizzes = await canvas.get_quiz_list(course_id)
    if not quizzes:
        return "Este curso no tiene cuestionarios."
    lines = [f"El curso tiene **{len(quizzes)}** cuestionario(s):\n"]
    for q in quizzes:
        due = q.get("due_at") or "sin fecha límite"
        pts = q.get("points_possible")
        pts_str = f"{pts} pts" if pts is not None else "sin puntaje"
        lines.append(f"- **{q.get('title')}** (ID: {q.get('id')}) — Entrega: {due} — {pts_str}")
    return "\n".join(lines)


@mcp.tool()
async def get_quiz(canvas_token: str, course_id: int, quiz_id: int) -> str:
    """
    Obtiene el detalle de un cuestionario.

    Args:
        canvas_token: Token de autenticación Canvas del usuario (variable api-aula).
        course_id: ID del curso.
        quiz_id: ID del cuestionario.
    """
    async with (await _client(canvas_token)) as canvas:
        q = await canvas.get_quiz(course_id, quiz_id)
    due = q.get("due_at") or "sin fecha límite"
    pts = q.get("points_possible")
    pts_str = f"{pts} puntos" if pts is not None else "sin puntaje definido"
    questions = q.get("question_count", "?")
    time_limit = q.get("time_limit")
    time_str = f"{time_limit} minutos" if time_limit else "sin límite de tiempo"
    allowed = q.get("allowed_attempts", 1)
    return (
        f"**{q.get('title')}** (ID: {q.get('id')})\n"
        f"- Fecha límite: {due}\n"
        f"- Puntaje: {pts_str}\n"
        f"- Preguntas: {questions}\n"
        f"- Tiempo límite: {time_str}\n"
        f"- Intentos permitidos: {allowed}"
    )
