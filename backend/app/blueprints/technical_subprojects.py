"""Versioned technical subprojects, distinct from settlement lines.

Parameters/methods/standards reference the existing capability ledger; no
guessed accreditation, synthetic choices or automatic permission assignment.
"""
from app.organization_privileges import has_full_platform_authority
import json
import re
from datetime import datetime
from flask import Blueprint, g, request
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..models import Project, CapabilityEntry, ReportTemplateProfile
from ..security import require_auth
from ..audit import add_operation_audit
from .report_assurance import ok, fail, writable

bp = Blueprint('technical_subprojects', __name__, url_prefix='/api/technical-subprojects')


class TechnicalSubproject(db.Model):
    __tablename__ = 'technical_subprojects'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)
    code = db.Column(db.String(60), unique=True, nullable=False)
    name = db.Column(db.String(240), nullable=False)
    department = db.Column(db.String(240), nullable=False)
    location = db.Column(db.String(240), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('report_template_profiles.id'), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    revision = db.Column(db.Integer, nullable=False, default=1)


class TechnicalSubprojectParameter(db.Model):
    __tablename__ = 'technical_subproject_parameters'
    subproject_id = db.Column(db.Integer, db.ForeignKey('technical_subprojects.id'), primary_key=True)
    capability_id = db.Column(db.Integer, db.ForeignKey('capability_entries.id'), primary_key=True)


class TechnicalSubprojectRevision(db.Model):
    __tablename__ = 'technical_subproject_revisions'
    subproject_id = db.Column(db.Integer, db.ForeignKey('technical_subprojects.id'), primary_key=True)
    revision = db.Column(db.Integer, primary_key=True)
    snapshot_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


def snapshot(row):
    revision = db.session.get(TechnicalSubprojectRevision, (row.id, row.revision))
    if not revision:
        raise ValueError('子项目缺少受控配置快照')
    return dict(json.loads(revision.snapshot_json), enabled=row.enabled)


@bp.get('')
@require_auth
def list_catalog():
    query = TechnicalSubproject.query
    if request.args.get('all') == '1':
        if not has_full_platform_authority(g.current_user):
            return fail('无配置维护权限', 403)
    else:
        query = query.filter_by(enabled=True)
    project_id = request.args.get('projectId')
    if project_id:
        if not project_id.isdigit():
            return fail('项目编号无效', 400)
        query = query.filter_by(project_id=int(project_id))
    return ok({'rows': [snapshot(row) for row in query.order_by(TechnicalSubproject.code).all()]})


@bp.get('/options')
@require_auth
def options():
    if not has_full_platform_authority(g.current_user):
        return fail('无配置维护权限', 403)
    keyword = str(request.args.get('keyword') or '').strip()[:80]
    capabilities = []
    if len(keyword) >= 2:
        capabilities = CapabilityEntry.query.filter(CapabilityEntry.active.is_(True), db.or_(
            CapabilityEntry.item_name.contains(keyword, autoescape=True), CapabilityEntry.standard_code.contains(keyword, autoescape=True))).order_by(CapabilityEntry.id).limit(100).all()
    return ok(dict(projects=[dict(id=p.id, code=p.code, name=p.name, department=p.department.name if p.department else p.source_department or '') for p in Project.query.filter_by(active=True).order_by(Project.code).all()],
        templates=[dict(id=t.id, code=t.code, name=t.name) for t in ReportTemplateProfile.query.filter_by(active=True).all()],
        parameters=[dict(id=c.id, name=c.item_name, method=c.method_clause or '', standard=c.standard_code, site=c.site, restriction=c.restriction or '') for c in capabilities]))


@bp.post('')
@bp.put('/<int:item_id>')
@require_auth
def save_catalog(item_id=None):
    if not has_full_platform_authority(g.current_user) or not writable():
        return fail('需要管理员权限且平台可写', 403)
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return fail('提交内容必须是对象', 400)
    for key, limit in (('code',60),('name',240),('department',240),('location',240)):
        if not isinstance(body.get(key),str) or not 0 < len(body[key].strip()) <= limit:
            return fail('请填写有效编号、名称、所属部门和适用场所', 400)
    if type(body.get('projectId')) is not int or type(body.get('templateId')) is not int or type(body.get('enabled')) is not bool:
        return fail('请选择所属项目、报告模板和启用状态', 400)
    project = db.session.get(Project, body['projectId'])
    template = db.session.get(ReportTemplateProfile, body['templateId'])
    if not project or not project.active or not template or not template.active:
        return fail('所属项目或报告模板不存在或已停用')
    ids = body.get('parameterIds')
    if not isinstance(ids, list) or not 1 <= len(ids) <= 200 or any(type(i) is not int for i in ids) or len(set(ids)) != len(ids):
        return fail('请选择 1–200 个不同的库内参数/方法', 400)
    caps = CapabilityEntry.query.filter(CapabilityEntry.id.in_(ids), CapabilityEntry.active.is_(True)).order_by(CapabilityEntry.id).all()
    if len(caps) != len(ids):
        return fail('参数已停用或不存在，请刷新配置')
    sites = {c.site for c in caps}
    if len(sites) != 1 or body['location'].strip() not in sites:
        return fail('适用场所必须与所选参数的能力地点一致；不同地点请分建子项目')
    row = TechnicalSubproject.query.filter_by(id=item_id).with_for_update().first() if item_id else None
    if item_id and not row:
        return fail('子项目不存在', 404)
    if row and (type(body.get('revision')) is not int or row.revision != body['revision']):
        return fail('配置版本已变更，请刷新后重试')
    if not row:
        row = TechnicalSubproject(project_id=project.id, template_id=template.id)
        db.session.add(row)
    else:
        row.revision += 1
    row.project_id, row.template_id = project.id, template.id
    for key in ('code','name','department','location'):
        setattr(row, key, body[key].strip())
    row.enabled = body['enabled']
    try:
        db.session.flush()
        TechnicalSubprojectParameter.query.filter_by(subproject_id=row.id).delete()
        for c in caps:
            db.session.add(TechnicalSubprojectParameter(subproject_id=row.id, capability_id=c.id))
        data = dict(id=row.id, revision=row.revision, code=row.code, name=row.name, projectId=project.id,
            projectCode=project.code, projectName=project.name, department=row.department, location=row.location,
            templateId=template.id, templateCode=template.code, templateName=template.name,
            templateReportType=template.report_type or '', enabled=row.enabled,
            parameters=[dict(id=c.id, name=c.item_name, method=c.method_clause or '', standard=c.standard_code, site=c.site, restriction=c.restriction or '') for c in caps])
        db.session.add(TechnicalSubprojectRevision(subproject_id=row.id, revision=row.revision, snapshot_json=json.dumps(data, ensure_ascii=False)))
        add_operation_audit('technical-subproject.configure', 'technical-subproject', row.id, actor=g.current_user,
            after={'revision':row.revision,'parameterCount':len(caps)}, category='configuration', message='维护检测子项目；历史快照不变，不变更检测资质与人员权限')
        db.session.commit()
        return ok(data)
    except IntegrityError:
        db.session.rollback()
        return fail('编号重复或并发修改，请刷新后重试')


def normalize_selection(value):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 50:
        raise ValueError('检测子项目必须为不超过 50 项的列表')
    result, seen = [], set()
    for item in value:
        if not isinstance(item, dict) or type(item.get('id')) is not int or type(item.get('revision')) is not int:
            raise ValueError('检测子项目标识或配置版本无效')
        identity = item['id'], item['revision']
        if item['id'] in seen:
            raise ValueError('检测子项目不能重复')
        row = db.session.get(TechnicalSubprojectRevision, identity)
        if not row:
            raise ValueError('检测子项目配置版本不存在，请重新选择')
        # Browser-provided names/methods/standards never override the snapshot.
        result.append(json.loads(row.snapshot_json))
        seen.add(item['id'])
    return result


def canonical_detail(detail):
    result = dict(detail or {})
    raw = result.get('rawSample')
    if not isinstance(raw, dict) or 'detectionSubprojects' not in raw:
        return result
    raw = dict(raw)
    rows = normalize_selection(raw['detectionSubprojects'])
    raw['detectionSubprojects'] = rows
    result['rawSample'] = raw
    # No changes to capability grants, method selection, money or permissions.
    # A link describes the selected technical work; it cannot authorize it.
    selected = raw.get('capabilityEntryIds') or []
    if not isinstance(selected, list) or any(type(i) is not int or i < 1 for i in selected):
        raise ValueError('样品能力参数必须是有效的参数 ID 列表')
    selected_parameters = set(selected)
    if any(p['id'] not in selected_parameters for row in rows for p in row['parameters']):
        raise ValueError('检测子项目所需参数尚未在样品能力参数中选全；请核对场所、标准及参数选择')
    codes = {r['templateCode'] for r in rows}
    if len(codes) > 1:
        raise ValueError('同一报告的子项目引用不同模板，请统一模板或拆分报告')
    sections = [s for s in result.get('summary', []) if s.get('title') != '检测子项目信息']
    if rows:
        fields = []
        for row in rows:
            fields.extend([[row['code'] + ' · ' + row['name'], row['projectName'] + ' / ' + row['department'] + ' / ' + row['location']],
                ['参数 / 方法 / 标准', '；'.join(p['name'] + ' / ' + p['method'] + ' / ' + p['standard'] for p in row['parameters'])],
                ['报告模板', row['templateName']]])
        sections.append({'title':'检测子项目信息','fields':fields})
    result['summary'] = sections
    return result


def configured_profile(report):
    rows = normalize_selection(((report.detail or {}).get('rawSample') or {}).get('detectionSubprojects'))
    if not rows:
        return None
    codes = {r['templateCode'] for r in rows}
    if len(codes) != 1:
        raise ValueError('检测子项目模板不一致')
    profile = ReportTemplateProfile.query.filter_by(code=next(iter(codes)), active=True).first()
    if not profile or not re.search(profile.report_no_pattern or r'$^', report.report_no or ''):
        raise ValueError('子项目报告模板已停用或不适用于本报告编号，请核对配置')
    return profile


def report_item_text(report, existing):
    rows = normalize_selection(((report.detail or {}).get('rawSample') or {}).get('detectionSubprojects'))
    return existing if not rows else str(existing or '') + '\n检测子项目：' + '；'.join(row['code'] + ' ' + row['name'] for row in rows)


def validate_render_kind(report, report_type):
    """The field-only renderer must not silently ignore the selected profile."""
    rows = normalize_selection(((report.detail or {}).get('rawSample') or {}).get('detectionSubprojects'))
    if not rows:
        return
    from ..docparser_field_only import _report_kind
    configured_profile(report)
    expected = {row.get('templateReportType') or '' for row in rows}
    if '' in expected or len(expected) != 1:
        raise ValueError('子项目模板缺少明确报告类型，请管理员补齐模板后更新子项目配置')
    if _report_kind(next(iter(expected))) != _report_kind(report_type):
        raise ValueError('当前报告类型与子项目指定模板不一致，请核对后再生成，不能以其他模板替代')
