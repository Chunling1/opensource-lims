from types import SimpleNamespace

import pytest

from app.docparser_field_only import _sample_form_engineering_name


@pytest.mark.parametrize('detail, expected', [
    ({'rawSample': {'engineeringName': '', 'sampleName': '不能借用的样品名'}}, '/'),
    ({'rawSample': {'engineeringName': '  \t\n'}}, '/'),
    ({'rawSample': {'engineeringName': None}}, '/'),
    ({'rawSample': {'engineeringName': '幕墙试验工程'}}, '幕墙试验工程'),
    ({'summary': [{'title': '送样信息', 'fields': [('工程名称（幕墙）', '')]}]}, '/'),
    ({}, '/'),
    ({'rawSample': {'sampleName': '旧记录工程名称'}}, '旧记录工程名称'),
])
def test_engineering_name_empty_fallback(detail, expected):
    assert _sample_form_engineering_name(SimpleNamespace(detail=detail)) == expected
