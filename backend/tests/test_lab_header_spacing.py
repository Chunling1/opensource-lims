"""Render real templates: LAB reserves two styled header paragraphs for QR space."""
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import pytest
from app.document_module import render_report, verify_vendor

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = "{" + NS["w"] + "}"
# Calibration has empty fixed headers and does not consume PageHeader.
PROFILES = [(k,l,v) for k in ("product","sampling") for l in ("CN","EN")
            for v in ("Standard","Extended")] + [(k,l,"Standard")
            for k in ("engineering","inspection") for l in ("CN","EN")]

@pytest.mark.parametrize("kind,language,variant", PROFILES)
def test_lab_header_preserves_two_blank_paragraphs_and_text_styles(kind, language, variant):
    blob, _ = render_report(dict(center="LAB", kind=kind, language=language,
                                 variant=variant, requirements={}),
                            dict(ReportNo="LAB-2026QA-0001", SampleName="Local QA"))
    headers = []
    with ZipFile(BytesIO(blob)) as package:
        for name in package.namelist():
            if name.startswith("word/header") and name.endswith(".xml"):
                root = ET.fromstring(package.read(name))
                paras = root.findall(".//w:p", NS)
                texts = ["".join(p.itertext()) for p in paras]
                if "Example Testing Lab Co., Ltd." in texts:
                    headers.append((paras,texts))
    assert headers, "Rendered report must contain the institution header"
    for paras, texts in headers:
        english = texts.index("Example Testing Lab Co., Ltd.")
        assert english == 3
        assert texts[:2] == ["", ""]
        assert texts[2] == "示例检测机构"
        assert [p.find("w:pPr/w:pStyle", NS).get(W+"val") for p in paras[:4]] == [
            "page-header-song", "page-header-song-small", "page-header-song", "page-header-song-small"]
        assert any("LAB-2026QA-0001" in text for text in texts[4:])

def test_vendor_revision_manifest_matches_current_files():
    assert verify_vendor()
