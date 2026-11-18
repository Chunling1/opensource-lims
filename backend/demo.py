from datetime import date, timedelta

from sqlalchemy import select
from werkzeug.security import generate_password_hash

from .schema import grants, items, samples, sequences, tasks, templates, users


def seed_demo(engine):
    today = date.today()
    day = today - timedelta(days=3)
    with engine.begin() as db:
        if db.scalar(select(users.c.id).limit(1)):
            return False
        accounts = [
            ("lin", "林澄", "水质组", ["claim", "test", "review", "transfer"]),
            ("zhou", "周禾", "水质组", ["claim", "test", "review"]),
            ("shen", "沈宁", "水质组", ["review"]),
            ("lu", "陆川", "水质组", ["claim", "test"]),
            ("he", "何杉", "材料组", ["claim", "test"]),
            ("zi", "顾桐", "水质组", ["catalog"]),
        ]
        password = generate_password_hash("LimsDemo2026")
        scope = "酸碱度 / 虚构方法 W-01"
        extra = "电导率 / 虚构方法 W-02"
        for account, name, department, permissions in accounts:
            uid = db.scalar(
                users.insert()
                .values(
                    account=account,
                    name=name,
                    department=department,
                    permissions=permissions,
                    password_hash=password,
                )
                .returning(users.c.id)
            )
            for duty in {"test", "review"}.intersection(permissions):
                for item in [scope, extra]:
                    db.execute(
                        grants.insert().values(
                            user_id=uid,
                            duty=duty,
                            scope=item,
                            start=day,
                            end=day if account == "lu" else today + timedelta(days=365),
                        )
                    )
        physical = db.scalar(
            templates.insert()
            .values(
                label="水样常规检测 · v1",
                review_mode="designated",
                physical=True,
                receive_required=True,
            )
            .returning(templates.c.id)
        )
        site = db.scalar(
            templates.insert()
            .values(label="现场测量 · v1", review_mode="pool", physical=False, receive_required=False)
            .returning(templates.c.id)
        )
        for i, (name, template, reviewed, received, frozen, dept) in enumerate(
            [
                ("溪流水样", physical, True, True, False, "水质组"),
                ("河岸测点", site, True, False, False, "水质组"),
                ("水槽水样", physical, True, False, False, "水质组"),
                ("复核留样", physical, True, True, True, "水质组"),
                ("材料浸出液", physical, True, True, False, "材料组"),
                ("待评审水样", physical, False, True, False, "水质组"),
            ],
            start=1,
        ):
            sid = db.scalar(
                samples.insert()
                .values(
                    number=f"YP-{i:04d}",
                    name=name,
                    commission=f"WT-{i:04d}",
                    department=dept,
                    template_id=template,
                    reviewed=reviewed,
                    received=received,
                    received_date=day if received else None,
                    commission_date=day,
                    frozen=frozen,
                    version=1,
                )
                .returning(samples.c.id)
            )
            db.execute(items.insert(), [dict(sample_id=sid, scope=x) for x in (scope, extra)])
            if reviewed and not frozen and (received or template == site):
                db.execute(tasks.insert().values(sample_id=sid, kind="claim", closed=False))
        for prefix in ["BG", "XC"]:
            db.execute(sequences.insert().values(prefix=prefix, last=0))
        return True
