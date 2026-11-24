from testkit.forms import loaded_form
from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile
import pytest
from lxml import etree
from app.extensions import db
from app.models import Standard
from app.document_field_projection import judgment_basis
from app import docparser_field_only as fields, document_module
from test_docparser_deep_integration import report
from test_admin_corrections import workspace, headers, url
from test_entrust_output_release import objects

pytest_plugins = ('testkit.fixtures',)
CODES = ['ISO 1234:2024', 'GB 2-2024', 'GB 3-2024']
STYLES = dict(zip(CODES, ['CN', 'EN', 'none']))
EXPECTED = 'ISO 1234:2024 《标准1》；\nGB 2-2024 <标准2>；\nGB 3-2024 标准3'


def library():
    for i, code in enumerate(CODES):
        db.session.add(Standard(code=code, name=f'标准{i+1}'))
    db.session.commit()


def settings(**extra):
    return dict(standardShowName=True, standardTitleStyles=STYLES, standardSeparatorText='；\n', **extra)


def test_save_reload_projection_and_legacy_client(workspace):
    client, actors, rows, _ = workspace
    item = rows[2]
    library()
    detail = deepcopy(item.detail)
    detail.setdefault('rawSample', {}).update(standardJudge='；'.join(CODES), judgmentDisplay=settings())
    item.detail = detail
    db.session.commit()
    def save(extra):
        record = client.get(url('reports', item), headers=headers(actors[1])).get_json()['data']
        return client.put(f'/api/reports/{item.report_no}/testinfo', headers=headers(actors[1]), json=loaded_form(client, f'/api/reports/{item.report_no}/testinfo', {
            'standards':['GB OTHER-2024'], 'standardShowName':False,
            'adminCorrection':{'revision':record['revision'],'confirmed':True,'reason':'核对判定依据显示'}, **extra,
        })).get_json()
    assert save({'judgmentDisplay':settings()})['code'] == 0
    db.session.refresh(item)
    assert item.detail['checkInput']['judgmentDisplay'] == settings()
    assert judgment_basis(item.detail, report=True) == EXPECTED
    assert save({})['code'] == 0
    assert judgment_basis(item.detail, report=True) == EXPECTED
    off = {**settings(), 'standardShowName':False, 'standardSeparatorText':' '}
    assert save({'judgmentDisplay':off})['code'] == 0
    assert judgment_basis(item.detail, report=True) == ' '.join(CODES)
    assert judgment_basis(item.detail) == EXPECTED  # Report overrides do not change the commission.
    assert save({'judgmentDisplay':{**off, 'standardSeparatorText':'<script>'}})['code'] != 0
    assert judgment_basis(item.detail, report=True) == ' '.join(CODES)


@pytest.mark.parametrize('language', ['CN','EN'])
def test_report_docx_keeps_mixed_styles(isolated_app, monkeypatch, language):
    from app.blueprints import report_publication
    monkeypatch.setattr(report_publication, 'report_qr_url', lambda _: 'https://example.invalid/report/judge')
    with isolated_app.app_context():
        library()
        item = report()
        item.id = 0; item.report_no = 'LAB-TEST-001'; item.department = ''
        item.detail['rawSample'].update(standardJudge='；'.join(CODES), reportLanguage=language)
        item.detail['checkInput'] = {'judgmentDisplay':settings()}
        before = deepcopy(item.detail)
        context = fields.report_context(item)
        assert context['Criteria'] == EXPECTED
        blob, _ = document_module.render_report(fields.profile_for(item), context)
        with ZipFile(BytesIO(blob)) as archive:
            text = ''.join(etree.fromstring(archive.read('word/document.xml')).xpath('//*[local-name()="t"]/text()'))
        for line in EXPECTED.split('\n'):
            assert line in text
        assert item.detail == before


@pytest.mark.parametrize('language,expected', [
    ('CN', 'GB/T 31433-2015 《建筑幕墙、门窗通用技术条件》'),
    ('EN', 'GB/T 31433-2015 <建筑幕墙、门窗通用技术条件>'),
])
def test_report_docx_keeps_judgment_title_with_enumeration_comma(isolated_app, monkeypatch, language, expected):
    from app.blueprints import report_publication
    monkeypatch.setattr(report_publication, 'report_qr_url', lambda _: 'https://example.invalid/report/judge')
    with isolated_app.app_context():
        item = report()
        item.id = 0
        item.report_no = 'LAB-TEST-001'
        item.department = ''
        item.detail['rawSample'].update(
            judgmentEntries=['GB/T 31433-2015 建筑幕墙、门窗通用技术条件', '按约定、附录 A'],
            reportLanguage=language, judgmentDisplay={'standardSeparatorText': '；'},
        )
        context = fields.report_context(item)
        assert context['Criteria'] == expected + '；按约定、附录 A'
        blob, _ = document_module.render_report(fields.profile_for(item), context)
        with ZipFile(BytesIO(blob)) as archive:
            text = ''.join(etree.fromstring(archive.read('word/document.xml')).xpath('//*[local-name()="t"]/text()'))
        assert expected + '；按约定、附录 A' in text


def test_existing_report_snapshot_keeps_legacy_judgment_and_accepts_renderer_update(isolated_app, monkeypatch):
    from app.blueprints import report_publication
    from app.report_version_consistency import confirmed_input_snapshot

    monkeypatch.setattr(report_publication, 'report_qr_url', lambda _: 'https://example.invalid/report/judge')
    with isolated_app.app_context():
        item = report()
        item.id = 0
        item.report_no = 'LAB-TEST-001'
        item.department = ''
        item.detail['rawSample'].update(
            standardJudge='GB/T 31433-2015 建筑幕墙、门窗通用技术条件',
            judgeBases={'legacy': True}, judgmentDisplay={'standardShowName': True},
        )
        current = {'report': {'detail': deepcopy(item.detail)}, 'template': fields.template_snapshot(item)}
        previous = deepcopy(current)
        previous['template']['fieldValues']['Criteria'] = 'GB/T 31433-2015 《建筑幕墙》；门窗通用技术条件'
        next(entry for entry in previous['template']['files'] if entry['filename'] == 'docparser_field_only.py')['sha256'] = '0' * 64
        assert confirmed_input_snapshot(current) == confirmed_input_snapshot(previous)
        item.detail['rawSample']['judgmentEntries'] = [item.detail['rawSample']['standardJudge']]
        current['report']['detail'] = deepcopy(item.detail)
        current['template']['fieldValues'] = fields.report_context(item)
        assert confirmed_input_snapshot(current) != confirmed_input_snapshot(previous)


@pytest.mark.parametrize('kind', ['product','product-extended','engineering','engineering-extended'])
def test_commission_output_and_names_without_narrow_year_regex(isolated_app, monkeypatch, kind):
    with isolated_app.app_context():
        library()
        monkeypatch.setattr(fields, 'institution_profile_for', lambda _: {'centerName':'虚拟机构'})
        entrust, item = objects(kind)
        item.report_no = 'LAB-TEST-R'
        item.detail['rawSample'].update(standardJudge='；'.join(CODES), judgmentDisplay=settings())
        assert fields.entrust_context(entrust, item, kind)['Criteria'] == EXPECTED
        blob, _ = fields.render_entrust(entrust, item, kind)
        with ZipFile(BytesIO(blob)) as archive:
            text = ''.join(etree.fromstring(archive.read('word/document.xml')).xpath('//*[local-name()="t"]/text()'))
        for line in EXPECTED.split('\n'):
            assert line in text


def test_aliases_free_text_no_judgment_and_language(isolated_app):
    with isolated_app.app_context():
        library()
        db.session.add(Standard(code='JJF 1001', name='术语'))
        db.session.commit()
        raw = {'standardJudge':'ISO 1234:2024；GB2—2024；JJF 1001', 'judgmentDisplay':{'standardShowName':True}}
        detail = {'rawSample':raw, 'reportComposition':{'reportLanguage':'EN'}}
        assert judgment_basis(detail, report=True) == 'ISO 1234:2024 <标准1>；GB2—2024 <标准2>；JJF 1001 <术语>'
        for value in ('/', '按委托要求', ''):
            raw['standardJudge'] = value
            assert judgment_basis(detail, '不应回退到检测依据', report=True) == value
        raw.pop('judgmentDisplay')
        raw['standardJudge'] = 'ISO 1234:2024；GB2—2024'
        assert judgment_basis(detail) == 'ISO 1234:2024《标准1》；GB2—2024《标准2》'


def test_display_labels_share_renderer_and_require_login(workspace):
    client, actors, _, _ = workspace
    library()
    path='/api/quality/std-library/display-names'
    assert client.post(path,json={'codes':CODES}).status_code == 401
    response=client.post(path,headers=headers(actors[1]),json={'codes':['GB2—2024','ISO 1234:2024','GB MISSING']}).get_json()
    assert response['data'] == {'GB2—2024':'标准2','ISO 1234:2024':'标准1','GB MISSING':''}
    for codes in (None, 'GB 2-2024', [None], ['x'*161], ['GB 2-2024']*201):
        result=client.post(path,headers=headers(actors[1]),json={'codes':codes}).get_json()
        assert result['code'] != 0


@pytest.mark.parametrize('report_output', [False, True])
@pytest.mark.parametrize('embedded', [False, True])
def test_judgment_order_independent_from_detection_records(isolated_app, report_output, embedded):
    from app.models import StdLibraryItem
    from app.functions.report_standard_text import load_report_standard_records, format_report_standards
    with isolated_app.app_context():
        first = StdLibraryItem(code='GB/T 3190-2020', name='成分')
        second = StdLibraryItem(code='GB/T 5237.1-2017', name='型材')
        db.session.add_all([first, second])
        db.session.flush()
        detail = {'rawSample': {
            'standardJudge': first.code + ('《登记名称》' if embedded else '') + '；按委托要求；' + second.code,
            'standardItemIds': [second.id, first.id],
            'judgmentDisplay': {'standardShowName': True}}}
        before = deepcopy(detail)
        assert judgment_basis(detail, report=report_output) == (
            first.code + (' 《登记名称》' if embedded else ' 《成分》') + '；按委托要求；' + second.code + ' 《型材》')
        records = load_report_standard_records([first.code, second.code], [second.id, first.id])
        assert format_report_standards([first.code, second.code], {}, True, records=records) == second.code + ' 《型材》；' + first.code + ' 《成分》'
        assert detail == before


def test_judgment_keeps_same_code_variants_inside_its_own_order(isolated_app):
    from app.models import StdLibraryItem
    with isolated_app.app_context():
        cn = StdLibraryItem(code='EN 442-1:2014', name='散热器')
        en = StdLibraryItem(code=cn.code, name='Radiators')
        first = StdLibraryItem(code='GB/T 3190-2020', name='成分')
        db.session.add_all([cn, en, first])
        db.session.flush()
        detail = {'rawSample': {'standardJudge': first.code + '；' + cn.code,
            'standardItemIds': [en.id, cn.id, first.id],
            'judgmentDisplay': {'standardShowName': True,
                'standardTitleStyles': {f'id:{en.id}': 'EN', f'id:{cn.id}': 'CN'}}}}
        assert judgment_basis(detail, report=True) == first.code + ' 《成分》；' + cn.code + ' <Radiators>；' + cn.code + ' 《散热器》'
