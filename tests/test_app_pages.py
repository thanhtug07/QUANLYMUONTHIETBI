# -*- coding: utf-8 -*-
"""
tests/test_app_pages.py — KIỂM TRA 7 TRANG QUA AppTest (CHỈ ĐỌC, KHÔNG GHI)
===========================================================================
- 7/7 trang render không exception;
- tương tác chính: filter / tìm kiếm / sắp xếp / Prev-Next phân trang;
- hồi quy stale-page: đổi filter làm tổng số trang co lại thì dòng phạm vi
  phải hiện "1–1 / 1" chứ không phải "41–41 / 1".

KHÔNG chạm data/*.csv thật: mọi thao tác chỉ đọc (không mở dialog ghi,
không submit form). Verify bằng `git diff data/` sau khi chạy.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")
DATA = Path(__file__).resolve().parent.parent / "data" / "borrow_records.csv"

PAGES = ["overview", "borrowing", "equipment", "borrowers", "alerts", "reports", "csv"]


def _run(page: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["page"] = page
    at.run()
    return at


def _first_borrow_id() -> str:
    with DATA.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if (row.get("borrow_id") or "").strip():
                return row["borrow_id"].strip()
    raise AssertionError("borrow_records.csv thiếu borrow_id để test tìm kiếm")


def test_all_pages_render_without_exception():
    for page in PAGES:
        at = _run(page)
        assert len(at.exception) == 0, f"trang {page}: {at.exception}"


def test_borrowing_filter_search_pagination():
    at = _run("borrowing")
    at.selectbox(key="borrow_status").set_value("Đã trả").run()
    assert len(at.exception) == 0
    at.text_input(key="borrow_search").set_value(_first_borrow_id()).run()
    assert len(at.exception) == 0
    at2 = _run("borrowing")
    at2.button(key="borrow_page_next").click().run()
    assert len(at2.exception) == 0
    assert at2.session_state["borrow_page"] == 2
    at2.button(key="borrow_page_prev").click().run()
    assert len(at2.exception) == 0
    assert at2.session_state["borrow_page"] == 1


def test_equipment_sort_and_status_filter():
    at = _run("equipment")
    at.selectbox(key="device_sort").set_value("Lượt mượn").run()
    assert len(at.exception) == 0
    at.selectbox(key="device_status").set_value("Sẵn sàng").run()
    assert len(at.exception) == 0


def test_overview_time_filter_and_borrowers_search():
    at = _run("overview")
    at.selectbox(key="filter_time").set_value("30 ngày").run()
    assert len(at.exception) == 0
    at2 = _run("borrowers")
    at2.text_input(key="borrower_search").set_value("CNTT").run()
    assert len(at2.exception) == 0


def test_stale_page_range_is_clamped():
    """Trang 5 + search còn 1 dòng -> phải hiện 1–1, không phải 41–41."""
    at = _run("borrowing")
    at.session_state["borrow_page"] = 5
    at.text_input(key="borrow_search").set_value(_first_borrow_id()).run()
    assert len(at.exception) == 0
    infos = [m.value for m in at.markdown if '<div class="pagination-info">' in m.value]
    assert infos, "phải còn thanh phân trang khi có 1 kết quả"
    text = infos[0]
    assert re.search(r">1–1 / 1 phiếu mượn<", text), text
    assert "41–" not in text, text


def _pagination_texts(at) -> list:
    """Các dòng phạm vi phân trang (bỏ khối CSS inject lẫn trong markdown)."""
    out = []
    for m in at.markdown:
        if '<div class="pagination-info">' in m.value:
            found = re.search(r">(\d+–\d+ / \d+[^<]*)<", m.value)
            if found:
                out.append(found.group(1))
    return out


def test_alerts_groups_paginate_five_per_page():
    """Mỗi nhóm cảnh báo 5 mục/trang: trang 1 là 1–5, sang trang là 6–10."""
    at = _run("alerts")
    assert len(at.exception) == 0
    assert "1–5 / 11 phiếu quá hạn" in _pagination_texts(at)
    at.button(key="alert_page_overdue_next").click().run()
    assert len(at.exception) == 0
    assert at.session_state["alert_page_overdue"] == 2
    assert "6–10 / 11 phiếu quá hạn" in _pagination_texts(at)


def test_alerts_filter_clamps_page():
    """Lọc còn 1 dòng khi đang ở trang sau -> kẹp về 1–1."""
    at = _run("alerts")
    at.session_state["alert_page_overdue"] = 3
    at.text_input(key="alert_search").set_value("PM061").run()
    assert len(at.exception) == 0
    assert "1–1 / 1 phiếu quá hạn" in _pagination_texts(at)


def test_alerts_dismiss_hides_item_for_session():
    """Bấm 'Đã xử lý' ẩn mục trong phiên + hiện ghi chú; Đặt lại hiện lại."""
    at = _run("alerts")
    before = " ".join(m.value for m in at.markdown)
    assert "alert_overdue_PM061" in str([b.key for b in at.button])
    at.button(key="handled_alert_overdue_PM061").click().run()
    assert len(at.exception) == 0
    after = " ".join(m.value for m in at.markdown)
    assert "PM061" not in after
    captions = " ".join(c.value for c in at.caption)
    assert "Đã ẩn 1 mục đã xử lý" in captions
    at.button(key="alert_reset").click().run()
    assert len(at.exception) == 0
    restored = " ".join(m.value for m in at.markdown)
    assert "PM061" in restored


def test_alerts_short_group_padded_with_empty_slots():
    """Nhóm 4 mục (Thất thoát) được bù ô trống để cân block Quá hạn."""
    at = _run("alerts")
    html = " ".join(m.value for m in at.markdown)
    assert "alert-slot-empty" in html
