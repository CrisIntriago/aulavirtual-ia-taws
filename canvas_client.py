import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx
from config import settings

logger = logging.getLogger("canvas")


class CanvasClient:
    def __init__(self):
        self.base_url = settings.canvas_base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {settings.canvas_api_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def aclose(self):
        await self._client.aclose()

    async def _get(self, path: str, params: dict = None) -> dict | list:
        url = f"{self.base_url}/api/v1{path}"
        t0 = time.perf_counter()
        response = await self._client.get(url, params=params or {})
        elapsed = (time.perf_counter() - t0) * 1000
        status = response.status_code
        logger.info("[Canvas] GET %s → %s (%.0fms)", path, status, elapsed)
        if not response.is_success:
            logger.warning("[Canvas] ERROR %s %s — body: %s", status, path, response.text[:200])
        response.raise_for_status()
        data = response.json()
        count = len(data) if isinstance(data, list) else "object"
        logger.debug("[Canvas] %s → %s items", path, count)
        return data

    async def _post(self, path: str, data: dict = None) -> dict:
        url = f"{self.base_url}/api/v1{path}"
        response = await self._client.post(url, json=data or {})
        response.raise_for_status()
        return response.json()

    async def get_courses(self, enrollment_type: str = None) -> list:
        params = {"per_page": 50}
        if enrollment_type:
            params["enrollment_type"] = enrollment_type
        return await self._get("/courses", params)

    async def get_course(self, course_id: int) -> dict:
        return await self._get(f"/courses/{course_id}")

    async def get_active_course_ids(self) -> list[tuple[int, str]]:
        courses = await self._get(
            "/courses",
            {
                "enrollment_state": "active",
                "state[]": ["available"],
                "per_page": 100,
            },
        )
        if not courses:
            return []
        return [
            (c["id"], c["name"])
            for c in courses
            if c.get("id") is not None and c.get("name") is not None
        ]

    async def get_assignments(
        self,
        course_ids: list[int] | None = None,
        active_courses: list[tuple[int, str]] | None = None,
        days_ahead: int = 7,
        per_page: int = 20,
    ):
        if active_courses is None:
            active_courses = await self.get_active_course_ids()
        if not course_ids:
            course_ids = [cid for (cid, _) in active_courses]

        now = datetime.now(timezone.utc)
        end_week = now + timedelta(days=days_ahead)

        async def fetch(course_id: int) -> list:
            try:
                assignments = await self._get(
                    f"/courses/{course_id}/assignments",
                    {"per_page": per_page, "bucket": "upcoming"},
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (403, 401, 404):
                    return []
                raise
            result = []
            for a in assignments:
                a["course_id"] = course_id
                due_at = a.get("due_at")
                if not due_at:
                    result.append(a)
                    continue
                due_date = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
                if now <= due_date <= end_week:
                    result.append(a)
            return result

        per_course = await asyncio.gather(*[fetch(cid) for cid in course_ids])
        all_assignments = [a for batch in per_course for a in batch]
        all_assignments.sort(
            key=lambda a: (
                a.get("due_at") is None,
                a.get("due_at") or "9999-12-31T23:59:59Z",
            )
        )
        return {
            "assignments": all_assignments,
            "course_names": [name for (_, name) in active_courses],
        }

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

    async def get_announcements(
        self,
        course_ids: list[int] | None = None,
        active_courses: list[tuple[int, str]] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        latest_only: bool = False,
        active_only: bool = True,
        per_page: int = 20,
    ):
        if active_courses is None:
            active_courses = await self.get_active_course_ids()

        params = {
            "per_page": per_page,
            "active_only": active_only,
            "latest_only": latest_only,
        }
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        params["context_codes[]"] = (
            [f"course_{cid}" for cid in course_ids]
            if course_ids
            else [f"course_{cid}" for (cid, _) in active_courses]
        )

        announcements = await self._get("/announcements", params)
        return {
            "announcements": announcements,
            "course_names": [name for (_, name) in active_courses],
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
