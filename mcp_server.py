from mcp.server.fastmcp import FastMCP
from canvas_client import canvas
import re
from datetime import datetime

mcp = FastMCP(
    name="canvas-lms-espol",
    description="Servidor MCP para Canvas LMS de la ESPOL",
    streamable_http_path="/",
)


@mcp.tool()
async def get_current_user() -> str:
    """Obtiene el perfil del usuario actualmente autenticado."""
    u = await canvas.get_current_user()
    name = u.get("name", "Desconocido")
    login = u.get("login_id") or u.get("primary_email") or "no disponible"
    uid = u.get("id", "?")
    return f"El usuario autenticado es **{name}** (ID: {uid}, login: {login})."


@mcp.tool()
async def get_courses(enrollment_type: str = "") -> str:
    """
    Lista los cursos del usuario autenticado.

    Args:
        enrollment_type: Filtrar por tipo de matrícula. Valores: student, teacher, ta, observer, designer. Dejar vacío para todos.
    """
    courses = await canvas.get_courses(enrollment_type or None)
    if not courses:
        return "No se encontraron cursos para este usuario."
    lines = [f"Se encontraron {len(courses)} curso(s):\n"]
    for c in courses:
        name = c.get("name") or c.get("course_code") or "Sin nombre"
        lines.append(f"- **{name}** (ID: {c.get('id')})")
    return "\n".join(lines)


@mcp.tool()
async def get_course(course_id: int) -> str:
    """
    Obtiene el detalle de un curso.

    Args:
        course_id: ID numérico del curso.
    """
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
async def get_assignments(course_id: int) -> str:
    """
    Lista todas las asignaciones/tareas de un curso.

    Args:
        course_id: ID numérico del curso.
    """
    assignments = await canvas.get_assignments(course_id)
    if not assignments:
        return "Este curso no tiene tareas registradas."
    lines = [f"El curso tiene {len(assignments)} tarea(s):\n"]
    for a in assignments:
        due = a.get("due_at") or "sin fecha límite"
        pts = a.get("points_possible")
        pts_str = f"{pts} pts" if pts is not None else "sin puntaje"
        lines.append(f"- **{a.get('name')}** (ID: {a.get('id')}) — Entrega: {due} — {pts_str}")
    return "\n".join(lines)


@mcp.tool()
async def get_assignment(course_id: int, assignment_id: int) -> str:
    """
    Obtiene el detalle de una asignación específica.

    Args:
        course_id: ID del curso.
        assignment_id: ID de la asignación.
    """
    a = await canvas.get_assignment(course_id, assignment_id)
    due = a.get("due_at") or "sin fecha límite"
    pts = a.get("points_possible")
    pts_str = f"{pts} puntos" if pts is not None else "sin puntaje definido"
    desc = a.get("description") or "sin descripción"
    # Strip HTML tags simply
    import re
    desc = re.sub(r"<[^>]+>", " ", desc).strip()
    desc = desc[:300] + "..." if len(desc) > 300 else desc
    return (
        f"**{a.get('name')}** (ID: {a.get('id')})\n"
        f"- Fecha límite: {due}\n"
        f"- Puntaje: {pts_str}\n"
        f"- Descripción: {desc}"
    )


@mcp.tool()
async def get_submissions(course_id: int, assignment_id: int) -> str:
    """
    Lista las entregas de los estudiantes para una asignación.

    Args:
        course_id: ID del curso.
        assignment_id: ID de la asignación.
    """
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
async def get_students(course_id: int) -> str:
    """
    Lista los estudiantes matriculados en un curso.

    Args:
        course_id: ID del curso.
    """
    students = await canvas.get_students(course_id)
    if not students:
        return "No se encontraron estudiantes matriculados en este curso."
    lines = [f"El curso tiene **{len(students)}** estudiante(s) matriculado(s):\n"]
    for s in students:
        lines.append(f"- {s.get('name', 'Sin nombre')} (ID: {s.get('id')})")
    return "\n".join(lines)


@mcp.tool()
async def get_enrollments(course_id: int) -> str:
    """
    Lista todas las matrículas de un curso (estudiantes, profesores, etc).

    Args:
        course_id: ID del curso.
    """
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
async def get_modules(course_id: int) -> str:
    """
    Lista los módulos de contenido de un curso.

    Args:
        course_id: ID del curso.
    """
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
    course_ids: list[int] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    latest_only: bool = False,
    active_only: bool = True,
    per_page: int = 20
) -> str:
    """
    📢 Obtiene anuncios de Canvas LMS para uno o varios cursos.

    Si no se especifican cursos, se consultarán automáticamente
    todos los cursos activos del usuario autenticado.

    Devuelve anuncios en un formato compacto, amigable y fácil
    de leer para chat.
    """


    ann_response = await canvas.get_announcements(
        course_ids=course_ids,
        start_date=start_date,
        end_date=end_date,
        latest_only=latest_only,
        active_only=active_only,
        per_page=per_page
    )
    return ann_response

@mcp.tool()
async def get_discussions(course_id: int) -> str:
    """
    Lista los foros de discusión de un curso.

    Args:
        course_id: ID del curso.
    """
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
async def get_student_grades(course_id: int, student_id: int) -> str:
    """
    Obtiene las notas de un estudiante en un curso.

    Args:
        course_id: ID del curso.
        student_id: ID del estudiante.
    """
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
async def get_quizzes(course_id: int) -> str:
    """
    Lista los cuestionarios/quizzes de un curso.

    Args:
        course_id: ID del curso.
    """
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
async def get_quiz(course_id: int, quiz_id: int) -> str:
    """
    Obtiene el detalle de un cuestionario.

    Args:
        course_id: ID del curso.
        quiz_id: ID del cuestionario.
    """
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
