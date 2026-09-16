# -*- coding: utf-8 -*-
"""
tests/test_alerts_filter.py — LỌC CẢNH BÁO (thuần, không cần Streamlit)
========================================================================
filter_alert_items: tìm kiếm theo từ khoá + lọc mức độ Cao/Trung bình.
"""
from __future__ import annotations

from pages.alerts import filter_alert_items

ITEMS = [
    {"title": "Quá hạn 40 ngày", "meta": "PM001",
     "details": ["Máy chiếu Epson", "Nguyễn Văn An"], "severity": "danger"},
    {"title": "Quá hạn 5 ngày", "meta": "PM002",
     "details": ["Loa JBL", "Trần Thị Bình"], "severity": "warning"},
    {"title": "Thiết bị thất thoát", "meta": "TB009",
     "details": ["Tablet"], "severity": "danger"},
]


def test_filter_by_query_matches_title_meta_details():
    assert [i["meta"] for i in filter_alert_items(ITEMS, search="pm001")] == ["PM001"]
    assert [i["meta"] for i in filter_alert_items(ITEMS, search="loa")] == ["PM002"]
    assert filter_alert_items(ITEMS, search="không có") == []


def test_filter_by_severity():
    assert {i["meta"] for i in filter_alert_items(ITEMS, severity="Cao")} == {"PM001", "TB009"}
    assert [i["meta"] for i in filter_alert_items(ITEMS, severity="Trung bình")] == ["PM002"]
    assert len(filter_alert_items(ITEMS, severity="Tất cả")) == 3


def test_filter_combined():
    assert [i["meta"] for i in filter_alert_items(ITEMS, search="quá hạn", severity="Cao")] == ["PM001"]
    assert filter_alert_items([], search="x") == []
