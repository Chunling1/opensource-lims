from __future__ import annotations

import json
from pathlib import Path

import click
from flask import Flask, current_app
from sqlalchemy import and_, or_

from .extensions import db


def register_commands(app: Flask) -> None:
    @app.cli.command('esign-release-unreceived')
    @click.option('--flow-id', type=click.IntRange(min=1), required=True)
    @click.option('--role', type=click.Choice(['reviewer', 'approver']), required=True)
    @click.option('--requested-at', required=True, help='Exact appendRequestedAt from this node.')
    @click.option('--evidence', required=True, help='Operator and provider non-acceptance confirmation reference.')
    def esign_release_unreceived(flow_id, role, requested_at, evidence):
        from .functions.esign_stages import release_unreceived
        from .functions.esign_service import EsignServiceError
        if not evidence.strip():
            raise click.UsageError('必须填写经办人及上游确认未受理的凭据编号')
        try:
            release_unreceived(flow_id, role, requested_at, evidence.strip())
        except EsignServiceError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo('已记录核实依据；本次未发送签署请求，可由本人重新准备签署入口。')

    @app.cli.command('report-delivery-initialize-grants')
    @click.option('--apply', is_flag=True, help='One-time user-authorized rollout; no startup regrant.')
    def initialize_delivery_grants(apply):
        from .report_delivery_grants import grant_existing_users
        from .models import User
        if not apply:
            click.echo(json.dumps({'dryRun': True, 'existingUsers': User.query.count()}))
            return
        changes = grant_existing_users()
        db.session.commit()
        click.echo(json.dumps({'applied': len(changes), 'recordedInAudit': True}))

    @app.cli.command("esign-dispatch-pending")
    @click.option("--apply", "apply_changes", is_flag=True, help="Call e签宝; default only lists ready tasks.")
    @click.option("--limit", type=click.IntRange(min=1, max=200), default=50)
    def esign_dispatch_pending_command(apply_changes: bool, limit: int) -> None:
        """Dispatch locally prepared report-signing tasks; safe dry-run by default."""
        from .functions.esign_service import EsignServiceError, dispatch_flow
        from .models import ReportEsignFlow

        rows = ReportEsignFlow.query.filter_by(status="ready").order_by(ReportEsignFlow.id).limit(limit).all()
        result = {"dryRun": not apply_changes, "ready": len(rows), "dispatched": 0, "failed": []}
        if apply_changes:
            for row in rows:
                try:
                    dispatch_flow(row.id)
                    result["dispatched"] += 1
                except EsignServiceError as exc:
                    result["failed"].append({"flowId": row.id, "code": exc.code})
        click.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))

    @app.cli.command("esign-reminders-run")
    @click.option("--apply", "apply_changes", is_flag=True, help="Send one e签宝 batch SMS per user; default is dry-run.")
    def esign_reminders_run_command(apply_changes: bool) -> None:
        """Create daily grouped reminders without sending per-report messages."""
        from datetime import date

        from .functions.esign_service import EsignServiceError, batch_sign_url_for_user
        from .models import EsignReminderLog, ReportEsignFlow, ReportEsignSigner, User

        day = date.today().isoformat()
        user_ids = [row[0] for row in db.session.query(ReportEsignSigner.user_id).join(
            ReportEsignFlow, ReportEsignFlow.id == ReportEsignSigner.flow_id
        ).filter(
            ReportEsignFlow.status == "signing",
            ReportEsignSigner.status.in_(("pending", "signing")),
        ).distinct().all()]
        summary = {"dryRun": not apply_changes, "date": day, "users": len(user_ids), "sent": 0, "skipped": 0, "failed": []}
        for user_id in user_ids:
            existing = EsignReminderLog.query.filter_by(user_id=user_id, reminder_date=day, channel="sms").first()
            if existing:
                summary["skipped"] += 1
                continue
            user = db.session.get(User, user_id)
            pending_count = ReportEsignSigner.query.join(
                ReportEsignFlow, ReportEsignFlow.id == ReportEsignSigner.flow_id
            ).filter(
                ReportEsignSigner.user_id == user_id,
                ReportEsignSigner.status.in_(("pending", "signing")),
                ReportEsignFlow.status == "signing",
            ).count()
            if not apply_changes:
                continue
            log = EsignReminderLog(
                user_id=user_id, reminder_date=day, channel="sms",
                pending_count=pending_count, status="sending",
            )
            db.session.add(log)
            db.session.commit()
            try:
                result = batch_sign_url_for_user(user, notify_sms=True)
                log.batch_serial_id = str(result.get("batchSerialId") or "")
                log.status = "sent"
                summary["sent"] += 1
            except EsignServiceError as exc:
                log.status = "failed"
                log.error_message = f"{exc.code}: {str(exc)}"[:300]
                summary["failed"].append({"userId": user_id, "code": exc.code})
            db.session.commit()
        click.echo(json.dumps(summary, ensure_ascii=False, sort_keys=True))

    @app.cli.command("esign-initial-sms-send")
    @click.option("--flow-id", type=click.IntRange(min=1), required=True)
    @click.option("--retry-failed", is_flag=True, help="Retry only prior failed initial notifications.")
    @click.option("--apply", "apply_changes", is_flag=True, help="Send e签宝 SMS; default is dry-run.")
    def esign_initial_sms_send_command(flow_id: int, retry_failed: bool, apply_changes: bool) -> None:
        """Send or retry the per-signer initial SMS for one signing flow."""
        from .functions.esign_service import EsignServiceError, send_initial_sms_notifications
        from .models import EsignReminderLog, ReportEsignFlow

        flow = db.session.get(ReportEsignFlow, flow_id)
        if not flow:
            raise click.ClickException("flow not found")
        channel = f"initial:{flow.id}"
        if len(channel) > 20:
            import hashlib
            channel = f"initial:{hashlib.sha256(str(flow.id).encode()).hexdigest()[:12]}"
        existing = EsignReminderLog.query.filter_by(channel=channel).count()
        if not apply_changes:
            click.echo(json.dumps({
                "dryRun": True,
                "flowId": flow.id,
                "status": flow.status,
                "signers": len({row.user_id for row in flow.signers}),
                "existingLogs": existing,
            }, ensure_ascii=False, sort_keys=True))
            return
        if not current_app.config.get("ESIGN_INITIAL_SMS_ENABLED"):
            raise click.ClickException("ESIGN_INITIAL_SMS_ENABLED is disabled")
        try:
            summary = send_initial_sms_notifications(flow.id, retry_failed=retry_failed)
        except EsignServiceError as exc:
            raise click.ClickException(f"{exc.code}: {str(exc)}") from exc
        summary["dryRun"] = False
        click.echo(json.dumps(summary, ensure_ascii=False, sort_keys=True))

    @app.cli.command("esign-bindings-import")
    @click.option("--source", type=click.Path(path_type=Path, exists=True), required=True)
    @click.option("--create-missing", is_flag=True, help="Create explicitly mapped missing users and personnel.")
    @click.option("--missing-account", "missing_accounts", multiple=True, metavar="NAME=ACCOUNT")
    @click.option("--department", type=str, default="", help="Department for newly created users.")
    @click.option("--credentials-out", type=click.Path(path_type=Path), default=None)
    @click.option("--apply", "apply_changes", is_flag=True, help="Save bindings; default validates only.")
    def esign_bindings_import_command(
        source: Path,
        create_missing: bool,
        missing_accounts: tuple[str, ...],
        department: str,
        credentials_out: Path | None,
        apply_changes: bool,
    ) -> None:
        """Import user/account/name/mobile bindings from a protected JSON file."""
        from datetime import datetime
        import os
        import secrets

        from .functions.esign_service import EsignServiceError, normalize_psn_account
        from .audit import add_operation_audit
        from .models import (
            Department,
            EsignIdentityBinding,
            Permission,
            Personnel,
            User,
        )
        from .security import hash_password

        payload = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise click.ClickException("source must be a JSON array")
        account_map = {}
        for raw in missing_accounts:
            name, separator, account = str(raw).partition("=")
            if not separator or not name.strip() or not account.strip():
                raise click.ClickException("--missing-account must use NAME=ACCOUNT")
            account_map[name.strip()] = account.strip()
        target_department = None
        if create_missing:
            if not department.strip():
                raise click.ClickException("--department is required with --create-missing")
            matches = Department.query.filter_by(name=department.strip()).all()
            if len(matches) != 1:
                raise click.ClickException("department must match exactly one row")
            target_department = matches[0]
            if apply_changes and not credentials_out:
                raise click.ClickException("--credentials-out is required when creating users")
        generated_credentials = []
        summary = {
            "dryRun": not apply_changes,
            "rows": len(payload),
            "valid": 0,
            "createdUsers": 0,
            "updated": 0,
            "errors": [],
        }
        for index, item in enumerate(payload, 1):
            try:
                created_user = False
                account = str(item.get("account") or "").strip()
                name = str(item.get("name") or "").strip()
                user = User.query.filter(db.func.lower(User.account) == account.lower()).first() if account else None
                if not user and name:
                    matches = User.query.filter_by(name=name, enabled=True).all()
                    user = matches[0] if len(matches) == 1 else None
                if not user and create_missing:
                    mapped_account = account_map.get(name, "")
                    if not mapped_account:
                        raise EsignServiceError("missing_account_mapping", "缺少新用户账号映射")
                    if User.query.filter(db.func.lower(User.account) == mapped_account.lower()).first():
                        raise EsignServiceError("account_conflict", "新用户账号已存在")
                    mobile = normalize_psn_account(item.get("mobile"), "mobile")
                    summary["valid"] += 1
                    if not apply_changes:
                        continue
                    from .platform.identity.login_security import initial_password
                    temp_password = initial_password(mapped_account)
                    user = User(
                        account=mapped_account,
                        name=name,
                        password_hash=hash_password(temp_password),
                        role_key="custom",
                        role_name="检测与报告审核人员",
                        home_path="/inspection/testing/data_entry",
                        department_id=target_department.id,
                        data_scope_type="department",
                        data_scope_desc=f"{target_department.name}：检测录入、报告审核及本人电子签署任务",
                        enabled=True,
                        must_change_password=True,
                    )
                    required_permission_codes = {
                        "dashboard.view",
                        "testing.view",
                        "testing.task_query.view",
                        "testing.data_entry.view",
                        "testing.data_check.view",
                        "report.view",
                        "report.review.view",
                        "report.query.view",
                    }
                    user.permissions = Permission.query.filter(
                        Permission.code.in_(required_permission_codes)
                    ).all()
                    missing_permission_codes = required_permission_codes - {
                        permission.code for permission in user.permissions
                    }
                    if missing_permission_codes:
                        raise EsignServiceError(
                            "permission_catalog_incomplete",
                            "检测录入或报告审核权限目录不完整",
                        )
                    user.project_steps = [
                        step
                        for step in target_department.project_steps
                        if step.step_code in {"data_entry", "report_review"}
                    ]
                    db.session.add(user)
                    db.session.flush()
                    personnel = Personnel(
                        name=name,
                        code=mapped_account,
                        dept=target_department.name,
                        position="电子签署人员",
                        mobile=mobile,
                        assigned_depts=target_department.name,
                        permissions="",
                    )
                    db.session.add(personnel)
                    db.session.flush()
                    created_user = True
                    generated_credentials.append({
                        "name": name,
                        "account": mapped_account,
                        "tempPassword": temp_password,
                    })
                    add_operation_audit(
                        "organization.user.create",
                        "user",
                        user.id,
                        category="security",
                        after={
                            "account": user.account,
                            "name": user.name,
                            "department": target_department.name,
                            "role": user.role_name,
                            "projectStepCount": len(user.project_steps),
                            "mustChangePassword": True,
                        },
                        message="电子签署受限账号导入创建",
                    )
                    summary["createdUsers"] += 1
                if not user:
                    raise EsignServiceError("user_not_found", "未找到唯一登录账号")
                if not created_user:
                    mobile = normalize_psn_account(item.get("mobile"), "mobile")
                    summary["valid"] += 1
                if not apply_changes:
                    continue
                personnel = Personnel.query.filter(db.func.lower(Personnel.code) == user.account.lower()).first()
                if personnel:
                    personnel.mobile = mobile
                row = EsignIdentityBinding.query.filter_by(user_id=user.id).first()
                if not row:
                    row = EsignIdentityBinding(user_id=user.id, legal_name=name or user.name, psn_account=mobile)
                    db.session.add(row)
                row.personnel_id = personnel.id if personnel else None
                row.legal_name = name or user.name
                row.psn_account = mobile
                row.psn_account_kind = "mobile"
                row.status = "pending"
                row.updated_at = datetime.utcnow()
                add_operation_audit(
                    "esign.binding.import",
                    "esign_identity_binding",
                    user.id,
                    category="security",
                    after={
                        "userId": user.id,
                        "account": user.account,
                        "name": row.legal_name,
                        "status": row.status,
                        "accountKind": row.psn_account_kind,
                    },
                    message="电子签署身份绑定导入",
                )
                summary["updated"] += 1
            except (EsignServiceError, AttributeError, TypeError) as exc:
                summary["errors"].append({"row": index, "code": getattr(exc, "code", "invalid_row")})
        if apply_changes and not summary["errors"]:
            db.session.commit()
            if generated_credentials and credentials_out:
                credentials_out.parent.mkdir(parents=True, exist_ok=True)
                credentials_out.write_text(
                    json.dumps(generated_credentials, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                os.chmod(credentials_out, 0o600)
        else:
            db.session.rollback()
        click.echo(json.dumps(summary, ensure_ascii=False, sort_keys=True))


    @app.cli.command("portal-catalog-sync")
    @click.option("--apply", "apply_changes", is_flag=True, help="Commit eligible catalogue rows; default is dry-run.")
    def portal_catalog_sync_command(apply_changes: bool) -> None:
        """Analyze standards/capabilities and synchronize public service objects."""
        from .functions.service_catalog import sync_catalog

        click.echo(json.dumps(sync_catalog(apply_changes=apply_changes), ensure_ascii=False, sort_keys=True))

    @app.cli.command("portal-catalog-diagnostics")
    def portal_catalog_diagnostics_command() -> None:
        """Print catalogue candidates and rejection reasons without changing data."""
        from .functions.service_catalog import public_catalog_diagnostics

        click.echo(json.dumps(public_catalog_diagnostics(), ensure_ascii=False, sort_keys=True))

    @app.cli.command("ai-index-rebuild")
    def ai_index_rebuild_command() -> None:
        """Rebuild the disposable search projection from authoritative tables."""
        from .functions.ai_index import rebuild

        click.echo(json.dumps(rebuild(), ensure_ascii=False, sort_keys=True))

    @app.cli.command("ai-index-run-once")
    @click.option("--limit", type=click.IntRange(min=1, max=5000), default=500)
    def ai_index_run_once_command(limit: int) -> None:
        """Process one OperationAudit increment."""
        from .functions.ai_index import incremental

        click.echo(json.dumps(incremental(limit), ensure_ascii=False, sort_keys=True))

    @app.cli.command("ai-index-status")
    def ai_index_status_command() -> None:
        """Print index watermark and backlog without exposing credentials."""
        from .functions.ai_index import status

        click.echo(json.dumps(status(), ensure_ascii=False, sort_keys=True))

    @app.cli.command("bootstrap-db")
    @click.option("--seed/--no-seed", default=True, show_default=True)
    def bootstrap_db(seed: bool) -> None:
        """Explicitly create a new database and optionally load bootstrap data."""
        if current_app.config.get("PROD"):
            raise click.ClickException(
                "production database bootstrap is forbidden; use Flask-Migrate upgrades only"
            )
        if seed:
            from .seed import seed_all

            seed_all()
        else:
            _register_all_models()
            db.create_all()
        click.echo("database bootstrap complete")

    @app.cli.command("import-reference-data")
    @click.option("--data-dir", type=click.Path(path_type=Path), default=None)
    @click.option("--apply", "apply_changes", is_flag=True, help="Commit imports; default is dry-run.")
    def import_reference_data(data_dir: Path | None, apply_changes: bool) -> None:
        """Validate or import the five legacy JSON reference datasets."""
        from .functions.reference_data_import import import_all_reference_data

        root = data_dir or Path(current_app.root_path) / "data"
        summaries = import_all_reference_data(root, dry_run=not apply_changes)
        for dataset, summary in summaries.items():
            click.echo(
                f"{dataset}: source={summary.source_rows}, inserted={summary.inserted}, "
                f"adopted={summary.adopted}, conflicts={summary.conflicts}, skipped={summary.skipped}"
            )
        if apply_changes:
            linked = _reconcile_standard_links()
            db.session.commit()
            click.echo(f"controlled standard links reconciled: {linked}")

    @app.cli.command("replace-standard-library")
    @click.option(
        "--source",
        type=click.Path(path_type=Path, exists=True, dir_okay=False, readable=True),
        required=True,
    )
    @click.option(
        "--apply",
        "apply_changes",
        is_flag=True,
        help="Commit the governed replacement; default is a transactionally rolled-back dry run.",
    )
    def replace_standard_library_command(source: Path, apply_changes: bool) -> None:
        """Replace both standard projections from one reviewed canonical payload."""
        from .applications.quality_resources.commands import replace_standard_library

        try:
            summary = replace_standard_library(source, apply_changes=apply_changes)
        except (OSError, ValueError, RuntimeError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(json.dumps(summary.as_dict(), ensure_ascii=False, sort_keys=True))

    @app.cli.command("migrate-departments")
    def migrate_departments() -> None:
        """Apply the idempotent department master-data merge to an existing database."""
        from .seed import _sync_departments

        _sync_departments()
        db.session.commit()
        click.echo("department master migration complete")

    @app.cli.command("import-personnel-accounts")
    @click.option("--source", type=click.Path(path_type=Path), default=None)
    @click.option("--password-output", type=click.Path(path_type=Path), default=None, help="Private new CSV file for randomly generated initial passwords.")
    @click.option("--apply", "apply_changes", is_flag=True, help="Commit the import; default is dry-run.")
    def import_personnel_accounts_command(source: Path | None, apply_changes: bool, password_output: Path | None) -> None:
        """Import the reviewed personnel roster and create minimum-permission accounts."""
        from .personnel_accounts import DEFAULT_SOURCE_NAME, import_personnel_accounts

        source_path = source or Path(current_app.root_path) / "data" / DEFAULT_SOURCE_NAME
        summary = import_personnel_accounts(source_path, apply_changes=apply_changes, password_output=password_output)
        click.echo(json.dumps(summary.as_dict(), ensure_ascii=False, sort_keys=True))

    @app.cli.command("repair-personnel-account-logins")
    @click.option("--source", type=click.Path(path_type=Path), default=None)
    @click.option("--apply", "apply_changes", is_flag=True, help="Commit repairs; default is dry-run.")
    @click.option(
        "--reset-account",
        "reset_accounts",
        multiple=True,
        help="Retired command; use administrator login security to generate random initial passwords.",
    )
    def repair_personnel_account_logins_command(
        source: Path | None,
        apply_changes: bool,
        reset_accounts: tuple[str, ...],
    ) -> None:
        """Repair pending first-login passwords and unlock roster accounts safely."""
        from .personnel_accounts import (
            DEFAULT_SOURCE_NAME,
            repair_personnel_account_logins,
        )

        source_path = source or Path(current_app.root_path) / "data" / DEFAULT_SOURCE_NAME
        summary = repair_personnel_account_logins(
            source_path,
            apply_changes=apply_changes,
            reset_accounts=frozenset(account.strip().lower() for account in reset_accounts),
        )
        click.echo(json.dumps(summary.as_dict(), ensure_ascii=False, sort_keys=True))

    @app.cli.command("import-appointment-authorizations")
    @click.option("--source", type=click.Path(path_type=Path), default=None)
    @click.option("--apply", "apply_changes", is_flag=True, help="Commit the import; default is dry-run.")
    def import_appointment_authorizations_command(source: Path | None, apply_changes: bool) -> None:
        """Import report-category projects and named personnel authorizations."""
        from .appointment_authorizations import (
            DEFAULT_SOURCE_NAME,
            import_appointment_authorizations,
        )

        source_path = source or Path(current_app.root_path) / "data" / DEFAULT_SOURCE_NAME
        summary = import_appointment_authorizations(source_path, apply_changes=apply_changes)
        click.echo(json.dumps(summary.as_dict(), ensure_ascii=False, sort_keys=True))

    @app.cli.command("import-cnas-capabilities")
    @click.option("--source", type=click.Path(path_type=Path, exists=True), required=True)
    @click.option("--apply", "apply_changes", is_flag=True, help="Commit a review batch; default is dry-run.")
    @click.option("--activate", is_flag=True, help="Activate only when extraction and department mapping have no exceptions.")
    @click.option("--report", "report_path", type=click.Path(path_type=Path), default=None)
    def import_cnas_capabilities_command(
        source: Path,
        apply_changes: bool,
        activate: bool,
        report_path: Path | None,
    ) -> None:
        """Validate/import official CNAS capability PDF attachments."""
        from .cnas_capabilities import import_capability_source

        summary = import_capability_source(
            source,
            apply_changes=apply_changes,
            activate=activate,
            report_path=report_path,
        )
        click.echo(json.dumps(summary, ensure_ascii=False, sort_keys=True))

    @app.cli.command("activate-confirmed-cnas-capabilities")
    @click.option("--batch-id", type=click.IntRange(min=1), required=True)
    @click.option("--review-note", required=True, help="Review basis recorded in the batch audit summary.")
    @click.option("--apply", "apply_changes", is_flag=True, help="Commit activation; default is dry-run.")
    def activate_confirmed_cnas_capabilities_command(
        batch_id: int,
        review_note: str,
        apply_changes: bool,
    ) -> None:
        """Activate every mapped capability row in a review batch, with an audit note."""
        from .cnas_capabilities import activate_confirmed_capability_entries
        from .models import CapabilityEntry, CapabilityImportBatch

        batch = db.session.get(CapabilityImportBatch, batch_id)
        if not batch or batch.status == "retired":
            raise click.ClickException("CNAS capability batch does not exist or is retired.")
        candidates = (
            CapabilityEntry.query.filter(
                CapabilityEntry.batch_id == batch.id,
                CapabilityEntry.mapping_status == "confirmed",
                CapabilityEntry.departments.any(),
            )
            .order_by(CapabilityEntry.id)
            .all()
        )
        inactive_ids = [entry.id for entry in candidates if not entry.active]
        summary = {
            "batchId": batch.id,
            "batchStatus": batch.status,
            "confirmedMapped": len(candidates),
            "alreadyActive": len(candidates) - len(inactive_ids),
            "toActivate": len(inactive_ids),
            "dryRun": not apply_changes,
        }
        if apply_changes and inactive_ids:
            try:
                activate_confirmed_capability_entries(
                    batch.id,
                    inactive_ids,
                    review_note=review_note,
                )
                db.session.commit()
            except Exception:
                db.session.rollback()
                raise
        click.echo(json.dumps(summary, ensure_ascii=False, sort_keys=True))

    @app.cli.command("migrate-legacy-files")
    @click.option("--apply", "apply_changes", is_flag=True, help="Persist files and metadata.")
    @click.option(
        "--purge-legacy",
        is_flag=True,
        help="After checksum verification, clear migrated BLOB columns.",
    )
    @click.option("--limit", type=click.IntRange(min=1), default=None)
    def migrate_legacy_files(
        apply_changes: bool,
        purge_legacy: bool,
        limit: int | None,
    ) -> None:
        """Move legacy BLOB content to private storage and optionally purge it."""
        from .functions.file_migration import migrate_legacy_bytes
        from .platform.file_vault import storage_backend
        from .models import ReportAttachment, ReportDocumentVersion

        attachment_query = ReportAttachment.query.filter(
            ReportAttachment.file_id.is_(None), ReportAttachment.data.is_not(None)
        ).order_by(ReportAttachment.id)
        version_query = ReportDocumentVersion.query.filter(
            or_(
                and_(ReportDocumentVersion.docx_file_id.is_(None), ReportDocumentVersion.docx_data.is_not(None)),
                and_(ReportDocumentVersion.pdf_file_id.is_(None), ReportDocumentVersion.pdf_data.is_not(None)),
            )
        ).order_by(ReportDocumentVersion.id)
        attachments = attachment_query.limit(limit).all() if limit else attachment_query.all()
        remaining = None if limit is None else max(0, limit - len(attachments))
        versions = version_query.limit(remaining).all() if remaining is not None else version_query.all()
        candidates = len(attachments) + sum(
            int(row.docx_file_id is None and row.docx_data is not None)
            + int(row.pdf_file_id is None and row.pdf_data is not None)
            for row in versions
        )
        if not apply_changes:
            if purge_legacy:
                raise click.UsageError("--purge-legacy requires --apply")
            click.echo(f"dry-run: {candidates} legacy files are eligible; pass --apply to migrate")
            return
        storage = storage_backend()
        migrated = 0
        for row in attachments:
            result = migrate_legacy_bytes(
                db.session, storage, row.data,
                category="report_attachment", original_name=row.name,
                content_type=row.content_type or "application/octet-stream",
                created_by=row.uploaded_by,
            )
            row.stored_file = result.stored_file
            db.session.commit()
            migrated += 1
        for row in versions:
            if row.docx_file_id is None and row.docx_data is not None:
                result = migrate_legacy_bytes(
                    db.session, storage, row.docx_data,
                    category="report_document",
                    original_name=f"{row.report_no}-V{row.version_no}.docx",
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    created_by=row.created_by,
                )
                row.docx_file = result.stored_file
                db.session.commit()
                migrated += 1
            if row.pdf_file_id is None and row.pdf_data is not None:
                result = migrate_legacy_bytes(
                    db.session, storage, row.pdf_data,
                    category="report_document",
                    original_name=f"{row.report_no}-V{row.version_no}.pdf",
                    content_type="application/pdf",
                    created_by=row.created_by,
                )
                row.pdf_file = result.stored_file
                db.session.commit()
                migrated += 1
        purged = _purge_verified_legacy_blobs(storage, limit=limit) if purge_legacy else 0
        click.echo(f"legacy file migration complete: migrated={migrated}, purged={purged}")

    @app.cli.command("seed-external-portal-v1")
    @click.option(
        "--apply",
        "apply_changes",
        is_flag=True,
        help="Create missing V1 public schemes; default is dry-run.",
    )
    def seed_external_portal_v1(apply_changes: bool) -> None:
        """Publish up to five reviewed, existing projects for the V1 test portal.

        This command never invents a project and never overwrites an existing
        external scheme.  Re-running it is therefore safe after administrators
        have edited public titles, prices or promotion copy in project master.
        """
        import re
        from datetime import datetime

        from .models import ExternalScheme, Project

        preferred_codes = ("CN", "DN", "HB", "HF", "RD")
        projects = Project.query.filter(Project.active.is_(True)).all()
        by_code = {}
        for project in projects:
            visible_codes = {
                str(project.code or "").strip().upper(),
                str(project.display_code or "").strip().upper(),
                str(project.number_code or "").strip().upper(),
            }
            for code in visible_codes:
                if code and code not in by_code:
                    by_code[code] = project

        selected = []
        seen_ids = set()
        for code in preferred_codes:
            project = by_code.get(code)
            if project is not None and project.id not in seen_ids:
                selected.append(project)
                seen_ids.add(project.id)

        existing_by_project = {
            row.project_id: row
            for row in ExternalScheme.query.filter(
                ExternalScheme.project_id.in_([row.id for row in selected] or [-1])
            ).all()
        }
        candidates = [row for row in selected if row.id not in existing_by_project]
        summary = {
            "dryRun": not apply_changes,
            "preferredCodes": list(preferred_codes),
            "matchedProjects": [
                {
                    "id": row.id,
                    "code": row.display_code or row.number_code or row.code,
                    "name": row.name,
                }
                for row in selected
            ],
            "existingSchemeCount": len(existing_by_project),
            "candidateCount": len(candidates),
            "createdCount": 0,
        }
        if not apply_changes:
            click.echo(json.dumps(summary, ensure_ascii=False, sort_keys=True))
            return

        created = []
        try:
            for order, project in enumerate(candidates, start=1):
                visible_code = str(
                    project.display_code or project.number_code or project.code or project.id
                ).strip()
                slug = re.sub(r"[^a-z0-9]+", "-", visible_code.lower()).strip("-")
                slug = slug or f"project-{project.id}"
                if ExternalScheme.query.filter_by(slug=slug).first():
                    slug = f"{slug}-{project.id}"
                department_name = project.department.name if project.department else ""
                row = ExternalScheme(
                    project=project,
                    slug=slug,
                    published=True,
                    public_title=project.name,
                    subtitle=f"{department_name}专业检测服务" if department_name else "专业检测服务",
                    summary=f"提供{project.name}检测咨询、预估报价与在线委托服务。",
                    description=(
                        f"本方案对应内部检测项目 {visible_code}，网上报价为预估信息，"
                        "最终范围、周期与价格以受理后的正式委托为准。"
                    ),
                    category=department_name or "检测服务",
                    price_mode="quote",
                    price_unit="项",
                    service_cycle_text="受理后确认",
                    feature_tags=["专业检测", "在线委托"],
                    deliverables=["检测报告"],
                    pricing_rules={},
                    display_order=100 - order,
                    version=1,
                    published_at=datetime.utcnow(),
                    updated_by="seed-external-portal-v1",
                )
                db.session.add(row)
                created.append(project.id)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        summary["createdCount"] = len(created)
        summary["createdProjectIds"] = created
        click.echo(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def _purge_verified_legacy_blobs(storage, *, limit: int | None = None) -> int:
    import hashlib

    from .models import ReportAttachment, ReportDocumentVersion

    candidates = []
    for row in ReportAttachment.query.filter(
        ReportAttachment.file_id.is_not(None),
        ReportAttachment.data.is_not(None),
    ).order_by(ReportAttachment.id):
        candidates.append((row, "data", row.stored_file))
    for row in ReportDocumentVersion.query.order_by(ReportDocumentVersion.id):
        if row.docx_file_id is not None and row.docx_data is not None:
            candidates.append((row, "docx_data", row.docx_file))
        if row.pdf_file_id is not None and row.pdf_data is not None:
            candidates.append((row, "pdf_data", row.pdf_file))
    if limit is not None:
        candidates = candidates[:limit]

    try:
        for row, attribute, stored_file in candidates:
            legacy = bytes(getattr(row, attribute))
            expected = (len(legacy), hashlib.sha256(legacy).hexdigest())
            if (
                stored_file is None
                or stored_file.status != "active"
                or (stored_file.size_bytes, stored_file.sha256) != expected
                or storage.checksum(stored_file.storage_key) != expected
            ):
                raise click.ClickException(
                    f"legacy BLOB verification failed for {row.__tablename__}.{row.id}.{attribute}"
                )
            setattr(row, attribute, None)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return len(candidates)


def _register_all_models() -> None:
    from . import models  # noqa: F401
    from .data_models import files, reference_imports  # noqa: F401


def _reconcile_standard_links() -> int:
    from .models import Standard, StdLibraryItem

    standard_by_code = {row.code: row.id for row in Standard.query.filter_by(deleted_at=None).all()}
    linked = 0
    for row in StdLibraryItem.query.filter_by(standard_id=None, deleted_at=None).all():
        standard_id = standard_by_code.get(row.code)
        if standard_id:
            row.standard_id = standard_id
            linked += 1
    return linked


__all__ = ["register_commands"]
