"""A-13 创建报告、A-14 上传 PDF、A-15 提交审核。"""
import hashlib
from datetime import timedelta

from sqlalchemy import func, select

from acceptance.base import DAY, LIN, PDF, SHEN, TODAY, ZHOU, Base
from backend.schema import files


class CreateReport(Base):
    def test_number_assigned_and_not_recycled(self):
        """A-13 / D-48：创建即取号；取消后号码不回收。"""
        rid = self.claim_and_report()
        first = self.report(rid)["number"]
        self.assertTrue(first.startswith("BG-"))
        self.act("cancel", reportId=rid, reason="委托方调整")
        self.assertEqual(self.report(rid)["state"], "cancelled")
        nxt = self.act("create", ruleId=1)["reportId"]
        self.assertNotEqual(self.report(nxt)["number"], first)

    def test_prefixes_count_separately(self):
        self.act("claim")
        a = self.act("create", ruleId=1)["reportId"]
        b = self.act("create", ruleId=2)["reportId"]
        self.assertEqual(self.report(a)["number"][-5:], self.report(b)["number"][-5:])

    def test_cancel_needs_reason(self):
        rid = self.claim_and_report()
        self.act("cancel", reportId=rid, reason=" ", status=400)

    def test_unknown_rule_rejected(self):
        self.act("claim")
        self.act("create", ruleId=999, status=422)


class UploadPdf(Base):
    def test_extension_only_rejected(self):
        rid = self.claim_and_report()
        self.act("upload", reportId=rid, kind="source", content=b"hello", status=422)

    def test_header_only_rejected(self):
        rid = self.claim_and_report()
        self.act("upload", reportId=rid, kind="source", name="a.docx", status=422)

    def test_rejected_upload_leaves_no_file(self):
        rid = self.claim_and_report()
        self.act("upload", reportId=rid, kind="source", content=b"x", status=422)
        self.assertEqual(list((self.root / "files").iterdir()), [])

    def test_sha256_recorded_and_download_matches(self):
        rid = self.claim_and_report()
        self.act("upload", reportId=rid, kind="source")
        f = self.report(rid)["files"][0]
        self.assertEqual(f["sha256"], hashlib.sha256(PDF).hexdigest())
        self.assertEqual(f["size"], len(PDF))
        self.assertEqual(self.lin.get(f"/api/files/{f['id']}").data, PDF)

    def test_replace_is_append_only(self):
        """A-14：文件记录只追加，替换后原件仍保留可下载。"""
        rid = self.claim_and_report()
        self.act("upload", reportId=rid, kind="source")
        old = self.report(rid)["files"][0]["id"]
        self.act("upload", reportId=rid, kind="source", replaces=old, content=PDF + b"\n%v2")
        current = [f["id"] for f in self.report(rid)["files"]]
        self.assertNotIn(old, current)
        self.assertEqual(self.lin.get(f"/api/files/{old}").data, PDF)
        with self.engine.connect() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(files)), 2)

    def test_only_in_draft(self):
        rid = self.ready()
        self.act("submit", reportId=rid, start=DAY, end=DAY, reviewerId=SHEN)
        self.act("upload", reportId=rid, kind="source", status=422)

    def test_bad_kind_rejected(self):
        rid = self.claim_and_report()
        self.act("upload", reportId=rid, kind="photo", status=422)

    def test_outsider_cannot_download(self):
        rid = self.claim_and_report()
        self.act("upload", reportId=rid, kind="source")
        fid = self.report(rid)["files"][0]["id"]
        self.assertNotEqual(self.login("he").get(f"/api/files/{fid}").status_code, 200)


class UploadLimit(Base):
    """D-119：上限由管理员设置；此处设为 1 MB 验证边界。"""
    pdf_mb = 1

    def test_over_limit_rejected_at_limit_ok(self):
        rid = self.claim_and_report()
        limit = 1024 * 1024
        ok = PDF + b"0" * (limit - len(PDF))
        self.act("upload", reportId=rid, kind="source", content=ok)
        r = self.lin.get(f"/api/samples/1").json["reports"][0]
        self.act("upload", reportId=rid, kind="source", content=ok + b"0",
                 version=r["version"], status=422)


class Submit(Base):
    def test_needs_source_and_draft(self):
        """A-15：至少一份原始记录和一份待签报告。"""
        rid = self.claim_and_report()
        self.act("submit", reportId=rid, start=DAY, end=DAY, reviewerId=SHEN, status=422)
        self.act("upload", reportId=rid, kind="draft")
        self.act("submit", reportId=rid, start=DAY, end=DAY, reviewerId=SHEN, status=422)
        self.act("upload", reportId=rid, kind="source")
        self.act("submit", reportId=rid, start=DAY, end=DAY, reviewerId=SHEN)
        self.assertEqual(self.report(rid)["state"], "review")

    def test_reviewer_must_be_eligible(self):
        """D-75：只能选候选人；本人、无审核授权者均被拒。"""
        rid = self.ready()
        cands = {u["id"] for u in self.report(rid)["reviewers"]}
        self.assertNotIn(LIN, cands)
        self.assertIn(SHEN, cands)
        for bad in (LIN, 4, 999):
            self.act("submit", reportId=rid, start=DAY, end=DAY, reviewerId=bad, status=422)

    def test_date_chain(self):
        rid = self.ready()
        recv = self.detail()["receivedDate"]
        before = (TODAY - timedelta(days=30)).isoformat()
        future = (TODAY + timedelta(days=1)).isoformat()
        # 开始晚于结束；开始早于收样；结束晚于今天
        for start, end in ((DAY, recv), (before, DAY), (DAY, future)):
            self.act("submit", reportId=rid, start=start, end=end, reviewerId=SHEN, status=422)
        self.act("submit", reportId=rid, start=recv, end=DAY, reviewerId=SHEN)

    def test_snapshot_frozen_after_submit(self):
        """A-15：送审资料包冻结——提交后不能再上传、取消。"""
        rid = self.ready()
        self.act("submit", reportId=rid, start=DAY, end=DAY, reviewerId=SHEN)
        self.act("upload", reportId=rid, kind="draft", status=422)
        self.act("cancel", reportId=rid, reason="撤回", status=422)

    def test_double_submit_rejected(self):
        rid = self.ready()
        self.act("submit", reportId=rid, start=DAY, end=DAY, reviewerId=SHEN)
        self.act("submit", reportId=rid, start=DAY, end=DAY, reviewerId=SHEN, status=422)

    def test_site_sample_needs_site_date(self):
        rid = self.ready(sid=2)
        self.act("submit", sid=2, reportId=rid, start=DAY, end=DAY, status=422)
        self.act("submit", sid=2, reportId=rid, start=DAY, end=DAY, siteDate=DAY)

    def test_non_owner_cannot_submit(self):
        rid = self.ready()
        self.act("submit", c=self.login("zhou"), reportId=rid, start=DAY, end=DAY,
                 reviewerId=SHEN, status=403)
        _ = ZHOU
