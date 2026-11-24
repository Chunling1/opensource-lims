"""JSON object/string/page checks applied only to declared input contracts."""
import re
from functools import wraps
from flask import jsonify, request

def json_fields(*strings, pagination=False):
    def decorate(view):
        @wraps(view)
        def checked(*args, **kwargs):
            body = request.get_json(silent=True)
            invalid = body is not None and not isinstance(body, dict)
            if body is None:
                body = {}
            if not invalid:
                invalid = any(body.get(key) is not None and not isinstance(body[key], str) for key in strings)
            if not invalid and pagination:
                for key in ('page', 'pageSize'):
                    value = body.get(key)
                    if value is None or value == '':
                        continue
                    if type(value) is int:
                        valid = value >= 0
                    else:
                        valid = isinstance(value, str) and bool(re.fullmatch(r'[0-9]{1,10}', value.strip()))
                    if not valid:
                        invalid = True
                        break
            if invalid:
                return jsonify({'code': 1, 'message': '请求参数格式无效', 'data': None}), 200
            return view(*args, **kwargs)
        return checked
    return decorate
