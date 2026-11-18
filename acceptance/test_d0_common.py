"""附表D D-0 通用规则：登录、原因必填、审计留痕、待办流转、失败不留痕、提示可读。"""
from uuid import uuid4

from sqlalchemy import func, select

from acceptance.base import DAY, HEAD, SHEN, ZHOU, Base
from backend.schema import events, tasks


class Session(Base):
    def test_anonymous_rejected(self):
        c = self.app.test_client()
        self.assertEqual(c.get("/api/samples").status_code, 401)
        r = c.post("/api/samples/1/claim", json={"version": 1, "requestId": str(uuid4())},
                   headers=HEAD)
        self.assertIn(r.status_code, (401, 403))

    def test_wrong_password(self):
        self.login("lin", password="bad", status=401)

    def test_action_without_csrf_header_rejected(self):
        r = self.lin.post("/api/samples/1/claim",
                          json={"version": 1, "requestId": str(uuid4())})
        self.assertEqual(r.status_code, 403)
        self.assertIsNone(self.detail()["owner"])

    def test_logout_ends_session(self):
        self.lin.post("/api/logout", headers=HEAD)
        self.assertEqual(self.lin.get("/api/samples").status_code, 401)


class Audit(Base):
    def rows(self, action=None):
        with self.engine.connect() as db:
            q = select(events)
            if action:
                q = q.where(events.c.action == action)
            return db.execute(q.order_by(events.c.id)).all()

    def test_every_success_writes_one_event(self):
        rid = self.ready()
        self.act("submit", reportId=rid, start=DAY, end=DAY, reviewerId=SHEN)
        self.assertEqual([r.action for r in self.rows()],
                         ["claim", "create", "upload", "upload", "submit"])
        for r in self.rows():
            self.assertTrue(r.request_id and r.at and r.actor)

    def test_failure_writes_no_event(self):
        self.act("claim", c=self.login("lu"), status=422)
        self.act("claim", version=42, status=409)
        self.assertEqual(self.rows(), [])

    def test_reason_and_previous_owner_kept(self):
        """D-0 审计：记录原因、前后值。"""
        self.act("claim")
        self.act("transfer", reason="更换人员", targetId=ZHOU)
        ev = self.rows("transfer")[0]
        text = str(ev.payload)
        self.assertIn("更换人员", text)
        self.assertEqual(ev.payload.get("previousOwner"), 1)

    def test_return_reason_kept(self):
        self.act("claim")
        self.act("return", reason="重新排班")
        self.assertIn("重新排班", str(self.rows("return")[0].payload))

    def test_upload_hash_kept(self):
        rid = self.claim_and_report()
        self.act("upload", reportId=rid, kind="source")
        self.assertIn("sha256", self.rows("upload")[0].payload)


class Tasks(Base):
    def open_tasks(self):
        with self.engine.connect() as db:
            return db.execute(select(tasks.c.kind, tasks.c.assigned, tasks.c.report_id)
                              .where(tasks.c.sample_id == 1, ~tasks.c.closed)).all()

    def test_submit_closes_author_opens_review1(self):
        """D-0 待办：关闭本节点，生成下一节点；指定模式落到所选审核人。"""
        rid = self.ready()
        self.assertIn(("author", 1, rid), [tuple(t) for t in self.open_tasks()])
        self.act("submit", reportId=rid, start=DAY, end=DAY, reviewerId=SHEN)
        self.assertEqual([tuple(t) for t in self.open_tasks()], [("review1", SHEN, rid)])

    def test_site_pool_mode_unassigned(self):
        rid = self.ready(sid=2)
        self.act("submit", sid=2, reportId=rid, start=DAY, end=DAY, siteDate=DAY)
        with self.engine.connect() as db:
            t = db.execute(select(tasks).where(tasks.c.report_id == rid, ~tasks.c.closed)).one()
        self.assertEqual((t.kind, t.assigned), ("review1", None))

    def test_claim_task_closed_after_claim(self):
        with self.engine.connect() as db:
            before = db.scalar(select(func.count()).select_from(tasks)
                               .where(tasks.c.sample_id == 1, tasks.c.kind == "claim", ~tasks.c.closed))
        self.assertEqual(before, 1)
        self.act("claim")
        kinds = [t.kind for t in self.open_tasks()]
        self.assertNotIn("claim", kinds)


class Messages(Base):
    """失败须说明原因（D-0 权限：返回是哪一层、什么原因）。"""

    def test_errors_are_readable_chinese(self):
        r = self.act("claim", c=self.login("lu"), status=422)
        self.assertRegex(r["error"], "授权")
        rid = self.claim_and_report()
        r = self.act("upload", reportId=rid, kind="source", content=b"x", status=422)
        self.assertIn("PDF", r["error"])
        r = self.act("submit", reportId=rid, start=DAY, end=DAY, reviewerId=SHEN, status=422)
        self.assertRegex(r["error"], "原始记录")

    def test_detail_explains_disabled_actions(self):
        d = self.detail(sid=3)
        self.assertTrue(d["actions"].get("claim"), "未收样样品应给出不可领取原因")
