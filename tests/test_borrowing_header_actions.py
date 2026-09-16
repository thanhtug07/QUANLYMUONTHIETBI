# -*- coding: utf-8 -*-
"""Cụm nút header card 'Danh sách phiếu mượn': sort mới nhất, xóa-all theo filter."""
from __future__ import annotations

import csv
from pathlib import Path

from streamlit.testing.v1 import AppTest

import data_store
from cleaners import RECORD_COLUMNS
from pages import borrowing

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _run(page: str = "borrowing") -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["page"] = page
    at.run()
    return at


def test_sort_newest_first_puts_latest_borrow_date_on_top():
    records = [
        {"borrow_id": "PM001", "borrow_date": "01/01/2024"},
        {"borrow_id": "PM002", "borrow_date": "20/06/2025"},
        {"borrow_id": "PM003", "borrow_date": ""},
        {"borrow_id": "PM004", "borrow_date": "15/03/2024"},
    ]
    ordered = borrowing.sort_records_by_borrow_date(records, newest_first=True)
    assert [r["borrow_id"] for r in ordered] == ["PM002", "PM004", "PM001", "PM003"]
    oldest = borrowing.sort_records_by_borrow_date(records, newest_first=False)
    assert [r["borrow_id"] for r in oldest][:3] == ["PM001", "PM004", "PM002"]
    assert oldest[-1]["borrow_id"] == "PM003"  # ngày rỗng luôn cuối, không crash


def test_delete_all_only_removes_filtered_scope(tmp_path):
    target = tmp_path / "borrow_records.csv"
    rows = [
        {"borrow_id": "PM001", "device_id": "TB001", "borrower_id": "U01",
         "borrow_date": "01/01/2024", "due_date": "10/01/2024", "return_date": "",
         "status": "borrowing"},
        {"borrow_id": "PM002", "device_id": "TB002", "borrower_id": "U02",
         "borrow_date": "02/01/2024", "due_date": "12/01/2024", "return_date": "",
         "status": "borrowing"},
        {"borrow_id": "PM003", "device_id": "TB003", "borrower_id": "U03",
         "borrow_date": "03/01/2024", "due_date": "13/01/2024", "return_date": "",
         "status": "returned"},
    ]
    data_store.write_rows(target, RECORD_COLUMNS, rows)
    removed = data_store.delete_rows(target, RECORD_COLUMNS, "borrow_id", ["PM001", "PM002"])
    assert removed == 2
    kept = data_store.read_raw_rows(target, RECORD_COLUMNS)
    assert [r["borrow_id"] for r in kept] == ["PM003"]
    assert data_store.delete_rows(target, RECORD_COLUMNS, "borrow_id", []) == 0  # rỗng: báo nhẹ, không crash


def test_delete_all_dialog_states_scope_and_no_undo():
    filtered_msg = borrowing.build_delete_all_message(5, True)
    assert "Xóa 5 phiếu" in filtered_msg
    assert "kết quả lọc hiện tại" in filtered_msg
    assert "Không thể hoàn tác" in filtered_msg
    assert "giữ nguyên" in filtered_msg
    unfiltered_msg = borrowing.build_delete_all_message(10, False)
    assert "Xóa 10 phiếu" in unfiltered_msg
    assert "đang không lọc" in unfiltered_msg


def test_borrowing_header_buttons_run_without_exception():
    at = _run()
    assert len(at.exception) == 0
    for key in ("borrow_sort_toggle", "borrow_select_page", "borrow_delete_filtered"):
        assert any(b.key == key for b in at.button), f"thiếu nút {key}"
    # 1. Toggle Mới nhất: đổi sort + về trang 1, không exception
    at.session_state["borrow_page"] = 2
    at.button(key="borrow_sort_toggle").click().run()
    assert len(at.exception) == 0
    assert at.session_state["borrow_page"] == 1
    assert at.session_state["borrow_newest_first"] is True
    # 2. Chọn tất cả trang này: bật cờ hỗ trợ, bulk bar dùng đúng dòng trang này
    at2 = _run()
    at2.button(key="borrow_select_page").click().run()
    assert len(at2.exception) == 0
    assert at2.session_state["borrow_select_all_page"] is True
    # 3. Xóa tất cả: mở dialog xác nhận nêu scope, không xóa ngay
    at3 = _run()
    at3.button(key="borrow_delete_filtered").click().run()
    assert len(at3.exception) == 0
    dialog = at3.session_state["dialog"] if "dialog" in at3.session_state else {}
    assert dialog.get("kind") == "delete_all"
    assert len(dialog.get("borrow_ids", [])) > 0
    with (Path(__file__).resolve().parent.parent / "data" / "borrow_records.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        before = sum(1 for row in csv.DictReader(handle) if (row.get("borrow_id") or "").strip())
    assert len(dialog["borrow_ids"]) <= before  # scope = kết quả lọc, không vượt tổng file
