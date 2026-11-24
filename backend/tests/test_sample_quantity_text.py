from io import BytesIO
from zipfile import ZipFile
from lxml import etree
import pytest
from test_entrust_output_release import objects
from app import docparser_field_only as fields
from app.entrust_render import _business_values
from app.document_module import verify_vendor
pytest_plugins = ('testkit.fixtures',)

@pytest.mark.parametrize('quantity,unit,expected', [('3','台','3 台'),('3台','台','3台'),('2台、3套','','2台、3套'),('0.5 m²','','0.5 m²'),('台式设备3','台','台式设备3 台')])
def test_quantity_legacy_and_full_text(quantity,unit,expected):
    e,r=objects();r.report_no='LAB-TEST-R';r.detail['rawSample'].update(sampleAmount=quantity,unit=unit)
    assert _business_values(e,r)['quantity']==expected

@pytest.mark.parametrize('kind', ['product','product-extended'])
@pytest.mark.parametrize('quantity', ['2台、3套及4件','1234台、5678套及90件'])
def test_quantity_complete_in_every_form(isolated_app,kind,quantity):
    with isolated_app.app_context():
        verify_vendor()
        e,r=objects();r.report_no='LAB-TEST-R';r.detail['rawSample'].update(sampleAmount=quantity,unit='')
        blob,_=fields.render_entrust(e,r,kind)
        with ZipFile(BytesIO(blob)) as z:
            text=''.join(etree.fromstring(z.read('word/document.xml')).xpath('//*[local-name()="t"]/text()'))
        assert text.count(quantity)==4
        assert '{{ Quantity }}' not in text

@pytest.mark.parametrize('kind', ['product','product-extended'])
def test_quantity_above_old_limit_fits_new_supplier_template(isolated_app,kind):
    with isolated_app.app_context():
        e,r=objects();r.report_no='LAB-TEST-R';r.detail['rawSample'].update(sampleAmount='一二三四五六七八九十台',unit='')
        blob,_=fields.render_entrust(e,r,kind)
        with ZipFile(BytesIO(blob)) as z:
            text=''.join(etree.fromstring(z.read('word/document.xml')).xpath('//*[local-name()="t"]/text()'))
        assert text.count('一二三四五六七八九十台')==4

@pytest.mark.parametrize('kind', ['product','product-extended'])
def test_supplier_paragraph_does_not_truncate_long_quantity(isolated_app,kind):
    with isolated_app.app_context():
        e,r=objects();r.report_no='LAB-TEST-R';r.detail['rawSample'].update(sampleAmount='超长数量'*1000,unit='')
        # Supplier build_paragraph keeps the full text at its minimum font
        # when no style fits. This checks data preservation, not visual fit.
        blob,_=fields.render_entrust(e,r,kind)
        with ZipFile(BytesIO(blob)) as z:
            text=''.join(etree.fromstring(z.read('word/document.xml')).xpath('//*[local-name()="t"]/text()'))
        assert text.count('超长数量'*1000)==4

@pytest.mark.parametrize('kind', ['engineering','engineering-extended'])
def test_unused_quantity_does_not_block_engineering(isolated_app,kind):
    with isolated_app.app_context():
        e,r=objects(kind);r.report_no='LAB-TEST-R'
        r.detail['rawSample'].update(sampleAmount='一二三四五六七八九十台',unit='')
        blob,_=fields.render_entrust(e,r,kind)
        assert blob.startswith(b'PK')
