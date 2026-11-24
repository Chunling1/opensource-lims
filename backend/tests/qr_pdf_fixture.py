"""Real transparent QR fixtures; URLs are deliberately non-production."""
from io import BytesIO
from pathlib import Path
import sys


def qr_png(text='https://example.invalid/report/qa'):
    sys.path.insert(0, str(Path(__file__).parents[1] / '_vendor'))
    try:
        import qrcode
    finally:
        sys.path.pop(0)
    qr = qrcode.QRCode(box_size=6, border=4)
    qr.add_data(text)
    qr.make(fit=True)
    image = qr.make_image(fill_color='black', back_color='transparent').convert('RGBA')
    stream = BytesIO()
    image.save(stream, format='PNG')
    return stream.getvalue()


def add_cover_qr(doc):
    doc[0].insert_image((450, 680, 522, 752), stream=qr_png())
