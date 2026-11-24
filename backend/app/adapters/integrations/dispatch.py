"""Fail-closed command dispatcher for external integration adapters.

The dispatcher is deliberately transport-agnostic.  A concrete Erp,
message, mail or WPS connector supplies ``transport`` while this boundary
enforces the rules shared by every connector:

* a versioned envelope and an explicit adapter scope;
* external side effects must be enabled by the deployment profile;
* one idempotency key may describe exactly one payload;
* timeouts and invalid responses are failures, never successful replays; and
* no core ORM model is imported or written here.

The in-memory ledger is suitable for one request worker and deterministic
tests.  Production connectors must inject a durable implementation before a
write-enabled external adapter is enabled.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from threading import RLock
from typing import Any, Protocol

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$")


class IntegrationDispatchError(RuntimeError):
    """Base error carrying a stable machine-readable code."""

    code = "integration_dispatch_failed"


class IntegrationDisabled(IntegrationDispatchError):
    code = "external_side_effects_disabled"


class IntegrationPermissionDenied(IntegrationDispatchError):
    code = "integration_scope_denied"


class IntegrationReplayConflict(IntegrationDispatchError):
    code = "integration_replay_conflict"


class IntegrationBusy(IntegrationDispatchError):
    code = "integration_request_in_progress"


class IntegrationTimeout(IntegrationDispatchError):
    code = "integration_timeout"


class IntegrationProtocolError(IntegrationDispatchError):
    code = "integration_protocol_error"


@dataclass(frozen=True)
class IntegrationEnvelope:
    """Versioned command accepted by the external anti-corruption layer."""

    version: str
    adapter: str
    action: str
    idempotency_key: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class IntegrationDispatchResult:
    """Successful transport result with replay evidence."""

    response: dict[str, Any]
    replayed: bool
    payload_sha256: str


class IntegrationTransport(Protocol):
    def __call__(
        self,
        action: str,
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class _CompletedReplay:
    payload_sha256: str
    response: dict[str, Any]


class InMemoryReplayLedger:
    """Atomic replay ledger used by controlled transports and tests."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._in_flight: dict[str, str] = {}
        self._completed: dict[str, _CompletedReplay] = {}

    def reserve(
        self,
        key: str,
        payload_sha256: str,
    ) -> IntegrationDispatchResult | None:
        with self._lock:
            completed = self._completed.get(key)
            if completed is not None:
                if completed.payload_sha256 != payload_sha256:
                    raise IntegrationReplayConflict(
                        "同一幂等键不能用于不同的外部命令载荷"
                    )
                return IntegrationDispatchResult(
                    response=dict(completed.response),
                    replayed=True,
                    payload_sha256=payload_sha256,
                )
            in_flight_hash = self._in_flight.get(key)
            if in_flight_hash is not None:
                if in_flight_hash != payload_sha256:
                    raise IntegrationReplayConflict(
                        "同一幂等键正在处理另一份外部命令载荷"
                    )
                raise IntegrationBusy("相同外部命令仍在处理中")
            self._in_flight[key] = payload_sha256
            return None

    def complete(
        self,
        key: str,
        payload_sha256: str,
        response: Mapping[str, Any],
    ) -> None:
        with self._lock:
            if self._in_flight.get(key) != payload_sha256:
                raise IntegrationReplayConflict("外部命令预留状态已变化")
            self._completed[key] = _CompletedReplay(
                payload_sha256=payload_sha256,
                response=dict(response),
            )
            self._in_flight.pop(key, None)

    def abort(self, key: str, payload_sha256: str) -> None:
        """Release only the matching failed reservation for a safe retry."""

        with self._lock:
            if self._in_flight.get(key) == payload_sha256:
                self._in_flight.pop(key, None)


def _validated_envelope(envelope: IntegrationEnvelope) -> IntegrationEnvelope:
    if envelope.version != "v1":
        raise IntegrationProtocolError("仅支持 integration command v1")
    for label, value in (
        ("adapter", envelope.adapter),
        ("action", envelope.action),
        ("idempotency_key", envelope.idempotency_key),
    ):
        if not _SAFE_ID.fullmatch(str(value or "")):
            raise IntegrationProtocolError(f"{label} 格式无效")
    if not isinstance(envelope.payload, Mapping):
        raise IntegrationProtocolError("payload 必须为对象")
    try:
        json.dumps(envelope.payload, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise IntegrationProtocolError("payload 必须可安全序列化") from exc
    return envelope


def _payload_hash(envelope: IntegrationEnvelope) -> str:
    canonical = json.dumps(
        {
            "version": envelope.version,
            "adapter": envelope.adapter,
            "action": envelope.action,
            "payload": envelope.payload,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def dispatch_integration_command(
    envelope: IntegrationEnvelope,
    *,
    authorized_scopes: set[str] | frozenset[str],
    external_side_effects_enabled: bool,
    transport: IntegrationTransport,
    replay_ledger: InMemoryReplayLedger,
    timeout_seconds: float = 5.0,
) -> IntegrationDispatchResult:
    """Dispatch one validated external command without touching core state."""

    envelope = _validated_envelope(envelope)
    if not external_side_effects_enabled:
        raise IntegrationDisabled("当前部署已关闭真实外部副作用")
    required_scope = f"integration:{envelope.adapter}:write"
    if required_scope not in authorized_scopes:
        raise IntegrationPermissionDenied("当前调用方无此外部适配器写入范围")
    if not 0 < float(timeout_seconds) <= 60:
        raise IntegrationProtocolError("timeout_seconds 必须在 0 到 60 秒之间")

    payload_sha256 = _payload_hash(envelope)
    replay = replay_ledger.reserve(envelope.idempotency_key, payload_sha256)
    if replay is not None:
        return replay
    try:
        response = transport(
            envelope.action,
            envelope.payload,
            float(timeout_seconds),
        )
        if not isinstance(response, Mapping):
            raise IntegrationProtocolError("外部适配器响应必须为对象")
        normalized = dict(response)
        replay_ledger.complete(
            envelope.idempotency_key,
            payload_sha256,
            normalized,
        )
        return IntegrationDispatchResult(
            response=normalized,
            replayed=False,
            payload_sha256=payload_sha256,
        )
    except TimeoutError as exc:
        replay_ledger.abort(envelope.idempotency_key, payload_sha256)
        raise IntegrationTimeout("外部适配器调用超时") from exc
    except Exception:
        replay_ledger.abort(envelope.idempotency_key, payload_sha256)
        raise


def integration_status(
    *,
    external_side_effects_enabled: bool,
    adapters: Mapping[str, bool],
) -> dict[str, Any]:
    """Return a non-secret status projection for operational diagnostics."""

    return {
        "protocol": "integration-command/v1",
        "externalSideEffectsEnabled": bool(external_side_effects_enabled),
        "adapters": {
            str(name): {"enabled": bool(enabled)}
            for name, enabled in sorted(adapters.items())
        },
    }


__all__ = [
    "InMemoryReplayLedger",
    "IntegrationBusy",
    "IntegrationDisabled",
    "IntegrationDispatchError",
    "IntegrationDispatchResult",
    "IntegrationEnvelope",
    "IntegrationPermissionDenied",
    "IntegrationProtocolError",
    "IntegrationReplayConflict",
    "IntegrationTimeout",
    "dispatch_integration_command",
    "integration_status",
]
