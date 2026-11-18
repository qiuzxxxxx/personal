from django.contrib.auth.models import User
from rest_framework.test import APITestCase


class WorkspaceV2SmokeTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("tester")
        self.client.force_authenticate(self.user)

    def test_calendar_focus_search_and_suggestions(self):
        created = self.client.post(
            "/api/tasks/",
            {"title": "408 网络错题复习", "estimated_minutes": 45},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        task_id = created.json()["id"]
        self.assertFalse(created.json()["is_scheduled"])

        calendar = self.client.get("/api/workspace/calendar/")
        self.assertEqual(calendar.status_code, 200)
        self.assertEqual(calendar.json()["unscheduled_tasks"][0]["id"], task_id)

        block = self.client.post(
            "/api/workspace/calendar/blocks/",
            {
                "task_id": task_id,
                "title": "408 网络错题复习",
                "day_date": calendar.json()["week_start"],
                "start_time": "14:00",
                "duration_minutes": 45,
            },
            format="json",
        )
        self.assertEqual(block.status_code, 201)
        self.assertEqual(block.json()["end_time"], "14:45")

        calendar = self.client.get("/api/workspace/calendar/")
        self.assertEqual(calendar.json()["unscheduled_tasks"], [])
        self.assertEqual(calendar.json()["total_scheduled_minutes"], 45)

        month = self.client.get(
            "/api/workspace/calendar/month/",
            {"month": calendar.json()["week_start"][:7]},
        )
        self.assertEqual(month.status_code, 200)
        self.assertEqual(month.json()["blocks"][0]["id"], block.json()["id"])

        focus = self.client.post(
            "/api/workspace/focus/",
            {"target_title": "408 网络错题复习", "minutes": 25},
            format="json",
        )
        self.assertEqual(focus.status_code, 201)
        stats = self.client.get("/api/workspace/focus/")
        self.assertEqual(stats.json()["weekly_total_minutes"], 25)

        search = self.client.get("/api/workspace/search/", {"q": "408"})
        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.json()["tasks"][0]["id"], task_id)

        self.client.force_authenticate(None)
        self.client.force_authenticate(User.objects.create_user("yk"))
        denied = self.client.get("/api/workspace/search/", {"q": "408"})
        self.assertEqual(denied.status_code, 403)

    def test_review_sm2_and_block_delete_restores_task(self):
        created = self.client.post(
            "/api/knowledge/reviews/",
            {"front": "TCP 三次握手？", "back": "SYN / SYN-ACK / ACK"},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        card_id = created.json()["id"]
        graded = self.client.post(
            f"/api/knowledge/reviews/{card_id}/grade/",
            {"grade": "good", "version": created.json()["version"]},
            format="json",
        )
        self.assertEqual(graded.status_code, 200)
        self.assertGreaterEqual(graded.json()["interval_days"], 1)

        task = self.client.post(
            "/api/tasks/", {"title": "可回退任务", "estimated_minutes": 30}, format="json"
        ).json()
        calendar = self.client.get("/api/workspace/calendar/").json()
        block = self.client.post(
            "/api/workspace/calendar/blocks/",
            {
                "task_id": task["id"],
                "day_date": calendar["week_start"],
                "start_time": "09:00",
                "duration_minutes": 30,
            },
            format="json",
        ).json()
        deleted = self.client.delete(f"/api/workspace/calendar/blocks/{block['id']}/")
        self.assertEqual(deleted.status_code, 200)
        calendar = self.client.get("/api/workspace/calendar/").json()
        self.assertEqual(calendar["unscheduled_tasks"][0]["id"], task["id"])

    def test_agent_suggestions(self):
        self.client.post(
            "/api/tasks/", {"title": "待排期任务", "estimated_minutes": 60}, format="json"
        )
        response = self.client.get("/api/agent/suggestions/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["suggestions"]), 1)
