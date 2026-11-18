"""A-11 领取、A-12 转交、退回待领取池（D-72）、独占编辑、D-59 回避。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

from sqlalchemy import update

from acceptance.base import HEAD, HE, LIN, LU, SHEN, TODAY, ZHOU, Base
from backend.schema import grants


class Claim(Base):
    def test_claim_sets_owner_and_leaves_pool(self):
        before = self.pool()["total"]
        self.act("claim")
        d = self.detail()
        self.assertEqual(d["owner"], "林澄")
        self.assertEqual(self.pool()["total"], before - 1)
        self.assertEqual(self.pool(view="mine")["total"], 1)

    def test_concurrent_claim_only_one_wins(self):
        """附表D A-11 测试点：并发领取只有一人成功。"""
        zhou = self.login("zhou")
        gate = Barrier(2)

        def go(c):
            gate.wait()
            return c.post("/api/samples/1/claim",
                          json={"version": 1, "requestId": str(uuid4())}, headers=HEAD).status_code

        with ThreadPoolExecutor(2) as ex:
            codes = sorted(ex.map(go, [self.lin, zhou]))
        self.assertEqual(codes[0], 200)
        self.assertNotEqual(codes[1], 200)
        self.assertIn(self.detail()["owner"], {"林澄", "周禾"})

    def test_claim_already_owned_rejected(self):
        self.act("claim")
        self.act("claim", c=self.login("zhou"), version=self.detail()["version"], status=409)

    def test_expired_grant_rejected(self):
        """附表D A-11 测试点：授权过期被拒（陆川授权昨日前已到期）。"""
        self.act("claim", c=self.login("lu"), status=422)

    def test_grant_expiring_mid_way_blocks_claim(self):
        with self.engine.begin() as db:
            db.execute(update(grants).where(grants.c.user_id == LIN, grants.c.duty == "test")
                       .values(end=TODAY - timedelta(days=1)))
        self.act("claim", status=422)

    def test_partial_coverage_rejected(self):
        """授权须覆盖全部项目和方法：删去一项授权即不得领取。"""
        with self.engine.begin() as db:
            db.execute(update(grants).where(grants.c.user_id == LIN, grants.c.duty == "test",
                                            grants.c.scope.like("电导率%"))
                       .values(end=TODAY - timedelta(days=1)))
        self.act("claim", status=422)

    def test_not_reviewed_not_received_frozen_rejected(self):
        for sid in (3, 4, 6):  # 未收样、已冻结、未评审
            self.act("claim", sid=sid, status=422)

    def test_stale_version_rejected(self):
        self.act("claim", version=99, status=409)

    def test_replay_same_request_is_idempotent(self):
        key = str(uuid4())
        first = self.act("claim", version=1, key=key)
        self.assertEqual(self.act("claim", version=1, key=key), first)


class ReturnToPool(Base):
    def test_return_needs_reason(self):
        self.act("claim")
        self.act("return", reason="   ", status=400)

    def test_return_before_upload_ok(self):
        """D-72：未上传资料时可填原因退回。"""
        self.claim_and_report()
        self.act("return", reason="重新排班")
        self.assertIsNone(self.detail()["owner"])
        self.act("claim", c=self.login("zhou"))

    def test_return_after_upload_blocked(self):
        """D-72：已上传资料只能转交。"""
        rid = self.claim_and_report()
        self.act("upload", reportId=rid, kind="source")
        self.act("return", reason="重新排班", status=422)

    def test_only_owner_can_return(self):
        self.act("claim")
        self.act("return", c=self.login("zhou"), reason="x", status=403)


class Transfer(Base):
    def test_transfer_needs_reason_and_target(self):
        self.act("claim")
        self.act("transfer", reason="  ", targetId=ZHOU, status=400)
        self.act("transfer", reason="换人", status=400)

    def test_target_without_coverage_rejected(self):
        """A-12：接收人授权须覆盖全部（陆川过期、沈宁无检测职责）。"""
        self.act("claim")
        for uid in (LU, SHEN):
            self.act("transfer", reason="换人", targetId=uid, status=422)

    def test_transfer_moves_ownership_and_edit_rights(self):
        """A-12：转交后原负责人失去编辑权限。"""
        rid = self.claim_and_report()
        self.act("upload", reportId=rid, kind="source")
        self.act("transfer", reason="更换人员", targetId=ZHOU)
        self.assertEqual(self.detail()["owner"], "周禾")
        self.act("upload", reportId=rid, kind="draft", status=403)
        self.act("create", ruleId=1, status=403)
        zhou = self.login("zhou")
        self.act("upload", c=zhou, reportId=rid, kind="draft")

    def test_former_author_cannot_review(self):
        """D-59：转交前录入过资料的人不在审核候选中，也不能被指定。"""
        rid = self.claim_and_report()
        self.act("upload", reportId=rid, kind="source")
        self.act("transfer", reason="更换人员", targetId=ZHOU)
        zhou = self.login("zhou")
        self.act("upload", c=zhou, reportId=rid, kind="draft")
        ids = {u["id"] for u in self.report(rid, c=zhou)["reviewers"]}
        self.assertNotIn(LIN, ids)
        self.assertNotIn(ZHOU, ids)
        self.act("submit", c=zhou, reportId=rid, start=self.detail()["receivedDate"],
                 end=TODAY.isoformat(), reviewerId=LIN, status=422)

    def test_cross_department_target_sees_sample(self):
        self.act("claim")
        self.act("transfer", reason="跨部门协作", targetId=HE)
        self.assertEqual(self.pool(c=self.login("he"), view="mine")["total"], 1)


class Exclusive(Base):
    """说明书 436 行：只有负责人能上传、修改、提交；同资格他人只能看。"""

    def test_peer_with_same_grant_cannot_edit(self):
        rid = self.claim_and_report()
        zhou = self.login("zhou")
        self.act("upload", c=zhou, reportId=rid, kind="source", status=403)
        self.act("create", c=zhou, ruleId=1, status=403)
        self.act("cancel", c=zhou, reportId=rid, reason="x", status=403)
        self.assertEqual(self.report(rid, c=zhou)["actions"], {})

    def test_catalog_admin_cannot_edit(self):
        rid = self.claim_and_report()
        zi = self.login("zi")
        self.act("upload", c=zi, reportId=rid, kind="source", status=403)
