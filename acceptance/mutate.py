"""变异检查：在临时副本中逐个改坏被测代码，确认验收测试能发现。不修改原代码。
用法：.venv/Scripts/python.exe acceptance/mutate.py
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MUTANTS = [
    ("D-72 退回不查上传", "backend/policy.py",
     '"已上传资料，请走转交。" if self.has_upload else ""', '""'),
    ("A-11 授权不查", "backend/policy.py",
     '("" if self.allowed else "当前检测授权未覆盖样品全部项目和方法。")', '""'),
    ("A-14 不查文件头", "backend/documents.py",
     'or not content.startswith(b"%PDF-")', ''),
    ("A-14 不查大小", "backend/documents.py",
     'if len(content) > max_bytes:', 'if False:'),
    ("A-15 不查原始记录", "backend/policy.py",
     '("请上传原始记录 PDF。" if "source" not in kinds else "")', '""'),
    ("D-59 不排除原作者", "backend/policy.py",
     'query = query.where(users.c.id != self.row.owner, ~users.c.id.in_(authors))',
     'query = query.where(users.c.id != self.row.owner)'),
    ("独占：非负责人可编辑", "backend/policy.py",
     'if self.row.owner != self.actor.id or "test" not in self.actor.permissions:',
     'if "test" not in self.actor.permissions:'),
    ("日期链不查", "backend/reporting.py",
     'if start > end or end > date.today() or (s.received_date and start < s.received_date):',
     'if False:'),
    ("领取不判已领", "backend/commands.py",
     'if action == "claim" and s.owner is not None:', 'if False:'),
]


def main():
    py = sys.executable
    survived = []
    for name, rel, old, new in MUTANTS:
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "p"
            shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(
                ".venv", "node_modules", "wheels", "instance", "__pycache__", "frontend"))
            f = dst / rel
            text = f.read_text(encoding="utf-8")
            if text.count(old) != 1:
                print(f"[跳过] {name}：原文出现 {text.count(old)} 次")
                survived.append(name + "（未注入）")
                continue
            f.write_text(text.replace(old, new), encoding="utf-8")
            r = subprocess.run([py, "-W", "ignore", "-m", "unittest", "discover",
                                "-s", "acceptance", "-t", "."], cwd=dst,
                               capture_output=True, text=True, encoding="utf-8")
            caught = r.returncode != 0
            tail = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else ""
            print(f"[{'发现' if caught else '漏检'}] {name}：{tail}")
            if not caught:
                survived.append(name)
    print("漏检：", survived or "无")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
