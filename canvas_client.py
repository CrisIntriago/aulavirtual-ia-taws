from datetime import datetime, timedelta, timezone

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

    async def get_assignments(
        self,
        course_ids: list[int] | None = None,
        days_ahead: int = 7,
        per_page: int = 20
    ):
        active_courses = await self.get_active_course_ids()
        if not course_ids:
            course_ids = [cid for (cid, name) in active_courses]

        all_assignments = []
        now = datetime.now(timezone.utc)
        end_week = now + timedelta(days=days_ahead)
        
        for course_id in course_ids:
            assignments = await self._get(
                f"/courses/{course_id}/assignments",
                {
                    "per_page": per_page,
                    "bucket": "upcoming"
                }
            )
            filtered = []
            for a in assignments:
                a["course_id"] = course_id
                due_at = a.get("due_at")
                if not due_at:
                    filtered.append(a)
                    continue
                due_date = datetime.fromisoformat(
                    due_at.replace("Z", "+00:00")
                )

                if due_date >= now and due_date <= end_week:
                    filtered.append(a)
                 
            all_assignments.extend(filtered)
        all_assignments.sort(
            key=lambda a: (
                a.get("due_at") is None,
                a.get("due_at") or "9999-12-31T23:59:59Z"
            )
        )
        response = {
            "assignments": all_assignments,
            "course_names": [name for (cid, name) in active_courses]
        }
        return response

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

    async def get_active_course_ids(self) -> list[int]:
        courses = await self._get(
            "/courses",
            {
                "enrollment_state": "active",
                "state[]": ["available"],
                "per_page": 100
            }
        )

        if not courses:
            return []

        course_id_name_tuples = []

        for course in courses:
            course_id = course.get("id")
            name = course.get("name")
            if course_id is not None and name is not None:
                course_id_name_tuples.append((course_id, name))

        return course_id_name_tuples

    async def get_announcements(self,
        course_ids: list[int] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        latest_only: bool = False,
        active_only: bool = True,
        per_page: int = 20
    ):
        
        active_courses_ids = await self.get_active_course_ids()
        params = {
            "per_page": per_page,
            "active_only": active_only,
            "latest_only": latest_only,
        }

        if start_date:
            params["start_date"] = start_date

        if end_date:
            params["end_date"] = end_date

        if course_ids:
            params["context_codes[]"] = [
                f"course_{cid}" for cid in course_ids
            ]
        else:
            params["context_codes[]"] = [f"course_{cid}" for (cid, name) in active_courses_ids]
        announcements =  await self._get(
            "/announcements",
            params
        )
        return {
            "announcements": announcements,
            "course_names": [name for (cid, name) in active_courses_ids]
        }

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
