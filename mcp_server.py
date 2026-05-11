from mcp.server.fastmcp import FastMCP
from canvas_client import canvas

mcp = FastMCP(
    name="canvas-lms-espol",
    description="Servidor MCP para Canvas LMS de la ESPOL",
)


@mcp.tool()
async def get_current_user() -> dict:
    """Obtiene el perfil del usuario actualmente autenticado."""
    return await canvas.get_current_user()


@mcp.tool()
async def get_courses(enrollment_type: str = "") -> list:
    """
    Lista los cursos del usuario autenticado.

    Args:
        enrollment_type: Filtrar por tipo de matrícula. Valores: student, teacher, ta, observer, designer. Dejar vacío para todos.
    """
    return await canvas.get_courses(enrollment_type or None)


@mcp.tool()
async def get_course(course_id: int) -> dict:
    """
    Obtiene el detalle de un curso.

    Args:
        course_id: ID numérico del curso.
    """
    return await canvas.get_course(course_id)


@mcp.tool()
async def get_assignments(course_id: int) -> list:
    """
    Lista todas las asignaciones/tareas de un curso.

    Args:
        course_id: ID numérico del curso.
    """
    return await canvas.get_assignments(course_id)


@mcp.tool()
async def get_assignment(course_id: int, assignment_id: int) -> dict:
    """
    Obtiene el detalle de una asignación específica.

    Args:
        course_id: ID del curso.
        assignment_id: ID de la asignación.
    """
    return await canvas.get_assignment(course_id, assignment_id)


@mcp.tool()
async def get_submissions(course_id: int, assignment_id: int) -> list:
    """
    Lista las entregas de los estudiantes para una asignación.

    Args:
        course_id: ID del curso.
        assignment_id: ID de la asignación.
    """
    return await canvas.get_submissions(course_id, assignment_id)


@mcp.tool()
async def get_students(course_id: int) -> list:
    """
    Lista los estudiantes matriculados en un curso.

    Args:
        course_id: ID del curso.
    """
    return await canvas.get_students(course_id)


@mcp.tool()
async def get_enrollments(course_id: int) -> list:
    """
    Lista todas las matrículas de un curso (estudiantes, profesores, etc).

    Args:
        course_id: ID del curso.
    """
    return await canvas.get_enrollments(course_id)


@mcp.tool()
async def get_modules(course_id: int) -> list:
    """
    Lista los módulos de contenido de un curso.

    Args:
        course_id: ID del curso.
    """
    return await canvas.get_modules(course_id)


@mcp.tool()
async def get_announcements(course_id: int) -> list:
    """
    Lista los anuncios recientes de un curso.

    Args:
        course_id: ID del curso.
    """
    return await canvas.get_announcements(course_id)


@mcp.tool()
async def get_discussions(course_id: int) -> list:
    """
    Lista los foros de discusión de un curso.

    Args:
        course_id: ID del curso.
    """
    return await canvas.get_discussions(course_id)


@mcp.tool()
async def get_student_grades(course_id: int, student_id: int) -> dict:
    """
    Obtiene las notas de un estudiante en un curso.

    Args:
        course_id: ID del curso.
        student_id: ID del estudiante.
    """
    return await canvas.get_grades(course_id, student_id)


@mcp.tool()
async def get_quizzes(course_id: int) -> list:
    """
    Lista los cuestionarios/quizzes de un curso.

    Args:
        course_id: ID del curso.
    """
    return await canvas.get_quiz_list(course_id)


@mcp.tool()
async def get_quiz(course_id: int, quiz_id: int) -> dict:
    """
    Obtiene el detalle de un cuestionario.

    Args:
        course_id: ID del curso.
        quiz_id: ID del cuestionario.
    """
    return await canvas.get_quiz(course_id, quiz_id)
