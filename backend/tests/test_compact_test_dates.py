from copy import deepcopy
import pytest
from app.report_date_display import compact_test_date, format_report_dates

@pytest.mark.parametrize('source,expected', [
 ('2026-10-11至2026-10-12','2026年10月11日至12日'),
 ('2026-10-31至2026-11-01','2026年10月31日至2026年11月1日'),
 ('2026-12-31至2027-01-01','2026年12月31日至2027年1月1日'),
 ('2026-10-11','2026年10月11日'),
 ('2026-10-12至2026-10-11','2026年10月12日至2026年10月11日'),
 ('2024-02-28至2024-02-29','2024年2月28日至29日'),
 ('2026年2月28日至2026年2月29日','2026年2月28日至2026年2月29日'),
 ('2026-10-11至2026-10-12；2026-11-01至2026-11-02','2026年10月11日至12日；2026年11月1日至2日'),
 ('2026年10月11日至12日','2026年10月11日至12日'),
 ('/','/'),('',''),
])
def test_only_same_month_testing_range_is_compact(source,expected):
 assert compact_test_date(source)==expected
 assert compact_test_date(expected)==expected

def test_field_boundary_keeps_input_and_other_date_fields():
 source='2026-10-11至2026-10-12'
 values=dict(TestDate=source,testDate=source,检测日期=source,ManufacturingDate=source,Remark=source)
 before=deepcopy(values);result=format_report_dates(values)
 assert values==before
 for key in ('TestDate','检测日期'):assert result[key]=='2026年10月11日至12日'
 assert result['testDate']=='2026年10月11日至2026年10月12日'
 assert result['ManufacturingDate']=='2026年10月11日至2026年10月12日'
 assert result['Remark']==source
 assert format_report_dates(values,language='EN')['TestDate']=='11 Oct 2026 to 12 Oct 2026'
