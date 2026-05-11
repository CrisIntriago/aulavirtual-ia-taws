import asyncio
import json
import inspect
from anthropic import Anthropic
from config import settings
from mcp_server import (
    get_current_user,
    get_courses,
    get_course,
    get_assignments,
    get_assignment,
    get_submissions,
    get_students,
    get_enrollments,
    get_modules,
    get_announcements,
    get_discussions,
    get_student_grades,
    get_quizzes,
    get_quiz,
)

SYSTEM_PROMPT = """Eres un asistente académico inteligente integrado al Aula Virtual de la ESPOL (Escuela Superior Politécnica del Litoral) a través de Canvas LMS.

Ayudas a estudiantes y docentes a consultar información académica: cursos, tareas, calificaciones, módulos, anuncios y foros. Respondes en español, con tono amigable pero profesional.

Cuando necesites información, usa las herramientas disponibles. Si necesitas un ID y el usuario no lo dio, primero consulta la lista correspondiente para encontrarlo. Nunca inventes datos."""

TOOLS = [
    {
        "name": "get_current_user",
        "description": "Obtiene el perfil del usuario actualmente autenticado.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_courses",
        "description": "Lista los cursos del usuario autenticado.",
        "input_schema": {
            "type": "object",
            "properties": {
                "enrollment_type": {
                    "type": "string",
                    "description": "Filtrar por tipo: student, teacher, ta, observer, designer. Dejar vacío para todos.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_course",
        "description": "Obtiene el detalle de un curso.",
        "input_schema": {
            "type": "object",
            "properties": {"course_id": {"type": "integer", "description": "ID del curso."}},
            "required": ["course_id"],
        },
    },
    {
        "name": "get_assignments",
        "description": "Lista todas las tareas de un curso.",
        "input_schema": {
            "type": "object",
            "properties": {"course_id": {"type": "integer", "description": "ID del curso."}},
            "required": ["course_id"],
        },
    },
    {
        "name": "get_assignment",
        "description": "Obtiene el detalle de una tarea específica.",
        "input_schema": {
            "type": "object",
            "properties": {
                "course_id": {"type": "integer", "description": "ID del curso."},
                "assignment_id": {"type": "integer", "description": "ID de la tarea."},
            },
            "required": ["course_id", "assignment_id"],
        },
    },
    {
        "name": "get_submissions",
        "description": "Lista las entregas de los estudiantes para una tarea.",
        "input_schema": {
            "type": "object",
            "properties": {
                "course_id": {"type": "integer", "description": "ID del curso."},
                "assignment_id": {"type": "integer", "description": "ID de la tarea."},
            },
            "required": ["course_id", "assignment_id"],
        },
    },
    {
        "name": "get_students",
        "description": "Lista los estudiantes matriculados en un curso.",
        "input_schema": {
            "type": "object",
            "properties": {"course_id": {"type": "integer", "description": "ID del curso."}},
            "required": ["course_id"],
        },
    },
    {
        "name": "get_enrollments",
        "description": "Lista todas las matrículas de un curso.",
        "input_schema": {
            "type": "object",
            "properties": {"course_id": {"type": "integer", "description": "ID del curso."}},
            "required": ["course_id"],
        },
    },
    {
        "name": "get_modules",
        "description": "Lista los módulos de contenido de un curso.",
        "input_schema": {
            "type": "object",
            "properties": {"course_id": {"type": "integer", "description": "ID del curso."}},
            "required": ["course_id"],
        },
    },
    {
        "name": "get_announcements",
        "description": "Lista los anuncios recientes de un curso.",
        "input_schema": {
            "type": "object",
            "properties": {"course_id": {"type": "integer", "description": "ID del curso."}},
            "required": ["course_id"],
        },
    },
    {
        "name": "get_discussions",
        "description": "Lista los foros de discusión de un curso.",
        "input_schema": {
            "type": "object",
            "properties": {"course_id": {"type": "integer", "description": "ID del curso."}},
            "required": ["course_id"],
        },
    },
    {
        "name": "get_student_grades",
        "description": "Obtiene las notas de un estudiante en un curso.",
        "input_schema": {
            "type": "object",
            "properties": {
                "course_id": {"type": "integer", "description": "ID del curso."},
                "student_id": {"type": "integer", "description": "ID del estudiante."},
            },
            "required": ["course_id", "student_id"],
        },
    },
    {
        "name": "get_quizzes",
        "description": "Lista los cuestionarios de un curso.",
        "input_schema": {
            "type": "object",
            "properties": {"course_id": {"type": "integer", "description": "ID del curso."}},
            "required": ["course_id"],
        },
    },
    {
        "name": "get_quiz",
        "description": "Obtiene el detalle de un cuestionario.",
        "input_schema": {
            "type": "object",
            "properties": {
                "course_id": {"type": "integer", "description": "ID del curso."},
                "quiz_id": {"type": "integer", "description": "ID del cuestionario."},
            },
            "required": ["course_id", "quiz_id"],
        },
    },
]

TOOL_MAP = {
    "get_current_user": get_current_user,
    "get_courses": get_courses,
    "get_course": get_course,
    "get_assignments": get_assignments,
    "get_assignment": get_assignment,
    "get_submissions": get_submissions,
    "get_students": get_students,
    "get_enrollments": get_enrollments,
    "get_modules": get_modules,
    "get_announcements": get_announcements,
    "get_discussions": get_discussions,
    "get_student_grades": get_student_grades,
    "get_quizzes": get_quizzes,
    "get_quiz": get_quiz,
}


async def call_tool(name: str, inputs: dict) -> str:
    fn = TOOL_MAP[name]
    if inspect.iscoroutinefunction(fn):
        return await fn(**inputs)
    return fn(**inputs)


async def chat(user_message: str, history: list) -> tuple[str, list]:
    client = Anthropic(api_key=settings.anthropic_api_key)
    history.append({"role": "user", "content": user_message})

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=history,
        )

        if response.stop_reason == "tool_use":
            tool_results = []
            assistant_content = response.content

            for block in response.content:
                if block.type == "tool_use":
                    print(f"  [tool] {block.name}({json.dumps(block.input, ensure_ascii=False)})")
                    result = await call_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            history.append({"role": "assistant", "content": assistant_content})
            history.append({"role": "user", "content": tool_results})

        else:
            text = next(b.text for b in response.content if hasattr(b, "text"))
            history.append({"role": "assistant", "content": text})
            return text, history


async def main():
    print("Asistente del Aula Virtual ESPOL")
    print("Escribe 'salir' para terminar.\n")
    history = []

    while True:
        user_input = input("Tú: ").strip()
        if not user_input or user_input.lower() == "salir":
            break
        response, history = await chat(user_input, history)
        print(f"\nAsistente: {response}\n")


if __name__ == "__main__":
    asyncio.run(main())
