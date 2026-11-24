"""Permission-scoped AI workbench APIs. Business mutations are deliberately absent."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import threading
import time
from datetime import datetime, timedelta

from flask import Blueprint, Response, current_app, g, jsonify, request, stream_with_context
from sqlalchemy import text

from ..platform.audit import add_operation_audit
from ..extensions import db
from ..forms.ai_forms import FormDraftError, schema_fields, validate_form_draft
from ..functions import ai_provider
from ..functions.ai_analysis import available_templates, resolve_template, run_analysis
from ..functions.ai_index import incremental, reauthorize_results, search, search_response, status
from ..models import AiSearchDictionary, OperationAudit
from ..security import require_auth

bp = Blueprint("ai", __name__, url_prefix="/api/ai")
ALLOWED_AUDIO_TYPES = {"audio/webm", "audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp4", "audio/ogg"}
_index_refresh_lock = threading.Lock()
_last_index_refresh = 0.0


@bp.after_request
def _prevent_ai_response_caching(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


def _error(message, status_code=400):
    return jsonify({"code": status_code, "message": message, "data": None}), status_code


def _require_permission(action=None):
    if "system.ai_assistant.view" not in g.current_user.permission_codes():
        return _error("无 AI 工作台权限", 403)
    if action and action not in g.current_user.action_codes():
        return _error("无 AI 语音录入权限", 403)
    return None


def _require_enabled(voice=False, provider=True):
    if not current_app.config.get("AI_ENABLED"):
        return _error("AI 功能尚未启用", 503)
    if provider and not (current_app.config.get("AI_BASE_URL") and current_app.config.get("AI_API_KEY")):
        return _error("AI 服务密文或北京地域端点尚未配置", 503)
    if voice and not current_app.config.get("AI_VOICE_ENABLED"):
        return _error("AI 语音功能尚未启用", 503)
    return None


def _refresh_index_best_effort():
    """Refresh only during AI requests; failures never escape into business APIs."""
    global _last_index_refresh
    if not current_app.config.get("AI_INDEX_ON_REQUEST", True):
        return
    now = time.monotonic()
    interval = max(5, int(current_app.config.get("AI_INDEX_INTERVAL_SECONDS", 30)))
    if now - _last_index_refresh < interval or not _index_refresh_lock.acquire(blocking=False):
        return
    try:
        incremental(current_app.config.get("AI_INDEX_BATCH_SIZE", 500))
        _last_index_refresh = time.monotonic()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("AI lazy index refresh failed; serving the last good index")
    finally:
        _index_refresh_lock.release()


def _is_ai_admin():
    department = getattr(g.current_user, "department", None)
    return g.current_user.role_key == "admin" or bool(
        department and (department.code == "ROOT" or department.name == "示例检测机构")
    )


def _rate_limited(action: str, maximum=30):
    since = datetime.utcnow() - timedelta(minutes=1)
    count = OperationAudit.query.filter(
        OperationAudit.user_id == g.current_user.id,
        OperationAudit.action == action,
        OperationAudit.created_at >= since,
        OperationAudit.success.is_(True),
    ).count()
    return count >= maximum


def _audit(action, *, result_ids=None, elapsed_ms=0, fields=None, token_usage=None):
    add_operation_audit(
        action, "ai_session", hashlib.sha256(f"{g.current_user.id}:{time.time_ns()}".encode()).hexdigest()[:16],
        category="ai", before=None, after={
            "model": current_app.config.get("AI_CHAT_MODEL"),
            "resultIds": list(result_ids or [])[:50],
            "fields": list(fields or [])[:30],
            "elapsedMs": int(elapsed_ms),
            "tokenUsage": {
                key: max(0, int(value or 0))
                for key, value in (token_usage or {}).items()
                if key in {"inputTokens", "outputTokens", "totalTokens"}
            },
        }, message="AI 仅生成只读回答或内存表单草稿",
    )


def _redact(value: str) -> str:
    value = str(value or "")
    value = re.sub(r"(?<!\d)1\d{10}(?!\d)", "[手机号已脱敏]", value)
    value = re.sub(r"(?<!\d)\d{15,18}[0-9Xx](?!\d)", "[证件号已脱敏]", value)
    value = re.sub(r"(?<!\d)\d{16,19}(?!\d)", "[账号已脱敏]", value)
    return value


def _redact_with_map(value: str, replacements: dict[str, str]):
    value = str(value or "")
    patterns = (
        (r"(?<!\d)1\d{10}(?!\d)", "PHONE"),
        (r"(?<!\d)\d{15,18}[0-9Xx](?!\d)", "IDENTITY"),
        (r"(?<!\d)\d{16,19}(?!\d)", "ACCOUNT"),
    )
    for pattern, label in patterns:
        def replace(match, replacement_label=label):
            token = f"[{replacement_label}_{len(replacements) + 1}]"
            replacements[token] = match.group(0)
            return token

        value = re.sub(pattern, replace, value)
    return value


def _restore_placeholders(value, replacements):
    if isinstance(value, list):
        return [_restore_placeholders(item, replacements) for item in value]
    if not isinstance(value, str):
        return value
    for token, original in replacements.items():
        value = value.replace(token, original)
    return value


def _safe_filters(payload) -> dict:
    raw = payload.get("filters") if isinstance(payload.get("filters"), dict) else {}
    return {
        "entityTypes": [str(value)[:40] for value in (raw.get("entityTypes") or [])[:10]],
        "statuses": [str(value)[:60] for value in (raw.get("statuses") or [])[:20]],
        "project": str(raw.get("project") or "")[:120],
        "dateFrom": str(raw.get("dateFrom") or "")[:10],
        "dateTo": str(raw.get("dateTo") or "")[:10],
    }


def _rerank_rows(query: str, rows: list[dict]) -> tuple[list[dict], dict]:
    if not current_app.config.get("AI_RERANK_ENABLED") or not rows:
        return rows, {"enabled": False, "status": "local"}
    maximum = max(1, min(int(current_app.config.get("AI_RERANK_CANDIDATES", 30)), 30))
    safe_rows = [{
        **row,
        "title": _redact(row.get("title") or ""),
        "summary": _redact(row.get("summary") or ""),
    } for row in rows[:maximum]]
    try:
        ranking, token_usage = ai_provider.rerank(_redact(query), safe_rows)
    except ai_provider.AiProviderError as exc:
        current_app.logger.warning("AI rerank fallback: %s", exc)
        return rows, {"enabled": True, "status": "fallback"}
    rank_by_id = {item["id"]: (index, item) for index, item in enumerate(ranking)}
    local_position = {row["id"]: index for index, row in enumerate(rows)}
    enriched = []
    for row in rows:
        rank = rank_by_id.get(row["id"])
        enriched.append({
            **row,
            "rerankScore": rank[1]["score"] if rank else None,
            "rerankReason": rank[1]["reason"] if rank else "",
        })
    enriched.sort(key=lambda row: (
        0 if row.get("exactMatch") else 1,
        rank_by_id.get(row["id"], (maximum + local_position[row["id"]], {}))[0],
        local_position[row["id"]],
    ))
    return enriched, {
        "enabled": True, "status": "applied", "candidates": len(safe_rows),
        "tokenUsage": token_usage,
    }


def _history(payload) -> list[dict]:
    maximum = max(0, min(int(current_app.config.get("AI_CHAT_MAX_TURNS", 6)), 8))
    result = []
    for turn in (payload.get("history") or [])[-maximum:]:
        if not isinstance(turn, dict) or turn.get("role") not in {"user", "assistant"}:
            continue
        content = _redact(str(turn.get("content") or "").strip()[:1000])
        if content:
            result.append({"role": turn["role"], "content": content})
    return result


def _validated_citations(answer: str, rows: list[dict]) -> tuple[str, list[dict]]:
    allowed = {
        int(row.get("_citationNumber") or index + 1): row
        for index, row in enumerate(rows)
    }
    used = []

    def replace(match):
        number = int(match.group(1))
        if number not in allowed:
            return "[引用不可用]"
        if number not in used:
            used.append(number)
        return f"[{number}]"

    cleaned = re.sub(r"\[(\d{1,3})\]", replace, str(answer or ""))
    citations = [{
        "number": number,
        "item": {key: value for key, value in allowed[number].items() if not key.startswith("_")},
    } for number in used]
    if rows and not citations:
        first_number = min(allowed)
        citations = [{
            "number": first_number,
            "item": {key: value for key, value in allowed[first_number].items() if not key.startswith("_")},
        }]
        cleaned = cleaned.rstrip() + f"\n\n依据记录：[{first_number}]"
    return cleaned, citations


@bp.post("/search")
@require_auth
def search_api():
    denied = _require_permission() or _require_enabled(provider=False)
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    query = str(payload.get("query") or "").strip()[:200]
    if not query:
        return _error("请输入检索内容")
    _refresh_index_best_effort()
    filters = _safe_filters(payload)
    if current_app.config.get("AI_SEARCH_V2_ENABLED"):
        data = search_response(
            g.current_user, query, filters,
            payload.get("pageSize") or payload.get("limit") or 20,
            payload.get("cursor"),
        )
        data["items"], data["rerank"] = _rerank_rows(query, data["items"])
        if data["rerank"].get("status") == "applied":
            _audit(
                "ai.rerank", result_ids=[row["id"] for row in data["items"]],
                token_usage=data["rerank"].get("tokenUsage"), fields=["redacted_candidates"],
            )
            db.session.commit()
        data["rerank"].pop("tokenUsage", None)
    else:
        data = {"items": search(g.current_user, query, payload.get("limit") or 20, filters)}
    return jsonify({"code": 0, "message": "ok", "data": data})


@bp.post("/chat/stream")
@require_auth
def chat_stream():
    denied = _require_permission() or _require_enabled()
    if denied:
        return denied
    if _rate_limited("ai.chat", 20):
        return _error("请求过于频繁，请稍后再试", 429)
    payload = request.get_json(silent=True) or {}
    question = _redact(str(payload.get("question") or "").strip()[:1000])
    if not question:
        return _error("请输入问题")
    _refresh_index_best_effort()
    started = time.monotonic()
    filters = _safe_filters(payload)
    analysis = None
    template_id = str(payload.get("templateId") or "")[:60]
    analysis_mode = payload.get("mode") == "analysis" or bool(template_id)
    if analysis_mode:
        if not current_app.config.get("AI_ANALYSIS_ENABLED"):
            return _error("AI 业务分析尚未启用", 503)
        template_id = template_id or resolve_template(question)
        if not template_id:
            return _error("请选择一个业务分析模板")
        try:
            analysis = run_analysis(
                g.current_user, template_id, filters,
                current_app.config.get("AI_ANALYSIS_MAX_SOURCES", 20),
            )
        except PermissionError as exc:
            return _error(str(exc), 403)
        except ValueError as exc:
            return _error(str(exc))
        rows = list(analysis.get("sources") or [])
    else:
        rows = search(g.current_user, question, 20, filters)
        rows, _rerank = _rerank_rows(question, rows)
    token_usage = {}
    try:
        if rows or analysis:
            response_text, token_usage = ai_provider.answer(
                question, rows, analysis=analysis, history=_history(payload),
            )
        else:
            response_text = "当前授权数据中没有可用于回答的依据。"
    except ai_provider.AiProviderError:
        response_text = "AI 服务暂时不可用。已保留当前权限范围内的检索或统计结果，请从引用记录进入业务页面核对。"
    # The provider call may take seconds. Reload every formal record and
    # permission relationship now so a revoked permission cannot survive in
    # an old answer or citation. Removed rows keep their original citation
    # number unavailable instead of shifting another record into its place.
    rows = reauthorize_results(g.current_user, rows, read_only=True)
    response_text, citations = _validated_citations(response_text, rows)
    _audit(
        "ai.chat", result_ids=[row["id"] for row in rows],
        elapsed_ms=(time.monotonic() - started) * 1000, token_usage=token_usage,
    )
    db.session.commit()

    @stream_with_context
    def events():
        yield f"data: {json.dumps({'type': 'status', 'stage': 'authorized', 'text': '已完成权限范围校验'}, ensure_ascii=False)}\n\n"
        if analysis:
            yield f"data: {json.dumps({'type': 'tool', 'name': template_id, 'data': analysis}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'sources', 'items': rows}, ensure_ascii=False)}\n\n"
        for citation in citations:
            yield f"data: {json.dumps({'type': 'citation', **citation}, ensure_ascii=False)}\n\n"
        for offset in range(0, len(response_text), 80):
            yield f"data: {json.dumps({'type': 'delta', 'text': response_text[offset:offset + 80]}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'elapsedMs': int((time.monotonic() - started) * 1000)}, ensure_ascii=False)}\n\n"

    return Response(events(), mimetype="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@bp.get("/analysis/templates")
@require_auth
def analysis_templates():
    denied = _require_permission() or _require_enabled(provider=False)
    if denied:
        return denied
    return jsonify({"code": 0, "message": "ok", "data": {
        "enabled": bool(current_app.config.get("AI_ANALYSIS_ENABLED")),
        "items": available_templates(g.current_user),
    }})


@bp.get("/suggestions")
@require_auth
def suggestions():
    denied = _require_permission() or _require_enabled(provider=False)
    if denied:
        return denied
    templates = available_templates(g.current_user)
    dictionary = AiSearchDictionary.query.filter(AiSearchDictionary.active.is_(True)).order_by(
        AiSearchDictionary.weight.desc(), AiSearchDictionary.code,
    ).all()
    return jsonify({"code": 0, "message": "ok", "data": {
        "quickQuestions": [row["prompt"] for row in templates[:7]],
        "dictionary": [{
            "canonical": row.canonical,
            "aliases": list(row.aliases or [])[:10],
            "entityTypes": list(row.entity_types or []),
        } for row in dictionary[:30]],
        "features": {
            "searchV2": bool(current_app.config.get("AI_SEARCH_V2_ENABLED")),
            "analysis": bool(current_app.config.get("AI_ANALYSIS_ENABLED")),
            "rerank": bool(current_app.config.get("AI_RERANK_ENABLED")),
        },
    }})


@bp.post("/feedback")
@require_auth
def feedback():
    denied = _require_permission() or _require_enabled(provider=False)
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    rating = str(payload.get("rating") or "")
    if rating not in {"helpful", "unhelpful"}:
        return _error("反馈类型无效")
    result_ids = [str(value)[:140] for value in (payload.get("resultIds") or [])[:20]]
    tags = [str(value)[:40] for value in (payload.get("tags") or [])[:10]]
    _audit("ai.feedback", result_ids=result_ids, fields=[rating, *tags])
    db.session.commit()
    return jsonify({"code": 0, "message": "ok", "data": {"accepted": True}})


@bp.post("/transcriptions")
@require_auth
def transcriptions():
    denied = _require_permission("ai.voice.use") or _require_enabled(voice=True)
    if denied:
        return denied
    if _rate_limited("ai.transcribe", 10):
        return _error("语音请求过于频繁，请稍后再试", 429)
    upload = request.files.get("audio")
    if not upload:
        return _error("缺少音频")
    media_type = (upload.mimetype or "").lower().partition(";")[0].strip()
    if media_type not in ALLOWED_AUDIO_TYPES:
        return _error("不支持的音频格式")
    try:
        duration = float(request.form.get("durationSeconds") or 0)
    except ValueError:
        return _error("音频时长无效")
    if duration <= 0 or duration > current_app.config["AI_AUDIO_MAX_SECONDS"]:
        return _error("单次录音必须在 90 秒以内")
    audio = upload.read(current_app.config["AI_AUDIO_MAX_BYTES"] + 1)
    if len(audio) > current_app.config["AI_AUDIO_MAX_BYTES"]:
        return _error("单次录音不能超过 8MB", 413)
    started = time.monotonic()
    data_uri = f"data:{media_type};base64,{base64.b64encode(audio).decode('ascii')}"
    try:
        transcript = ai_provider.transcribe(data_uri)
    except ai_provider.AiProviderError as exc:
        return _error(str(exc), 502)
    finally:
        audio = b""
        data_uri = ""
    _audit("ai.transcribe", elapsed_ms=(time.monotonic() - started) * 1000)
    db.session.commit()
    return jsonify({"code": 0, "message": "ok", "data": {"text": transcript}})


@bp.post("/form-drafts")
@require_auth
def form_drafts():
    denied = _require_permission("ai.voice.use") or _require_enabled(voice=True)
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    schema_id = str(payload.get("schemaId") or "")
    replacements = {}
    transcript = _redact_with_map(str(payload.get("transcript") or "").strip()[:6000], replacements)
    current_values = payload.get("currentValues") if isinstance(payload.get("currentValues"), dict) else {}
    try:
        fields = schema_fields(schema_id)
        safe_current = {key: _redact_with_map(value, replacements) for key, value in current_values.items() if key in fields and not isinstance(value, (dict, list))}
        raw = ai_provider.form_draft(schema_id, fields, transcript, safe_current)
        for item in raw:
            if isinstance(item, dict):
                item["value"] = _restore_placeholders(item.get("value"), replacements)
        patches = validate_form_draft(schema_id, raw)
    except FormDraftError as exc:
        return _error(str(exc))
    except ai_provider.AiProviderError as exc:
        return _error(str(exc), 502)
    _audit("ai.form_draft", fields=[item["path"] for item in patches])
    db.session.commit()
    return jsonify({"code": 0, "message": "ok", "data": {"schemaId": schema_id, "patches": patches}})


@bp.post("/form-drafts/apply-audit")
@require_auth
def form_draft_apply_audit():
    denied = _require_permission("ai.voice.use") or _require_enabled(voice=True)
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    try:
        patches = validate_form_draft(str(payload.get("schemaId") or ""), payload.get("patches") or [])
    except FormDraftError as exc:
        return _error(str(exc))
    _audit("ai.form_draft.apply", fields=[item["path"] for item in patches])
    db.session.commit()
    return jsonify({"code": 0, "message": "ok", "data": {"acceptedPaths": [item["path"] for item in patches]}})


@bp.get("/dictionary")
@require_auth
def dictionary_list():
    denied = _require_permission() or _require_enabled(provider=False)
    if denied:
        return denied
    if not _is_ai_admin():
        return _error("仅管理员或根机构可维护 AI 业务词典", 403)
    rows = AiSearchDictionary.query.order_by(AiSearchDictionary.weight.desc(), AiSearchDictionary.code).all()
    return jsonify({"code": 0, "message": "ok", "data": {"items": [row.to_row() for row in rows]}})


@bp.put("/dictionary")
@require_auth
def dictionary_save():
    denied = _require_permission() or _require_enabled(provider=False)
    if denied:
        return denied
    if not _is_ai_admin():
        return _error("仅管理员或根机构可维护 AI 业务词典", 403)
    payload = request.get_json(silent=True) or {}
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    if not items or len(items) > 100:
        return _error("业务词典必须包含 1 至 100 项")
    accepted = []
    allowed_types = {"entrust", "sample", "report", "standard", "capability", "equipment", "finance"}
    for item in items:
        if not isinstance(item, dict):
            return _error("业务词典项目格式无效")
        code = str(item.get("code") or "").strip().lower()[:80]
        canonical = str(item.get("canonical") or "").strip()[:160]
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{1,79}", code) or not canonical:
            return _error("业务词典代码或规范词无效")
        aliases = list(dict.fromkeys(
            str(value).strip()[:160] for value in (item.get("aliases") or [])[:30]
            if str(value).strip()
        ))
        entity_types = list(dict.fromkeys(
            str(value).strip().lower() for value in (item.get("entityTypes") or [])[:10]
            if str(value).strip().lower() in allowed_types
        ))
        try:
            weight = max(1, min(int(item.get("weight") or 4), 20))
        except (TypeError, ValueError):
            return _error("业务词典权重无效")
        row = AiSearchDictionary.query.filter_by(code=code).first() or AiSearchDictionary(code=code)
        row.canonical, row.aliases, row.entity_types = canonical, aliases, entity_types
        row.weight, row.active, row.updated_at = weight, bool(item.get("active", True)), datetime.utcnow()
        db.session.add(row)
        accepted.append(code)
    _audit("ai.dictionary.update", fields=accepted)
    db.session.commit()
    return jsonify({"code": 0, "message": "ok", "data": {"acceptedCodes": accepted}})


@bp.get("/index/status")
@require_auth
def index_status():
    denied = _require_permission()
    if denied:
        return denied
    if not _is_ai_admin():
        return _error("仅管理员或根机构可查看 AI 运行诊断", 403)
    dialect = db.engine.dialect.name
    try:
        migration = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar() or ""
        database_ok = True
    except Exception:
        db.session.rollback()
        migration, database_ok = "unknown", False
    return jsonify({"code": 0, "message": "ok", "data": {
        **status(), "enabled": bool(current_app.config.get("AI_ENABLED")),
        "voiceEnabled": bool(current_app.config.get("AI_VOICE_ENABLED")),
        "searchV2Enabled": bool(current_app.config.get("AI_SEARCH_V2_ENABLED")),
        "analysisEnabled": bool(current_app.config.get("AI_ANALYSIS_ENABLED")),
        "rerankEnabled": bool(current_app.config.get("AI_RERANK_ENABLED")),
        "database": {"connected": database_ok, "dialect": dialect, "migration": migration},
    }})
