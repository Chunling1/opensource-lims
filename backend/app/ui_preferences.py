"""Account-owned table display preferences; no business data or permission changes."""
import re
from datetime import datetime
from flask import g, jsonify, request
from .extensions import db
from .models import User
from .security import require_auth
from .app_workspace import PersonalProfile


def ui_preferences(user):
    record = db.session.get(PersonalProfile, user.id)
    return (record.details or {}).get('uiPreferences', {}) if record else {}


def register_ui_preferences(bp):
    @bp.put('/ui-preferences')
    @require_auth
    def save_ui_preferences():
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or set(body) != {'key', 'settings'}:
            return jsonify(code=400, message='显示设置参数无效', data=None), 400
        key, settings = body['key'], body['settings']
        valid = isinstance(key, str) and re.fullmatch(r'[a-zA-Z0-9_.:-]{1,120}', key)
        valid = valid and isinstance(settings, dict) and bool(settings) and not (set(settings) - {'columns', 'pageSize', 'sort', 'direction', 'introducedColumns'})
        if valid:
            for field, value in settings.items():
                if field in {'columns', 'introducedColumns'}:
                    valid = isinstance(value, list) and len(value) <= 200 and all(isinstance(x, str) and re.fullmatch(r'[a-zA-Z0-9_.:-]{1,100}', x) for x in value) and len(set(value)) == len(value)
                elif field == 'pageSize':
                    valid = type(value) is int and 1 <= value <= 1000
                elif field == 'direction':
                    valid = value in ('asc', 'desc', '')
                else:
                    valid = isinstance(value, str) and len(value) <= 100
                if not valid:
                    break
        if not valid:
            return jsonify(code=400, message='显示设置参数无效', data=None), 400
        # Use the same lock as personal-profile updates so neither overwrites the other.
        db.session.query(User).filter_by(id=g.current_user.id).with_for_update().one()
        record = db.session.get(PersonalProfile, g.current_user.id)
        if record is None:
            record = PersonalProfile(user_id=g.current_user.id, details={})
            db.session.add(record)
        saved = dict((record.details or {}).get('uiPreferences', {}))
        if key not in saved and len(saved) >= 200:
            return jsonify(code=400, message='显示设置数量超过限制', data=None), 400
        saved[key] = settings
        record.details = {**(record.details or {}), 'uiPreferences': saved}
        record.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify(code=0, message='已保存显示设置', data=settings)
