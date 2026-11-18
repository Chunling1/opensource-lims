"""验收测试公共夹具：只经 HTTP 接口操作，依据开发说明书 D 号与附表 D 动作。

不依赖被测代码的内部函数，仅使用：make_app、Alembic 迁移、seed_demo（演示种子）。
虚构账号（seed_demo）：1 林澄 lin、2 周禾 zhou、3 沈宁 shen（仅审核）、4 陆川 lu（授权已过期）、
5 何杉 he（材料组）、6 顾桐 zi（资料管理，无检测授权）。
样品：1 溪流水样（已收样，指定审核）、2 河岸测点（现场，审核池）、3 未收样、4 已冻结、
5 材料组、6 未评审。编号规则：1=BG、2=XC。
"""
import io
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from backend.app import make_app
from backend.demo import seed_demo

HEAD = {"X-LIMS-Action": "1"}
TODAY = date.today()
DAY = TODAY.isoformat()
PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF"
LIN, ZHOU, SHEN, LU, HE, ZI = 1, 2, 3, 4, 5, 6


class Base(unittest.TestCase):
    pdf_mb = None

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        if self.pdf_mb:
            old = os.environ.get("LIMS_PDF_MB")
            os.environ["LIMS_PDF_MB"] = str(self.pdf_mb)
            self.addCleanup(lambda: os.environ.pop("LIMS_PDF_MB") if old is None
                            else os.environ.__setitem__("LIMS_PDF_MB", old))
        url = os.getenv("LIMS_TEST_POSTGRES")
        if url:  # 每条测试一个临时 schema，跑完删除
            admin = create_engine(url)
            self.addCleanup(admin.dispose)
            schema = "acc_" + uuid4().hex
            with admin.begin() as db:
                db.execute(CreateSchema(schema))

            def drop():
                with admin.begin() as db:
                    db.execute(DropSchema(schema, cascade=True))

            self.addCleanup(drop)
            url = make_url(url).update_query_dict({"options": "-csearch_path=" + schema})
        self.app = make_app(self.root, url)
        self.app.testing = True
        self.engine = self.app.extensions["engine"]
        self.addCleanup(self.engine.dispose)
        cfg = Config()
        cfg.set_main_option("script_location",
                            str(Path(__file__).resolve().parents[1] / "backend" / "migrations"))
        cfg.attributes["engine"] = self.engine
        command.upgrade(cfg, "head")
        self.assertTrue(seed_demo(self.engine))
        self.lin = self.login("lin")

    # ---- 接口辅助 ----
    def login(self, account, password="LimsDemo2026", status=200):
        c = self.app.test_client()
        r = c.post("/api/login", json={"account": account, "password": password}, headers=HEAD)
        self.assertEqual(r.status_code, status, r.get_data(as_text=True))
        return c

    def detail(self, sid=1, c=None):
        r = (c or self.lin).get(f"/api/samples/{sid}")
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.json

    def report(self, rid, sid=1, c=None):
        return next(x for x in self.detail(sid, c)["reports"] if x["id"] == rid)

    def act(self, action, sid=1, c=None, status=200, version=None, key=None,
            name="demo.pdf", content=PDF, **data):
        c = c or self.lin
        if version is None:
            d = c.get(f"/api/samples/{sid}").json or {}
            rid = data.get("reportId")
            version = next((x["version"] for x in d.get("reports", []) if x["id"] == rid),
                           d.get("version", 1))
        data.update(version=version, requestId=key or str(uuid4()))
        path = f"/api/samples/{sid}/{action}"
        if action == "upload":
            data["file"] = (io.BytesIO(content), name)
            r = c.post(path, data=data, headers=HEAD)
        else:
            r = c.post(path, json=data, headers=HEAD)
        self.assertEqual(r.status_code, status, f"{action}: {r.get_data(as_text=True)}")
        return r.json

    def claim_and_report(self, sid=1, c=None, rule=1):
        self.act("claim", sid, c)
        return self.act("create", sid, c, ruleId=rule)["reportId"]

    def ready(self, sid=1, c=None):
        """领取、建报告、传原始记录和待签报告，返回报告 id。"""
        rid = self.claim_and_report(sid, c)
        for kind in ("source", "draft"):
            self.act("upload", sid, c, reportId=rid, kind=kind)
        return rid

    def pool(self, c=None, **q):
        r = (c or self.lin).get("/api/samples", query_string=q)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.json
