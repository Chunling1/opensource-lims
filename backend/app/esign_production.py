"""Production-only eSign configuration. Never falls back to sandbox credentials."""
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path('/opt/lims-platform-20261005')
CONFIG = ROOT / 'esign-production.private.json'
STATE = ROOT / 'esign-production-state.json'
ORIGIN = 'https://openapi.esign.cn'
SEAL = os.environ.get('ESIGN_SEAL_ID', '00000000-0000-0000-0000-000000000000')


def validate(data):
    if data.get('schema') != 1 or data.get('baseUrl') != ORIGIN:
        raise ValueError('PRODUCTION_ORIGIN_REQUIRED')
    if not isinstance(data.get('appId'), str) or len(data['appId'].strip()) < 6 or not isinstance(data.get('appSecret'), str) or len(data['appSecret']) < 16:
        raise ValueError('PRODUCTION_CREDENTIALS_REQUIRED')
    if not isinstance(data.get('sealId'), str) or not data['sealId'].strip() or type(data.get('agreeSkipWillingness')) is not bool:
        raise ValueError('PRODUCTION_SEAL_OR_SIGN_CONFIG_CHANGED')
    if data.get('organizationName') != '示例检测机构':
        raise ValueError('ORGANIZATION_MISMATCH')
    return data


def fingerprint(data):
    keys = ('baseUrl', 'appId', 'appSecret', 'orgId', 'organizationName', 'sealId', 'sealName', 'agreeSkipWillingness', 'callbackUrl')
    return hashlib.sha256(json.dumps({k:data.get(k) for k in keys}, sort_keys=True).encode()).hexdigest()


def secure_read(path):
    stat = path.stat()
    if path.is_symlink() or (os.name != 'nt' and stat.st_mode & 0o077):
        raise ValueError('PRIVATE_FILE_PERMISSIONS_REQUIRED')
    return json.loads(path.read_text('utf8'))


def configure(app):
    # Missing/invalid activation stops eSign, while the rest of the app stays available.
    app.config.update(ESIGN_ENABLED=False, ESIGN_EXTERNAL_SIDE_EFFECTS_ENABLED=False,
        ESIGN_ENVIRONMENT='production', ESIGN_BASE_URL=ORIGIN, ESIGN_APP_ID='',
        ESIGN_APP_SECRET='', ESIGN_PRODUCTION_READY=False, ESIGN_REQUIRED_FOR_ISSUANCE=True)
    try:
        data = validate(secure_read(CONFIG))
        state = secure_read(STATE)
        if state.get('status') != 'active' or state.get('fingerprint') != fingerprint(data):
            raise ValueError('PRODUCTION_NOT_ACTIVATED')
        cutoff = state.get('minFlowId')
        if not isinstance(cutoff, int) or cutoff < 1 or not data.get('orgId'):
            raise ValueError('PRODUCTION_IDENTITY_REQUIRED')
        url = urlsplit(data.get('callbackUrl', ''))
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            raise ValueError('HTTPS_CALLBACK_REQUIRED')
    except (OSError, ValueError, TypeError):
        app.config['ESIGN_PRODUCTION_STATUS'] = 'configuration_required'
        return
    app.config.update(ESIGN_ENABLED=True, ESIGN_WORKFLOW_ENABLED=True,
        ESIGN_EXTERNAL_SIDE_EFFECTS_ENABLED=True, ESIGN_PRODUCTION_READY=True,
        ESIGN_PRODUCTION_STATUS='configured_not_live_signing_verified',
        ESIGN_APP_ID=data['appId'], ESIGN_APP_SECRET=data['appSecret'],
        ESIGN_ORG_ID=data['orgId'], ESIGN_ORG_NAME=data['organizationName'],
        ESIGN_ORG_SEAL_ID=data['sealId'], ESIGN_ORG_AUTOSIGN_ENABLED=True,
        ESIGN_CALLBACK_PUBLIC_URL=data['callbackUrl'], ESIGN_PROVIDER_FLOW_MIN_ID=cutoff,
        ESIGN_AGREE_SKIP_WILLINGNESS=data['agreeSkipWillingness'])


def require_ready():
    from flask import current_app
    from .functions.esign_service import EsignServiceError
    if not current_app.config.get('ESIGN_PRODUCTION_READY'):
        raise EsignServiceError('production_not_configured', 'e签宝正式环境尚未完成配置')


def require_flow(flow_id):
    from flask import current_app
    from .functions.esign_service import EsignServiceError
    require_ready()
    if int(flow_id or 0) < int(current_app.config['ESIGN_PROVIDER_FLOW_MIN_ID']):
        raise EsignServiceError('sandbox_flow_read_only', '此为历史沙箱流程，请重新准备正式签署任务')


def request_payload(method, path, payload):
    """No request is made here. Add willingness config only to personal signers."""
    from copy import deepcopy
    require_ready()
    if method.upper() == 'POST' and path == '/v3/sign-flow/create-by-file':
        payload = deepcopy(payload)
        for signer in payload.get('signers', []):
            if signer.get('signerType') == 0:
                from flask import current_app
                signer.setdefault('signConfig', {})['agreeSkipWillingness'] = current_app.config.get('ESIGN_AGREE_SKIP_WILLINGNESS', False)
    return payload
