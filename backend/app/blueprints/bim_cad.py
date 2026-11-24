from __future__ import annotations

import logging
import threading
import time
from typing import Any

from flask import Blueprint, current_app, g, jsonify, request

from ..adapters.experiments import (
    BimCadExperimentError,
    experiment_status,
    recognize_document,
    run_experiment,
)
from ..extensions import db
from ..platform.audit import add_operation_audit
from ..security import require_auth

bp = Blueprint("bim_cad_experiment", __name__, url_prefix="/api/experiments/bim-cad")
logger = logging.getLogger(__name__)
VIEW_PERMISSION = "bim_lab.workbench.view"
_inference_gate = threading.BoundedSemaphore(value=1)


@bp.after_request
def _prevent_experiment_response_caching(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


def _has_permission() -> bool:
    user = getattr(g, "current_user", None)
    return bool(user and (user.role_key == "admin" or VIEW_PERMISSION in user.permission_codes()))


def _success(data: Any):
    return jsonify({"code": 0, "message": "ok", "data": data})


def _error(message: str, *, code: str, http_status: int):
    return jsonify({"code": code, "message": message, "data": None}), http_status


def _permission_error():
    return _error("当前账号未开通 BIM/CAD 实验权限", code="forbidden", http_status=403)


def _feature_enabled() -> bool:
    return bool(current_app.config.get("BIM_CAD_EXPERIMENT_ENABLED", False))


def _audit(action: str, detail: dict[str, Any], *, success_value: bool = True) -> None:
    try:
        add_operation_audit(
            action=action,
            object_type="bim_cad_experiment",
            object_id=str(detail.get("recognitionId") or detail.get("simulationId") or "attempt"),
            after=detail,
            success=success_value,
            category="experiment",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.warning("BIM/CAD experiment audit failed", exc_info=True)


@bp.get("/status")
@require_auth
def status():
    if not _has_permission():
        return _permission_error()
    return _success(experiment_status(current_app.config))


@bp.post("/recognize")
@require_auth
def recognize():
    if not _has_permission():
        return _permission_error()
    if not _feature_enabled():
        return _error("BIM/CAD 实验功能尚未启用", code="bim_cad_experiment_disabled", http_status=503)
    upload = request.files.get("file")
    if upload is None:
        return _error("请选择图纸文件", code="drawing_required", http_status=400)
    max_bytes = int(current_app.config.get("BIM_CAD_MAX_BYTES", 20 * 1024 * 1024))
    payload = upload.stream.read(max_bytes + 1)
    if len(payload) > max_bytes:
        return _error(
            f"图纸文件不能超过 {max_bytes // (1024 * 1024)}MB",
            code="drawing_too_large",
            http_status=413,
        )
    if not _inference_gate.acquire(blocking=False):
        return _error("识别引擎正在处理其他任务，请稍后重试", code="bim_cad_engine_busy", http_status=429)
    started = time.perf_counter()
    try:
        result = recognize_document(
            payload,
            upload.filename or "drawing",
            str(request.form.get("preprocessing") or "auto"),
            current_app.config,
        )
    except BimCadExperimentError as exc:
        _audit(
            "识别失败",
            {"code": exc.code, "fileBytes": len(payload), "elapsedMs": round((time.perf_counter() - started) * 1000)},
            success_value=False,
        )
        return _error(str(exc), code=exc.code, http_status=exc.status_code)
    except Exception:
        logger.exception("BIM/CAD recognition failed")
        _audit("识别失败", {"code": "internal_error", "fileBytes": len(payload)}, success_value=False)
        return _error("图纸识别失败，请稍后重试", code="bim_cad_recognition_failed", http_status=500)
    finally:
        _inference_gate.release()
    _audit(
        "图纸识别",
        {
            "recognitionId": result.get("recognitionId"),
            "sourceHashPrefix": str(result.get("sourceHash") or "")[:16],
            "fileBytes": len(payload),
            "model": result.get("model"),
            "elapsedMs": round((time.perf_counter() - started) * 1000),
        },
    )
    return _success(result)


@bp.post("/simulate")
@require_auth
def simulate():
    if not _has_permission():
        return _permission_error()
    if not _feature_enabled():
        return _error("BIM/CAD 实验功能尚未启用", code="bim_cad_experiment_disabled", http_status=503)
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _error("请提交有效的模拟参数", code="invalid_simulation_payload", http_status=400)
    started = time.perf_counter()
    try:
        result = run_experiment("energy-simulation", body)
    except BimCadExperimentError as exc:
        return _error(str(exc), code=exc.code, http_status=exc.status_code)
    except Exception:
        logger.exception("BIM/CAD simulation failed")
        return _error("计算模拟失败，请核对参数后重试", code="bim_cad_simulation_failed", http_status=500)
    _audit(
        "计算模拟",
        {
            "simulationId": result.get("simulationId"),
            "recognitionId": str(body.get("recognitionId") or "")[:64],
            "elapsedMs": round((time.perf_counter() - started) * 1000),
        },
    )
    return _success(result)
