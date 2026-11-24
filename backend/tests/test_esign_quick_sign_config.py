"""Verify private activation and the actual serialized request; no provider calls."""
import copy
import json

import pytest
from flask import Flask
from app import esign_production as production
from app.functions.esign_service import EsignV3Client


def configured_app(tmp_path, monkeypatch, enabled):
    data = dict(schema=1, baseUrl=production.ORIGIN, appId='demo-esign-app-id',
        appSecret='isolated-test-secret-not-real', sealId=production.SEAL,
        organizationName='示例检测机构', orgId='test-org',
        callbackUrl='https://example.invalid/callback', agreeSkipWillingness=enabled)
    state = dict(status='active', fingerprint=production.fingerprint(data), minFlowId=1)
    for name, value in [('CONFIG',data),('STATE',state)]:
        path=tmp_path / (name+'.json')
        path.write_text(json.dumps(value),encoding='utf8')
        path.chmod(0o600)
        monkeypatch.setattr(production,name,path)
    app=Flask(__name__)
    production.configure(app)
    return app, data


@pytest.mark.parametrize('enabled',[True,False])
def test_active_private_config_reaches_serialized_personal_signers_only(tmp_path,monkeypatch,enabled):
    app,_=configured_app(tmp_path,monkeypatch,enabled)
    assert app.config['ESIGN_PRODUCTION_READY'] is True
    captured=[]
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self): return b'{"code":0,"data":{"signFlowId":"test-flow"}}'
    def urlopen(req,**kwargs):
        captured.append(req)
        return Response()
    monkeypatch.setattr('urllib.request.urlopen',urlopen)
    payload={'signers':[
        {'signerType':0,'signConfig':{'signOrder':1}},
        {'signerType':0,'signConfig':{'signOrder':2}},
        {'signerType':1,'signConfig':{'signOrder':3}}]}
    original=copy.deepcopy(payload)
    with app.app_context():
        result=EsignV3Client().request('POST','/v3/sign-flow/create-by-file',payload)
    assert result['signFlowId']=='test-flow' and len(captured)==1
    sent=json.loads(captured[0].data)
    assert [s['signConfig']['agreeSkipWillingness'] for s in sent['signers'][:2]]==[enabled,enabled]
    assert sent['signers'][2]==original['signers'][2]
    assert payload==original


def test_editing_config_without_reactivating_fingerprint_disables_provider(tmp_path,monkeypatch):
    app,data=configured_app(tmp_path,monkeypatch,False)
    data['agreeSkipWillingness']=True
    production.CONFIG.write_text(json.dumps(data),encoding='utf8')
    production.configure(app)
    assert app.config['ESIGN_PRODUCTION_READY'] is False
    assert app.config['ESIGN_EXTERNAL_SIDE_EFFECTS_ENABLED'] is False


def test_read_and_existing_flow_requests_are_not_rewritten(tmp_path,monkeypatch):
    app,_=configured_app(tmp_path,monkeypatch,True)
    payload={'signers':[{'signerType':0}]}
    with app.app_context():
        assert production.request_payload('GET','/v3/sign-flow/existing',None) is None
        assert production.request_payload('POST','/v3/sign-flow/existing/sign-url',payload) is payload
    assert payload=={'signers':[{'signerType':0}]}
