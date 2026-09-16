# -*- coding: utf-8 -*-
"""
tests/test_layout_equal.py — KHOÁ FIX CÂN CHIỀU CAO 2 LỖI LAYOUT
================================================================
- Lỗi 1 (Tổng quan): 2 chart cạnh nhau dùng cùng chiều cao cơ sở, weekday bù
  đúng phần trục X xoay nhãn, footer cùng 1 dòng, hàng bọc key để CSS stretch.
- Lỗi 2 (Cảnh báo): 2 card bọc key để CSS stretch + pagination bám đáy, nút
  hành động xuống dòng thay vì ellipsis "Chi t...", slots bù giữ nguyên.

AppTest không đo được px nên test khoá ở mức config + CSS + nội dung render
(không exception, đủ 2 card, đủ slots/pagination). Không chạm data/*.csv.
"""
from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from ui import charts

CSS_FILE = Path(__file__).resolve().parent.parent / "styles" / "dashboard.css"
APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _run(page: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["page"] = page
    at.run()
    return at


def test_weekday_plot_compensates_rotated_category_axis():
    """Plot weekday cao hơn đúng phần trục X xoay nhãn để tổng khối bằng nhau."""
    assert charts.CHART_HEIGHT == 240
    assert charts.WEEKDAY_EXTRA_AXIS == 40
    assert charts.WEEKDAY_CHART_HEIGHT == charts.CHART_HEIGHT + charts.WEEKDAY_EXTRA_AXIS


def test_equal_row_css_scopes_and_stretches():
    css = CSS_FILE.read_text(encoding="utf-8")
    assert ".st-key-ov_equal_charts" in css
    assert ".st-key-alerts_equal_row" in css
    assert "align-items: stretch" in css
    # Pagination bám đáy chỉ có tác dụng khi card đã giãn đầy cột.
    assert "margin-top: auto" in css


def test_chart_footers_locked_to_single_line():
    css = CSS_FILE.read_text(encoding="utf-8")
    assert ".chart-footer strong" in css
    assert ".chart-footer span" in css


def test_alert_action_buttons_wrap_instead_of_ellipsis():
    """Không còn nowrap nào trên nút Chi tiết/Đã xử lý (nguồn của 'Chi t...')."""
    css = CSS_FILE.read_text(encoding="utf-8")
    for selector in ('[class*="st-key-alert_"]', '[class*="st-key-handled_"]'):
        start = css.find(selector)
        assert start != -1, selector
        block = css[start: css.find("}", start)]
        assert "white-space: normal" in block, selector
        assert "nowrap" not in block, selector


def test_overview_renders_both_equal_cards_without_exception():
    at = _run("overview")
    assert len(at.exception) == 0, at.exception
    html = " ".join(m.value for m in at.markdown)
    assert "Lượt mượn theo loại thiết bị" in html
    assert "Ngày mượn nhiều nhất" in html
    # Mỗi chart kèm đúng 1 footer tóm tắt cùng class (chiều cao footer bằng nhau).
    assert html.count('class="chart-footer"') >= 2


def test_alerts_equal_cards_slots_and_pagination_intact():
    at = _run("alerts")
    assert len(at.exception) == 0, at.exception
    html = " ".join(m.value for m in at.markdown)
    assert "Quá hạn" in html and "Thất thoát" in html
    assert "alert-slot-empty" in html  # nhóm ngắn vẫn bù ô trống
    assert html.count('class="pagination-info"') == 3  # đủ 3 nhóm
    keys = [b.key for b in at.button]
    assert "alert_page_overdue_next" in keys
    assert "handled_alert_overdue_PM061" in keys
