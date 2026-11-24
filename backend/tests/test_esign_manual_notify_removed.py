"""Batch-3 Q8 (P123, 2026-11-07): the manual "通知/重发当前签署人" entry is retired.

Automatic provider SMS and scheduled reminders stay; only the manual endpoint is gone.
"""
from app.external_side_effects import request_has_external_side_effect


def test_manual_notify_signers_route_is_removed(isolated_app):
    rules = [rule.rule for rule in isolated_app.url_map.iter_rules()]
    assert not any(rule.endswith('/notify-signers') for rule in rules)
    # Remaining esign side-effect routes are still registered and still guarded.
    assert any(rule.endswith('/flows/<int:flow_id>/cancel') for rule in rules)
    assert request_has_external_side_effect('POST', '/api/esign/flows/1/cancel')
    assert not request_has_external_side_effect('POST', '/api/esign/flows/1/notify-signers')


def test_automatic_sms_entry_point_is_kept():
    from app.functions.esign_service import send_initial_sms_notifications
    assert callable(send_initial_sms_notifications)
