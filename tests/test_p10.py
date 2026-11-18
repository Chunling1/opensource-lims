import io
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import CreateSchema, DropSchema

from backend.app import make_app
from backend.demo import seed_demo
from backend.schema import events, files, grants, reports, samples, tasks, users

HEAD = {"X-LIMS-Action": "1"}
DAY = date.today().isoformat()
PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF"


class Slice(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        url = os.getenv("LIMS_TEST_POSTGRES")
        if url:
            base = create_engine(url)
            self.addCleanup(base.dispose)
            schema = "p10_test_" + uuid4().hex
            with base.begin() as db:
                db.execute(CreateSchema(schema))

            def cleanup_schema():
                with base.begin() as db:
                    db.execute(DropSchema(schema, cascade=True))

            self.addCleanup(cleanup_schema)
            url = make_url(url).update_query_dict({"options": "-csearch_path=" + schema})
        self.app = make_app(self.root, url)
        self.engine = self.app.extensions["engine"]
        self.addCleanup(self.engine.dispose)
        self.app.testing = True
        cfg = Config()
        cfg.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[1] / "backend" / "migrations")
        )
        cfg.attributes["engine"] = self.engine
        command.upgrade(cfg, "head")
        command.upgrade(cfg, "head")
        self.assertTrue(seed_demo(self.engine))
        self.lin = self.login("lin")

    def login(self, account):
        client = self.app.test_client()
        res = client.post(
            "/api/login", json={"account": account, "password": "LimsDemo2026"}, headers=HEAD
        )
        self.assertEqual(res.status_code, 200)
        return client

    def post(self, action, sid=1, client=None, version=None, key=None, status=200, **data):
        c = client or self.lin
        if version is None:
            detail = c.get(f"/api/samples/{sid}").json
            version = next(
                (r["version"] for r in detail["reports"] if r["id"] == data.get("reportId")),
                detail["version"],
            )
        data.update(version=version, requestId=key or str(uuid4()))
        path = f"/api/samples/{sid}/{action}"
        if action == "upload":
            data["file"] = (io.BytesIO(data.pop("content", PDF)), "demo.pdf")
            res = c.post(path, data=data, headers=HEAD)
        else:
            res = c.post(path, json=data, headers=HEAD)
        self.assertEqual(res.status_code, status, res.get_data(as_text=True))
        return res.json

    def detail(self, client=None, sid=1):
        return (client or self.lin).get(f"/api/samples/{sid}").json

    def test_scope_pool_and_transfer(self):
        self.assertEqual(self.lin.get("/api/samples").json["total"], 2)
        self.assertEqual(
            self.lin.get("/api/samples?project=W-01&commission=0001&state=pool").json["total"], 1
        )
        self.assertEqual(self.lin.get("/api/samples?view=mine").json["total"], 0)
        self.assertEqual(self.lin.get("/api/samples/5").status_code, 404)
        expired = self.login("lu")
        self.assertEqual(expired.get("/api/samples").json["total"], 0)
        self.post("claim", client=expired, status=422)
        for sid in (3, 4, 6):
            self.post("claim", sid=sid, status=422)
        self.post("claim")
        self.post("return", reason="重新排班")
        self.post("claim")
        self.post("transfer", reason="更换人员", targetId=4, status=422)
        r = self.post("create", ruleId=1)["reportId"]
        self.post("upload", reportId=r, kind="source")
        self.post("return", reason="重新排班", status=422)
        self.post("transfer", reason="更换人员", targetId=2)
        self.post("upload", reportId=r, kind="draft", status=403)
        zhou = self.login("zhou")
        detail = self.detail(zhou)
        self.assertNotIn("transfer", detail["actions"])
        self.assertEqual([u["id"] for u in detail["reports"][0]["reviewers"]], [3])

    def test_report_list_scope_filters_and_pagination(self):
        self.post("claim")
        for _ in range(11):
            self.post("create", ruleId=1)
        last = self.detail()["reports"][-1]
        self.post("cancel", reportId=last["id"], reason="调整")
        page = self.lin.get("/api/reports?page=2").json
        self.assertEqual((page["total"], len(page["rows"])), (11, 1))
        rows = self.lin.get("/api/reports?number=BG&sample=YP-0001&state=cancelled").json["rows"]
        self.assertEqual([r["id"] for r in rows], [last["id"]])
        self.assertEqual(self.login("he").get("/api/reports").json["total"], 0)
        self.assertEqual(self.app.test_client().get("/api/reports").status_code, 401)

    def test_worklist_transitions_and_visibility(self):
        def tasks(client, query=""):
            result=client.get("/api/tasks"+query)
            self.assertEqual(result.status_code,200)
            return result.json
        self.assertEqual(tasks(self.lin)["counts"]["claim"],2)
        self.assertEqual(tasks(self.login("zi"))["total"],0)
        self.assertEqual(tasks(self.login("lu"))["counts"]["claim"],0)
        self.assertTrue(all(row["arrived"] for row in tasks(self.lin)["rows"]))
        self.post("claim")
        self.assertEqual(tasks(self.lin)["counts"],{"claim":1,"author":1,"returned":0,"review1":0})
        self.assertIsNone(tasks(self.lin,"?kind=author")["rows"][0]["reportId"])
        rid=self.post("create",ruleId=1)["reportId"]
        row=tasks(self.lin,"?kind=author&pageSize=20")["rows"][0]
        self.assertEqual(row["reportId"],rid)
        self.assertEqual(tasks(self.lin)["counts"]["author"],1)
        self.assertEqual(tasks(self.lin,"?end=2000-01-01")["total"],0)
        for kind in ("source","draft"):
            self.post("upload",reportId=rid,kind=kind)
        self.post("submit",reportId=rid,start=DAY,end=DAY,reviewerId=3)
        self.assertEqual(tasks(self.lin)["counts"]["author"],0)
        self.assertEqual(tasks(self.login("shen"))["counts"]["review1"],1)
        self.assertEqual(tasks(self.login("zhou"))["counts"]["review1"],0)
        for endpoint in ("tasks","samples","reports"):
            self.assertEqual(self.lin.get("/api/"+endpoint+"?pageSize=50").json["pageSize"],50)
            self.assertEqual(self.lin.get("/api/"+endpoint+"?pageSize=11").status_code,400)

    def test_concurrent_claim_and_request_replay(self):
        zhou = self.login("zhou")
        barrier = Barrier(2)

        def claim(c):
            key = str(uuid4())
            barrier.wait()
            res = c.post("/api/samples/1/claim", json={"version": 1, "requestId": key}, headers=HEAD)
            return c, key, res.status_code, res.json

        with ThreadPoolExecutor(max_workers=2) as threads:
            results = list(threads.map(claim, [self.lin, zhou]))
        self.assertEqual(sorted(r[2] for r in results), [200, 409])
        c, key, _, result = next(r for r in results if r[2] == 200)
        self.assertEqual(self.post("claim", client=c, version=1, key=key), result)
        self.post("claim", sid=2, client=c, version=1, key=key, status=409)
        with self.engine.connect() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(events)), 1)

    def test_report_lifecycle_and_history(self):
        self.post("claim")
        r = self.post("create", ruleId=1)["reportId"]
        self.post("cancel", reportId=r, reason="委托方调整")
        r = self.post("create", ruleId=1)["reportId"]
        sibling = self.post("create", ruleId=2)["reportId"]
        self.assertEqual(self.detail()["reports"][1]["number"], "BG-00002")
        params = dict(reportId=r, start=DAY, end=DAY, reviewerId=3)
        self.post("submit", **params, status=422)
        self.post("upload", reportId=r, kind="source", content=b"plain text", status=422)
        self.assertFalse(list((self.root / "files").iterdir()))
        self.post("upload", reportId=r, kind="source")
        original = self.detail()["reports"][1]["files"][0]["id"]
        self.post("upload", reportId=r, kind="source", replaces=original, content=PDF + b"\n")
        self.post("upload", reportId=r, kind="source")
        self.post("upload", reportId=r, kind="draft")
        self.post("upload", reportId=r, kind="draft")
        self.assertEqual(len(self.detail()["reports"][1]["files"]), 3)
        with self.lin.get(f"/api/files/{original}") as downloaded:
            self.assertEqual(downloaded.data, PDF)
        self.assertEqual(self.login("he").get(f"/api/files/{original}").status_code, 404)
        self.post("submit", **{**params, "start": "2000-01-01"}, status=422)
        self.post("submit", **{**params, "reviewerId": 1}, status=422)
        self.post("submit", **params)
        self.post("upload", reportId=r, kind="source", status=422)
        self.post("cancel", reportId=r, reason="撤回", status=422)
        self.assertEqual(self.detail()["reports"][2]["state"], "draft")
        with self.engine.connect() as db:
            snap = db.scalar(select(reports.c.snapshot).where(reports.c.id == r))
            self.assertEqual(len(snap), 3)
            self.assertNotIn(original, {f["id"] for f in snap})
            self.assertEqual(db.scalar(select(func.count()).select_from(files)), 5)
            self.assertEqual(
                db.scalar(
                    select(tasks.c.assigned).where(tasks.c.report_id == r, tasks.c.kind == "review1")
                ),
                3,
            )
            self.assertIsNone(db.scalar(select(reports.c.snapshot).where(reports.c.id == sibling)))

    def test_independent_report_edits(self):
        self.post("claim")
        a = self.post("create", ruleId=1)["reportId"]
        b = self.post("create", ruleId=1)["reportId"]
        self.post("upload", reportId=a, kind="source", version=1)
        self.post("upload", reportId=b, kind="source", version=1)
        self.post("upload", reportId=a, kind="draft", version=1, status=409)

    def test_cross_department_assignment_and_immutable_audit(self):
        self.post("claim")
        self.post("transfer", reason="跨部门协作", targetId=5)
        he = self.login("he")
        self.assertEqual(he.get("/api/samples?view=mine").json["total"], 1)
        self.post("create", client=he, ruleId=1)
        for write in (update(events).values(action="rewrite"), events.delete()):
            with self.assertRaises(DBAPIError), self.engine.begin() as db:
                db.execute(write)
        with self.engine.begin() as db:
            db.execute(update(users).where(users.c.account == "zhou").values(data_scope="self"))
        self.assertEqual(self.login("zhou").get("/api/samples/1").status_code, 404)

    def test_site_pool_and_catalog_notice(self):
        self.post("claim", sid=2)
        r = self.post("create", sid=2, ruleId=2)["reportId"]
        for kind in ("source", "draft"):
            self.post("upload", sid=2, reportId=r, kind=kind)
        self.post("submit", sid=2, reportId=r, start=DAY, end=DAY, status=422)
        self.post("submit", sid=2, reportId=r, start=DAY, end=DAY, siteDate=DAY)
        self.assertEqual(self.detail(sid=2)["siteDate"], DAY)
        self.post("claim")
        r = self.post("create", ruleId=1)["reportId"]
        for kind in ("source", "draft"):
            self.post("upload", reportId=r, kind=kind)
        version = self.detail()["reports"][0]["version"]
        with self.engine.begin() as db:
            db.execute(
                update(grants)
                .where(grants.c.duty == "review")
                .values(end=date.today() - timedelta(days=1))
            )
        self.post("submit", reportId=r, start=DAY, end=DAY, reviewerId=3, version=version, status=422)
        self.assertTrue(self.detail()["reports"][0]["actions"]["submit"])
        self.assertEqual(len(self.login("zi").get("/api/notices").json), 1)
        self.assertEqual(self.lin.get("/api/notices").status_code, 403)
        with self.engine.begin() as db:
            db.execute(update(samples).where(samples.c.id == 1).values(frozen=True))
        self.post("upload", reportId=r, kind="source", status=422)


if __name__ == "__main__":
    unittest.main()
