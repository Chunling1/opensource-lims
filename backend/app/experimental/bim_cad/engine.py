from __future__ import annotations

import base64
import hashlib
import importlib.util
import math
import threading
import time
import uuid
from pathlib import Path
from typing import Any

MODEL_NAME = "M2_UNet_ResNet34_DA"
MODEL_SHA256 = "d54e1ed1644bf795ba3dbdbfef5355b55e9f0110002f79de1bf2c6c2abdf6077"
MODEL_BENCHMARK_MIOU = 0.787


class BimCadExperimentError(RuntimeError):
    def __init__(self, message: str, *, code: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


_hash_lock = threading.Lock()
_hash_cache: dict[str, tuple[int, int, str]] = {}
_model_lock = threading.Lock()
_model_instance: Any | None = None
_model_instance_path: str | None = None


def _sha256_file(path: Path) -> str:
    stat = path.stat()
    key = str(path.resolve())
    cached = _hash_cache.get(key)
    signature = (stat.st_size, stat.st_mtime_ns)
    if cached and cached[:2] == signature:
        return cached[2]
    with _hash_lock:
        cached = _hash_cache.get(key)
        if cached and cached[:2] == signature:
            return cached[2]
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        value = digest.hexdigest()
        _hash_cache[key] = (signature[0], signature[1], value)
        return value


def _dependency_state() -> dict[str, bool]:
    return {
        "numpy": importlib.util.find_spec("numpy") is not None,
        "opencv": importlib.util.find_spec("cv2") is not None,
        "onnxruntime": importlib.util.find_spec("onnxruntime") is not None,
        "pymupdf": importlib.util.find_spec("fitz") is not None,
    }


def _model_path(config: Any) -> Path | None:
    raw = str(config.get("BIM_CAD_MODEL_PATH") or "").strip()
    return Path(raw).expanduser() if raw else None


def experiment_status(config: Any) -> dict[str, Any]:
    enabled = bool(config.get("BIM_CAD_EXPERIMENT_ENABLED", False))
    dependencies = _dependency_state()
    path = _model_path(config)
    model_exists = bool(path and path.is_file())
    model_verified = False
    model_error = ""
    if model_exists and path:
        try:
            model_verified = _sha256_file(path).lower() == MODEL_SHA256
            if not model_verified:
                model_error = "模型文件校验不通过"
        except OSError:
            model_error = "模型文件不可读取"
    elif enabled:
        model_error = "尚未配置实验模型"
    ready = enabled and model_exists and model_verified and all(dependencies.values())
    return {
        "enabled": enabled,
        "ready": ready,
        "model": MODEL_NAME,
        "modelBenchmark": {
            "name": "研究样本 mIoU",
            "value": MODEL_BENCHMARK_MIOU,
            "notice": "该数值为研究样本指标，不代表本次上传图纸的识别准确率。",
        },
        "modelExists": model_exists,
        "modelVerified": model_verified,
        "modelError": model_error,
        "dependencies": dependencies,
        "supportedFiles": ["PNG", "JPG", "JPEG", "WEBP", "PDF"],
        "nativeCadNotice": "DWG/DXF 请先导出为图片或 PDF；当前实验不直接解析原生 CAD 文件。",
        "privacyNotice": "上传内容仅在本次请求中临时处理，请求结束即释放；不写入正式业务库、报告、附件或流程。",
    }


def _load_segmenter(config: Any) -> Any:
    global _model_instance, _model_instance_path
    status = experiment_status(config)
    if not status["ready"]:
        message = status["modelError"] or "实验识别引擎尚未就绪"
        raise BimCadExperimentError(message, code="bim_cad_engine_unavailable", status_code=503)
    path = _model_path(config)
    if path is None:
        raise BimCadExperimentError("模型文件尚未配置", status_code=503, code="model_unavailable")
    resolved = str(path.resolve())
    if _model_instance is not None and _model_instance_path == resolved:
        return _model_instance
    with _model_lock:
        if _model_instance is not None and _model_instance_path == resolved:
            return _model_instance
        from .floorplan_onnx import FloorplanSegmenterONNX

        _model_instance = FloorplanSegmenterONNX(resolved)
        _model_instance_path = resolved
        return _model_instance


def _sniff_file(data: bytes, filename: str) -> str:
    extension = Path(filename or "").suffix.lower()
    if data.startswith(b"%PDF-"):
        detected = "pdf"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        detected = "png"
    elif data.startswith(b"\xff\xd8\xff"):
        detected = "jpeg"
    elif len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        detected = "webp"
    else:
        raise BimCadExperimentError(
            "无法识别文件格式，请上传 PNG、JPG、WEBP 或 PDF。",
            code="unsupported_drawing_format",
        )
    allowed_extensions = {
        "pdf": {".pdf"},
        "png": {".png"},
        "jpeg": {".jpg", ".jpeg"},
        "webp": {".webp"},
    }
    if extension and extension not in allowed_extensions[detected]:
        raise BimCadExperimentError("文件扩展名与实际内容不一致。", code="drawing_type_mismatch")
    return detected


def _decode_document(data: bytes, kind: str, *, max_side: int, max_pixels: int) -> tuple[Any, dict[str, Any]]:
    import cv2
    import numpy as np

    meta: dict[str, Any] = {"sourceType": kind, "page": 1}
    if kind == "pdf":
        try:
            import fitz

            document = fitz.open(stream=data, filetype="pdf")
            if document.needs_pass:
                raise BimCadExperimentError("暂不支持加密 PDF。", code="encrypted_pdf")
            if document.page_count < 1:
                raise BimCadExperimentError("PDF 中没有可识别页面。", code="empty_pdf")
            page = document.load_page(0)
            rect = page.rect
            longest = max(float(rect.width), float(rect.height), 1.0)
            zoom = min(3.0, max_side / longest)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            buffer = np.frombuffer(pixmap.tobytes("png"), dtype=np.uint8)
            image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
            meta["pdfPageCount"] = document.page_count
            document.close()
        except BimCadExperimentError:
            raise
        except Exception as exc:
            raise BimCadExperimentError("PDF 解析失败，请导出为图片后重试。", code="pdf_decode_failed") from exc
    else:
        buffer = np.frombuffer(data, dtype=np.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None or not getattr(image, "size", 0):
        raise BimCadExperimentError("图纸图像无法读取。", code="drawing_decode_failed")

    original_height, original_width = image.shape[:2]
    if original_height * original_width > max_pixels * 16:
        raise BimCadExperimentError("图纸像素尺寸过大，请压缩后重试。", code="drawing_dimensions_exceeded")
    scale = min(1.0, max_side / max(original_width, original_height))
    if original_height * original_width * scale * scale > max_pixels:
        scale = math.sqrt(max_pixels / float(original_height * original_width))
    if scale < 1.0:
        image = cv2.resize(
            image,
            (max(1, round(original_width * scale)), max(1, round(original_height * scale))),
            interpolation=cv2.INTER_AREA,
        )
    meta.update(
        {
            "originalWidth": original_width,
            "originalHeight": original_height,
            "processedWidth": int(image.shape[1]),
            "processedHeight": int(image.shape[0]),
            "resized": scale < 1.0,
        }
    )
    return image, meta


def _preview_data_url(image: Any, *, quality: int = 84) -> str:
    import cv2

    ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise BimCadExperimentError("识别预览生成失败。", code="preview_encode_failed", status_code=500)
    return "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode("ascii")


def recognize_document(
    data: bytes,
    filename: str,
    preprocessing: str,
    config: Any,
) -> dict[str, Any]:
    if not data:
        raise BimCadExperimentError("请选择图纸文件。", code="drawing_required")
    max_bytes = int(config.get("BIM_CAD_MAX_BYTES", 20 * 1024 * 1024))
    if len(data) > max_bytes:
        raise BimCadExperimentError(
            f"图纸文件不能超过 {max_bytes // (1024 * 1024)}MB。",
            code="drawing_too_large",
            status_code=413,
        )
    kind = _sniff_file(data, filename)
    image, source_meta = _decode_document(
        data,
        kind,
        max_side=int(config.get("BIM_CAD_MAX_SIDE", 2048)),
        max_pixels=int(config.get("BIM_CAD_MAX_PIXELS", 6_000_000)),
    )
    segmenter = _load_segmenter(config)
    mode = preprocessing if preprocessing in {"auto", "none"} else "auto"
    started = time.perf_counter()
    result = segmenter.predict(image, use_preprocessing=mode != "none")
    elapsed = time.perf_counter() - started

    stats = result.get("stats") or {}
    geometry = result.get("geometry") or {}

    def contour_length(items: list[dict[str, Any]]) -> float:
        total = 0.0
        for item in items:
            points = item.get("pts") if isinstance(item, dict) else None
            if not isinstance(points, list) or len(points) < 2:
                continue
            for index, point in enumerate(points):
                nxt = points[(index + 1) % len(points)]
                if isinstance(point, list) and isinstance(nxt, list) and len(point) >= 2 and len(nxt) >= 2:
                    total += math.hypot(float(nxt[0]) - float(point[0]), float(nxt[1]) - float(point[1]))
        return total

    def component_area(name: str) -> float:
        values = geometry.get(name) or []
        return float(sum(max(0.0, float(item.get("area", 0.0))) for item in values if isinstance(item, dict)))

    metrics = {
        "wallLengthPx": contour_length(geometry.get("walls") or []),
        "windowLengthPx": contour_length(geometry.get("windows") or []),
        "doorLengthPx": contour_length(geometry.get("doors") or []),
        "wallAreaPx": component_area("walls"),
        "windowAreaPx": component_area("windows"),
        "doorAreaPx": component_area("doors"),
        "wallComponents": len(geometry.get("walls") or []),
        "windowComponents": len(geometry.get("windows") or []),
        "doorComponents": len(geometry.get("doors") or []),
    }
    source_hash = hashlib.sha256(data).hexdigest()
    return {
        "recognitionId": uuid.uuid4().hex,
        "sourceHash": source_hash,
        "source": source_meta,
        "model": MODEL_NAME,
        "modelBenchmark": {
            "name": "研究样本 mIoU",
            "value": MODEL_BENCHMARK_MIOU,
            "notice": "仅为既有研究样本结果，本次图纸须人工复核。",
        },
        "elapsedSeconds": round(elapsed, 3),
        "preprocessing": mode,
        "stats": stats,
        "metrics": metrics,
        "preview": {
            "original": _preview_data_url(image),
            "overlay": _preview_data_url(result["overlay"]),
        },
        "warnings": [
            "识别覆盖图和构件数量必须人工复核。",
            "本次结果仅用于科研与方案估算，不形成检测结论。",
            "上传内容未写入正式业务库、报告、附件或流程。",
        ],
    }


def _bounded_number(value: Any, name: str, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise BimCadExperimentError(f"{name}格式不正确。", code="invalid_simulation_parameter") from exc
    if not math.isfinite(number) or number < low or number > high:
        raise BimCadExperimentError(
            f"{name}应在 {low:g}～{high:g} 之间。",
            code="simulation_parameter_out_of_range",
        )
    return number


def simulate_energy(payload: dict[str, Any]) -> dict[str, Any]:
    from .energy_calc import (
        BUILDING_DEFAULTS,
        CLIMATE_DB,
        COOLING_SYSTEMS,
        HEATING_SYSTEMS,
        calculate_energy,
    )

    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    image = payload.get("imageSize") if isinstance(payload.get("imageSize"), dict) else {}
    params = payload.get("parameters") if isinstance(payload.get("parameters"), dict) else {}
    width = _bounded_number(image.get("width"), "处理图宽度", 32, 10000)
    height_px = _bounded_number(image.get("height"), "处理图高度", 32, 10000)
    scale_mm = _bounded_number(params.get("scaleMmPerPixel"), "图纸比例", 0.1, 2000)
    scale_m = scale_mm / 1000.0
    floors = int(_bounded_number(params.get("floors"), "地上层数", 1, 200))
    floor_height = _bounded_number(params.get("floorHeight"), "层高", 2.0, 20.0)

    override = params.get("floorAreaM2")
    floor_area = (
        _bounded_number(override, "单层面积", 1.0, 1_000_000.0)
        if override not in {None, ""}
        else width * height_px * scale_m * scale_m
    )
    wall_length = _bounded_number(metrics.get("wallLengthPx", 0), "墙体像素长度", 0, 100_000_000) * scale_m
    window_length = _bounded_number(metrics.get("windowLengthPx", 0), "窗体像素长度", 0, 100_000_000) * scale_m
    wall_area = wall_length * floor_height * floors
    window_area = window_length * floor_height * floors
    door_area = _bounded_number(metrics.get("doorAreaPx", 0), "门体像素面积", 0, 100_000_000) * scale_m * scale_m * floors

    city = str(params.get("city") or "beijing")
    building_type = str(params.get("buildingType") or "office")
    heating_system = str(params.get("heatingSystem") or "gas_boiler")
    cooling_system = str(params.get("coolingSystem") or "split_ac")
    if city not in CLIMATE_DB:
        raise BimCadExperimentError("请选择有效城市。", code="invalid_city")
    if building_type not in BUILDING_DEFAULTS:
        raise BimCadExperimentError("请选择有效建筑类型。", code="invalid_building_type")
    if heating_system not in HEATING_SYSTEMS or cooling_system not in COOLING_SYSTEMS:
        raise BimCadExperimentError("请选择有效系统类型。", code="invalid_system_type")

    calculation_input = {
        "geometry": {
            "floor_area_m2": floor_area,
            "wall_area_m2": max(wall_area - window_area - door_area, 0.0),
            "window_area_m2": window_area,
            "door_area_m2": door_area,
            "roof_area_m2": floor_area,
        },
        "building": {
            "floors": floors,
            "height": floor_height,
            "building_type": building_type,
            "orientation": str(params.get("orientation") or "south"),
        },
        "envelope": {
            "u_wall": _bounded_number(params.get("wallU", 0.5), "外墙传热系数", 0.05, 10),
            "u_window": _bounded_number(params.get("windowU", 2.4), "外窗传热系数", 0.1, 15),
            "u_roof": _bounded_number(params.get("roofU", 0.4), "屋面传热系数", 0.05, 10),
            "u_floor": _bounded_number(params.get("floorU", 0.5), "地面传热系数", 0.05, 10),
            "shgc": _bounded_number(params.get("windowShgc", 0.5), "外窗太阳得热系数", 0.05, 1),
        },
        "climate": {"city_id": city},
        "heating": {"system_type": heating_system},
        "cooling": {"system_type": cooling_system},
        "lighting": {"lpd": _bounded_number(params.get("lightingPowerDensity", 8), "照明功率密度", 0, 80)},
        "equipment": {"epd": _bounded_number(params.get("equipmentPowerDensity", 12), "设备功率密度", 0, 150)},
        "ventilation": {"ach": _bounded_number(params.get("ventilationRate", 0.5), "换气次数", 0, 20)},
        "schedule": {"op_hours": _bounded_number(params.get("operatingHours", 2500), "年运行小时数", 1, 8760)},
    }
    result = calculate_energy(calculation_input)
    return {
        "simulationId": uuid.uuid4().hex,
        "method": "识别像素量＋人工比例校核＋简化建筑能耗估算",
        "inputs": calculation_input,
        "result": result,
        "warnings": [
            "图纸比例、单层面积和构件识别结果须由专业人员校核。",
            "本结果为实验估算，不替代法定检测、审图、能耗模拟或工程设计结论。",
            "如需正式模拟，应复核围护结构参数、气象文件、人员设备时刻表和系统效率。",
        ],
    }
