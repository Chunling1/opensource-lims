"""Render uploaded conclusions completely before fitting the fixed report cell."""
from io import BytesIO

POLICY = 'conclusion-wps-image-v1'


def render(blob, converter):
    import fitz
    from PIL import Image, ImageChops
    pdf = converter(blob)
    if not pdf or not pdf.startswith(b'%PDF-'):
        raise ValueError('结论文件 WPS 转换失败，未生成报告')
    images = []
    with fitz.open(stream=pdf, filetype='pdf') as document:
        for page in document:
            if page.rect.width * page.rect.height * 9 > 16_000_000:
                raise ValueError('结论文件页面尺寸过大，请调整为普通纸张；未生成报告')
            pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False, colorspace=fitz.csRGB)
            image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            bbox = ImageChops.difference(image, Image.new('RGB', image.size, 'white')).getbbox()
            if bbox is None:
                continue
            if images:
                raise ValueError('结论文件包含多页内容，请精简为一页后重新上传；未生成报告')
            # Include all visible ink, including borders/images, with a small margin.
            bbox = (max(0, bbox[0]-3), max(0, bbox[1]-3), min(image.width, bbox[2]+3), min(image.height, bbox[3]+3))
            sizes = [s['size'] for b in page.get_text('dict')['blocks'] if 'lines' in b
                     for line in b['lines'] for s in line['spans'] if s['text'].strip()]
            cropped = image.crop(bbox)
            data = BytesIO(); cropped.save(data, format='PNG')
            images.append((data.getvalue(), {'widthPt': cropped.width/3, 'heightPt': cropped.height/3,
                                           'minFontPt': min(sizes) if sizes else None}))
    if not images:
        raise ValueError('结论文件没有可见内容，未生成报告')
    if len(images) != 1:
        raise ValueError('结论文件包含多页内容，请精简为一页后重新上传；未生成报告')
    return images[0]
