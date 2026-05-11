import httpx
from config import settings


class CanvasClient:
    def __init__(self):
        self.base_url = settings.canvas_base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {settings.canvas_api_token}",
            "Content-Type": "application/json",
        }

    async def _get(self, path: str, params: dict = None) -> dict | list:
        url = f"{self.base_url}/api/v1{path}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers, params=params or {})
            response.raise_for_status()
            return response.json()

    async def _post(self, path: str, data: dict = None) -> dict:
        url = f"{self.base_url}/api/v1{path}"
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self.headers, json=data or {})
            response.raise_for_status()
            return response.json()

    async def get_courses(self, enrollment_type: str = None) -> list:
        params = {"per_page": 50}
        if enrollment_type:
            params["enrollment_type"] = enrollment_type
        return await self._get("/courses", params)

    async def get_course(self, course_id: int) -> dict:
        return await self._get(f"/courses/{course_id}")

    async def get_assignments(self, course_id: int) -> list:
        return await self._get(f"/courses/{course_id}/assignments", {"per_page": 50})

    async def get_assignment(self, course_id: int, assignment_id: int) -> dict:
        return await self._get(f"/courses/{course_id}/assignments/{assignment_id}")

    async def get_submissions(self, course_id: int, assignment_id: int) -> list:
        return await self._get(
            f"/courses/{course_id}/assignments/{assignment_id}/submissions",
            {"per_page": 50, "include[]": "user"},
        )

    async def get_students(self, course_id: int) -> list:
        return await self._get(
            f"/courses/{course_id}/users",
            {"enrollment_type[]": "student", "per_page": 50},
        )

    async def get_enrollments(self, course_id: int) -> list:
        return await self._get(f"/courses/{course_id}/enrollments", {"per_page": 50})

    async def get_modules(self, course_id: int) -> list:
        return await self._get(f"/courses/{course_id}/modules", {"per_page": 50})

    async def get_announcements(self, course_id: int) -> list:
        return await self._get(
            "/announcements",
            {"context_codes[]": f"course_{course_id}", "per_page": 20},
        )

    async def get_discussions(self, course_id: int) -> list:
        return await self._get(f"/courses/{course_id}/discussion_topics", {"per_page": 50})

    async def get_grades(self, course_id: int, student_id: int) -> dict:
        return await self._get(
            f"/courses/{course_id}/enrollments",
            {"user_id": student_id, "include[]": "grades"},
        )

    async def get_current_user(self) -> dict:
        return await self._get("/users/self")

    async def get_quiz_list(self, course_id: int) -> list:
        return await self._get(f"/courses/{course_id}/quizzes", {"per_page": 50})

    async def get_quiz(self, course_id: int, quiz_id: int) -> dict:
        return await self._get(f"/courses/{course_id}/quizzes/{quiz_id}")


canvas = CanvasClient()
