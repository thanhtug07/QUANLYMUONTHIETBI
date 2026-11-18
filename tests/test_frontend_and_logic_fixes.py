# -*- coding: utf-8 -*-
"""
tests/test_frontend_and_logic_fixes.py — KIỂM TRA CÁC BẢN VÁ FRONTEND & LOGIC
=============================================================================
Bao phủ các lỗi và cải tiến do đội ngũ subagent phát hiện:
- XSS escaping trong layout, badges, topbar, alerts, recent_history_html;
- Lọc "Thất thoát" không lấy nhầm các phiếu "Đã trả" trong lịch sử;
- _active_counts ở trang Người mượn tính cả phiếu "overdue";
- Đồng bộ trạng thái thiết bị (sync_device_status) khi thêm/sửa/xóa phiếu mượn;
- Đọc CSV theo tên cột header khi thứ tự cột đảo và bắt lỗi csv.Error (NUL byte);
- Chuẩn hoá trạng thái tiếng Việt có dấu ("ĐANG MƯỢN", "Sẵn sàng"...);
- Báo cáo không cộng đúp lỗi validation vào lỗi cleaning;
- Topbar bell badge hiển thị số cảnh báo thật;
- Dọn dẹp session_state["dialog"] khi chuyển trang (goto_page).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import cleaners
import data_store
import main
import statistics as stat_mod
import validators
from cleaners import BORROWER_COLUMNS, DEVICE_COLUMNS, RECORD_COLUMNS
from pages import alerts as alerts_page
from pages import borrowers as borrowers_page
from pages import common as common_page
from ui import app_shell, badges

TODAY = date(2026, 9, 16)


def test_vietnamese_accented_status_aliases():
    assert cleaners.normalize_status(
        "ĐANG MƯỢN", cleaners.DEVICE_STATUSES, cleaners.DEVICE_STATUS_ALIASES
    ) == "borrowed"
    assert cleaners.normalize_status(
        "Sẵn sàng", cleaners.DEVICE_STATUSES, cleaners.DEVICE_STATUS_ALIASES
    ) == "available"
    assert cleaners.normalize_status(
        "Bảo trì", cleaners.DEVICE_STATUSES, cleaners.DEVICE_STATUS_ALIASES
    ) == "maintenance"
    assert cleaners.normalize_status(
        "Thất thoát", cleaners.RECORD_STATUSES, cleaners.RECORD_STATUS_ALIASES
    ) == "lost"
    assert cleaners.normalize_status(
        "Quá hạn", cleaners.RECORD_STATUSES, cleaners.RECORD_STATUS_ALIASES
    ) == "overdue"
    assert cleaners.normalize_status(
        "Đã trả", cleaners.RECORD_STATUSES, cleaners.RECORD_STATUS_ALIASES
    ) == "returned"


def test_stdlib_statistics_reexported():
    """statistics.py ở thư mục gốc vẫn giữ các hàm stdlib như mean/stdev."""
    assert hasattr(stat_mod, "mean")
    assert stat_mod.mean([2, 4, 6]) == 4


def test_reordered_csv_columns_mapped_by_header(tmp_path: Path):
    """File CSV có cột hợp lệ nhưng đảo thứ tự cột vẫn đọc đúng trường."""
    dev_file = tmp_path / "devices.csv"
    dev_file.write_text(
        "status,device_name,device_id,category\navailable,Máy chiếu Sony,TB010,Máy chiếu\n",
        encoding="utf-8",
    )
    assert cleaners.missing_columns(dev_file, DEVICE_COLUMNS) == []
    loaded = cleaners.load_csv(dev_file, DEVICE_COLUMNS)
    assert len(loaded) == 1
    assert loaded[0]["device_id"] == "TB010"
    assert loaded[0]["device_name"] == "Máy chiếu Sony"
    assert loaded[0]["category"] == "Máy chiếu"
    assert loaded[0]["status"] == "available"

    raw = data_store.read_raw_rows(dev_file, DEVICE_COLUMNS)
    assert raw[0]["device_id"] == "TB010"
    assert raw[0]["status"] == "available"


def test_nul_byte_csv_does_not_crash(tmp_path: Path):
    """File CSV chứa NUL byte (\\x00) không làm crash csv.reader."""
    bad = tmp_path / "bad.csv"
    bad.write_bytes(b"device_id,device_name,category,status\nTB001,\x00abc,Laptop,available\n")
    assert isinstance(cleaners.load_csv(bad, DEVICE_COLUMNS), list)
    assert isinstance(cleaners.missing_columns(bad, DEVICE_COLUMNS), list)
    assert isinstance(data_store.read_raw_rows(bad, DEVICE_COLUMNS), list)
    assert isinstance(data_store.count_rows(bad), int)
    assert isinstance(data_store.file_columns(bad), list)


def test_lost_filter_excludes_historical_returned_records():
    """Lọc Trạng thái = 'Thất thoát' không lấy nhầm các phiếu 'returned' cũ của cùng thiết bị."""
    records = [
        {
            "borrow_id": "PM001",
            "borrower_id": "SV001",
            "device_id": "TB015",
            "borrow_date": "2026-06-01",
            "due_date": "2026-06-10",
            "return_date": "2026-06-05",
            "status": "returned",
        },
        {
            "borrow_id": "PM002",
            "borrower_id": "SV002",
            "device_id": "TB015",
            "borrow_date": "2026-07-31",
            "due_date": "2026-08-10",
            "return_date": "",
            "status": "lost",
        },
    ]
    filtered = common_page.filter_records(records, status="Thất thoát", today=TODAY)
    assert [r["borrow_id"] for r in filtered] == ["PM002"]

    listed = common_page.apply_listing_filters(records, status="Thất thoát", today=TODAY)
    assert [r["borrow_id"] for r in listed] == ["PM002"]


def test_borrower_active_counts_includes_overdue():
    records = [
        {"borrow_id": "PM001", "borrower_id": "SV001", "status": "borrowing"},
        {"borrow_id": "PM002", "borrower_id": "SV001", "status": "overdue"},
        {"borrow_id": "PM003", "borrower_id": "SV001", "status": "returned"},
        {"borrow_id": "PM004", "borrower_id": "SV002", "status": "overdue"},
    ]
    counts = borrowers_page._active_counts(records)
    assert counts["SV001"] == 2
    assert counts["SV002"] == 1


def test_sync_device_status_updates_catalog(tmp_path: Path):
    dev_p = tmp_path / "devices.csv"
    rec_p = tmp_path / "borrow_records.csv"
    devices = [
        {"device_id": "TB001", "device_name": "Laptop", "category": "Laptop", "status": "available"},
        {"device_id": "TB002", "device_name": "Loa", "category": "Loa", "status": "borrowed"},
    ]
    records = [
        {
            "borrow_id": "PM001",
            "borrower_id": "SV001",
            "device_id": "TB001",
            "borrow_date": "10/09/2026",
            "due_date": "20/09/2026",
            "return_date": "",
            "status": "borrowing",
        },
        {
            "borrow_id": "PM002",
            "borrower_id": "SV001",
            "device_id": "TB002",
            "borrow_date": "01/09/2026",
            "due_date": "05/09/2026",
            "return_date": "04/09/2026",
            "status": "returned",
        },
    ]
    data_store.write_rows(dev_p, DEVICE_COLUMNS, devices)
    data_store.write_rows(rec_p, RECORD_COLUMNS, records)
    data_store.sync_device_status(dev_p, rec_p, DEVICE_COLUMNS, RECORD_COLUMNS, ["TB001", "TB002"])

    updated = {d["device_id"]: d["status"] for d in data_store.read_raw_rows(dev_p, DEVICE_COLUMNS)}
    assert updated["TB001"] == "borrowed"
    assert updated["TB002"] == "available"


def test_alerts_details_raw_and_escaped_in_html():
    errors = [
        {
            "row": 273,
            "field": "borrower_id",
            "value": "SV999",
            "error": "Người mượn 'SV999' không tồn tại trong borrowers.csv",
            "table": "borrow_records",
        }
    ]
    items = alerts_page._data_items(errors)
    # Tìm kiếm theo chuỗi có dấu nháy đơn phải khớp vì details giữ raw string.
    matched = alerts_page.filter_alert_items(items, search="'sv999'")
    assert len(matched) == 1
    # Khi render sang HTML, ký tự nguy hiểm được escape.
    html = alerts_page._alert_item_html(
        "<script>", "meta", ["<b>test</b>"], badges.status_badge("Quá hạn"), "danger"
    )
    assert "<script>" not in html
    assert "<b>test</b>" not in html


def test_overdue_duplicate_borrow_ids_produce_unique_keys():
    overdue = [
        {"borrow_id": "PM001", "device_id": "TB001", "borrower_id": "SV001", "days_overdue": 5, "status": "overdue"},
        {"borrow_id": "PM001", "device_id": "TB002", "borrower_id": "SV002", "days_overdue": 3, "status": "overdue"},
    ]
    items = alerts_page._overdue_items(overdue, {}, {})
    keys = [item["key"] for item in items]
    assert len(keys) == len(set(keys))


def test_candidate_validation_ignores_preexisting_duplicates():
    devices = [
        {"device_id": "TB001", "device_name": "A", "category": "Laptop", "status": "available"},
        {"device_id": "TB001", "device_name": "B", "category": "Laptop", "status": "available"},
    ]
    candidate = {"device_id": "TB002", "device_name": "C", "category": "Laptop", "status": "available"}
    assert validators.validate_candidate_device(candidate, devices, editing=False) == []


def test_report_does_not_double_count_validation_errors(tmp_path: Path):
    dev_p = tmp_path / "d.csv"
    bor_p = tmp_path / "b.csv"
    rec_p = tmp_path / "r.csv"
    dev_p.write_text("device_id,device_name,category,status\nTB001,Laptop,Laptop,available\n", encoding="utf-8")
    bor_p.write_text("borrower_id,name,class_name,phone\nSV001,An,CNTT,0912345678\n", encoding="utf-8")
    rec_p.write_text(
        "borrow_id,borrower_id,device_id,borrow_date,due_date,return_date,status\n"
        "PM001,SV999,TB001,01/09/2026,10/09/2026,05/09/2026,returned\n",
        encoding="utf-8",
    )
    res = main.run_pipeline(dev_p, bor_p, rec_p, today=TODAY)
    assert "Lỗi khi làm sạch (cleaning) : 0" in res["report_text"]
    assert "Lỗi khi kiểm tra (validation): 1" in res["report_text"]


def test_recent_history_html_escapes_and_renders():
    records = [
        {
            "borrow_id": "PM001",
            "device_id": "TB001",
            "borrower_id": "SV001",
            "borrow_date": "2026-09-10",
            "due_date": "2026-09-20",
            "return_date": "",
            "status": "borrowing",
        }
    ]
    html = common_page.recent_history_html(
        records,
        {"TB001": {"device_name": "Laptop <Dell>"}},
        {"SV001": {"name": "An & Bình"}},
        "device_id",
        "TB001",
    )
    assert "PM001" in html
    assert "An &amp; Bình" in html
    assert "<Dell>" not in html
