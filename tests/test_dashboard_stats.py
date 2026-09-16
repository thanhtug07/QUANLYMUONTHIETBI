# -*- coding: utf-8 -*-
"""
tests/test_dashboard_stats.py — KIỂM TRA SỐ LIỆU CHO DASHBOARD MỚI
==================================================================
Chỉ kiểm tra helper thuần (không render Streamlit, không chạm CSV thật):

- borrows_by_weekday: đủ 7 nhãn đúng thứ tự, đếm đúng, bỏ ngày lỗi;
- previous_window: kỳ trước liền kề cùng độ dài, None khi "Tất cả";
- format_delta: chuỗi pill đúng, None khi kỳ trước bằng 0 (caller ẨN pill);
- compute_all: có key borrows_by_weekday;
- MetricCard delta: markup pill đúng tone, ẩn khi rỗng.
"""
from __future__ import annotations

from datetime import date

import statistics as stat_mod
from ui.metrics import MetricCard, render_metric_card
from utils.helpers import previous_window

TODAY = date(2026, 9, 16)  # Thứ 2


def test_weekday_labels_order_monday_first():
    assert stat_mod.WEEKDAY_LABELS[0] == "Thứ 2"
    assert stat_mod.WEEKDAY_LABELS[-1] == "Chủ nhật"
    assert len(stat_mod.WEEKDAY_LABELS) == 7


def test_borrows_by_weekday_counts_and_order():
    rows = [
        {"borrow_date": "14/09/2026", "due_date": "20/09/2026"},  # Thứ 2
        {"borrow_date": "14/09/2026", "due_date": "20/09/2026"},  # Thứ 2
        {"borrow_date": "16/09/2026", "due_date": "23/09/2026"},  # Thứ 4
        {"borrow_date": "abc", "due_date": ""},  # ngày lỗi -> bỏ qua
    ]
    result = stat_mod.borrows_by_weekday(rows)
    assert [label for label, _ in result] == list(stat_mod.WEEKDAY_LABELS)
    assert dict(result)["Thứ 2"] == 2
    assert dict(result)["Thứ 4"] == 1
    assert sum(count for _, count in result) == 3


def test_borrows_by_weekday_empty_has_seven_zeroes():
    result = stat_mod.borrows_by_weekday([])
    assert len(result) == 7
    assert all(count == 0 for _, count in result)


def test_previous_window_fixed_modes():
    assert previous_window("7 ngày", today=TODAY) == (date(2026, 9, 1), date(2026, 9, 8))
    assert previous_window("30 ngày", today=TODAY) == (date(2026, 7, 17), date(2026, 8, 16))
    assert previous_window("3 tháng", today=TODAY) == (date(2026, 3, 19), date(2026, 6, 17))


def test_previous_window_custom_and_all():
    assert previous_window("Tùy chỉnh", date(2026, 9, 1), date(2026, 9, 10), TODAY) == (
        date(2026, 8, 22), date(2026, 8, 31))
    assert previous_window("Tất cả", today=TODAY) is None


def test_format_delta_values():
    assert stat_mod.format_delta(120, 100) == "+20,0%"
    assert stat_mod.format_delta(80, 100) == "−20,0%"
    assert stat_mod.format_delta(100, 100) == "0,0%"
    assert stat_mod.format_delta(5, 0) is None
    assert stat_mod.format_delta(0, 0) is None


def test_compute_all_has_weekday_key():
    stats = stat_mod.compute_all([], [], [])
    assert len(stats["borrows_by_weekday"]) == 7


def test_metric_card_delta_markup_and_tones():
    html = render_metric_card(MetricCard("X", 10, delta="+12,5%", delta_tone="good"))
    assert "kpi-delta good" in html and "12,5%" in html
    html = render_metric_card(MetricCard("X", 10, delta="−8,0%", delta_tone="bad"))
    assert "kpi-delta bad" in html
    html = render_metric_card(MetricCard("X", 10))
    assert "kpi-delta" not in html
