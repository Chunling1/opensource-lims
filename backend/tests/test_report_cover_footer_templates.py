"""Supplied report templates and the four-line institutional cover footer."""
from io import BytesIO
import json
from zipfile import ZipFile

from lxml import etree
import pytest

from app import document_module


PROFILES = [(kind, variant, language)
            for kind, variants in [('Product', ['Standard', 'Extended']),
                                   ('Sampling', ['Standard', 'Extended']),
                                   ('Engineering', ['Standard']), ('Inspection', ['Standard'])]
            for variant in variants for language in ['CN', 'EN']]
PROFILES.append(('Calibration', 'Standard', 'CN'))
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


@pytest.mark.parametrize('kind,variant,language', [p for p in PROFILES if p[0] != 'Calibration'])
def test_cover_footer_styles_resolve_and_preserve_all_four_lines(tmp_path, kind, variant, language):
    # Use the real helper in its isolated vendor working directory. Four lines
    # exercise the new final style even for centers whose default has two lines.
    output = tmp_path / 'cover.docx'
    script = '''
import sys
sys.path.insert(0, str(__import__('pathlib').Path.cwd().parents[1] / '_vendor'))
from template_helper import ReportProduct, ReportSampling, ReportEngineering, ReportInspection, ReportCalibration
kind, variant, language, output = sys.argv[1:]
helper = globals()['Report' + kind](f'assets/templates/LAB-Report-{kind}-{language}-{variant}-202609_tpl.docx',
    CoverFooter='Company CN\\nCompany EN\\nCenter CN\\nCenter EN & testing')
helper._template.render({'CoverFooter': helper._cover_footer})
helper._template.save(output)
'''
    import os
    import subprocess
    import sys
    env = {k: v for k, v in os.environ.items()
           if k.upper() in {'PATH', 'SYSTEMROOT', 'SYSTEMDRIVE', 'PROGRAMDATA', 'WINDIR', 'TEMP', 'TMP', 'LANG'}}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    result = subprocess.run([sys.executable, '-B', '-c', script, kind, variant, language, str(output)],
                            cwd=document_module.VENDOR, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    with ZipFile(output) as archive:
        root = etree.fromstring(archive.read('word/document.xml'))
        styles = etree.fromstring(archive.read('word/styles.xml'))
    declared = {n.get(W+'styleId') for n in styles.findall(W+'style')}
    expected_styles = ['cover-footer-song', 'cover-footer-song-small', 'cover-footer-song-fs',
                       'cover-footer-song-small-5']
    values = ['Company CN', 'Company EN', 'Center CN', 'Center EN & testing']
    actual = []
    for p in root.iter(W+'p'):
        text = ''.join(p.itertext())
        if text in values:
            style = p.find(W+'pPr/'+W+'pStyle').get(W+'val')
            assert style in declared
            actual.append((text, style))
    assert actual == list(zip(values, expected_styles))


@pytest.mark.parametrize('kind,variant,language', PROFILES)
def test_platform_report_render_accepts_updated_templates(kind, variant, language):
    profile = dict(kind=kind.lower(), category=kind, variant=variant, language=language,
                   center='LAB' if kind in {'Inspection', 'Calibration'} else 'LAB',
                   extended=variant == 'Extended')
    blob, audit = document_module.render_report(profile, {
        'ReportNo': 'LAB-QA-001', 'SampleName': 'QA sample', 'Client': 'QA client',
        'ReportDate': '', 'ReportQRCode': 'https://example.invalid/report/template-qa',
    })
    with ZipFile(BytesIO(blob)) as archive:
        text = ''.join(''.join(etree.fromstring(archive.read(n)).itertext())
                       for n in archive.namelist() if n.startswith('word/') and n.endswith('.xml'))
    assert 'LAB-QA-001' in text
    assert '{{' not in text and '{%' not in text
    assert audit['operation'] == 'report'
    # Both exact package integrity and audit fingerprints still bind the update.
    manifest = json.loads(document_module.MANIFEST.read_text(encoding='utf-8'))
    assert document_module.verify_vendor() == manifest['archiveSha256']
