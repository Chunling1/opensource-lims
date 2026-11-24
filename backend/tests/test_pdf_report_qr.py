from unittest.mock import Mock

import fitz
import pytest

from qr_pdf_fixture import add_cover_qr, qr_png

pytest_plugins = ('testkit.fixtures',)


def source(*, rotated=False, no_qr=False, overlap=False, wrong_qr=False, signature=False):
    with fitz.open() as doc:
        for index in range(4):
            page = doc.new_page(width=842 if index == 2 else 595, height=595 if index == 2 else 842)
            page.draw_rect(page.rect, fill=(.85, .9, 1), overlay=False)
            page.insert_text((45, 100), f'QA report page {index + 1}')
        if not no_qr:
            add_cover_qr(doc)
            doc[0].insert_image((50, 680, 122, 752), stream=qr_png('https://example.invalid/account'))
        if rotated:
            doc[2].set_rotation(90)
        if overlap:
            doc[1].insert_text((540, 35), 'BUSY')
        if wrong_qr:
            from app.pdf_report_qr import MM
            doc[1].insert_image((595-21*MM, 5*MM, 595-5*MM, 21*MM), stream=qr_png('https://example.invalid/other'))
        if signature:
            widget = fitz.Widget()
            widget.field_name = 'signature'
            widget.field_type = fitz.PDF_WIDGET_TYPE_SIGNATURE
            widget.rect = fitz.Rect(100, 200, 200, 240)
            doc[1].add_widget(widget)
        return doc.tobytes()


@pytest.mark.parametrize('category', ['product', 'sampling', 'inspection', 'engineering', 'calibration'])
@pytest.mark.parametrize('rotated', [False, True])
def test_original_qr_no_backing_exclusions_and_byte_idempotence(category, rotated):
    from app.pdf_report_qr import add_interior_report_qr, MM
    raw = source(rotated=rotated)
    final, proof = add_interior_report_qr(raw, category=category)
    assert proof['pages'] == ([2, 3, 4] if category == 'calibration' else [2, 3])
    assert proof['addedBackground'] is False
    assert add_interior_report_qr(final, category=category)[0] == final
    with fitz.open(stream=raw) as before, fitz.open(stream=final) as after:
        for index in range(len(before)):
            assert before[index].get_text() == after[index].get_text()
            if index + 1 not in proof['pages']:
                assert before[index].get_pixmap().samples == after[index].get_pixmap().samples
                continue
            page = after[index]
            rect = fitz.Rect(page.rect.width-21*MM, 5*MM, page.rect.width-5*MM, 21*MM)
            item = next(x for x in page.get_image_info(xrefs=True) if abs((fitz.Rect(x['bbox'])*page.rotation_matrix).x0-rect.x0) < .3)
            assert page.parent.extract_image(item['xref'])['smask'] > 0
            assert len(page.get_drawings()) == len(before[index].get_drawings())  # No white rectangle.
            assert before[index].get_pixmap(clip=(0, 70, page.rect.width, page.rect.height)).samples == page.get_pixmap(clip=(0, 70, page.rect.width, page.rect.height)).samples


@pytest.mark.parametrize('condition, message', [('no_qr', '无法唯一识别'), ('overlap', '重叠'), ('wrong_qr', '不同图像'), ('signature', '已签名')])
def test_reject_unsafe_input_without_overwriting(condition, message):
    from app.pdf_report_qr import add_interior_report_qr
    with pytest.raises(ValueError, match=message):
        add_interior_report_qr(source(**{condition: True}), category='product')


def test_repeated_preview_and_retry_do_not_generate_again(isolated_app, monkeypatch):
    from app import preview_cache as cache, report_documents as documents, docparser_field_only as fields
    from app.extensions import db
    from app.models import Report
    monkeypatch.setattr(fields, 'applies_to', lambda _: True)
    monkeypatch.setattr(fields, 'profile_for', lambda _: {'kind': 'product'})
    compose = Mock(return_value=(source(), []))
    monkeypatch.setattr(documents, '_compose_complete_report_pdf', compose)
    monkeypatch.setattr(cache, 'source_snapshot', lambda r: {'detail': r.detail})
    monkeypatch.setattr(cache, '_enqueue', lambda app, task, **kw: cache._execute(app, *task))
    with isolated_app.app_context():
        r = Report(report_no='QA-QR-CACHE', detail={'input': 1})
        db.session.add(r); db.session.commit()
        no = r.report_no
        cache.prepare(r)
        first, state = cache.cached_pdf(Report.query.filter_by(report_no=no).one())
        assert state['status'] == 'ready'
        for retry in [False, True, True]:
            r = Report.query.filter_by(report_no=no).one()
            assert cache.prepare(r, retry=retry)['status'] == 'ready'
            assert cache.cached_pdf(r)[0] == first
        assert compose.call_count == 1
        r.detail = {'input': 2}; db.session.commit()
        cache.prepare(r)
        assert cache.status(Report.query.filter_by(report_no=no).one())['status'] == 'ready'
        assert compose.call_count == 2
