# -*- coding: utf-8 -*-
"""
tests/test_crud_safety.py — KIỂM TRA CRUD AN TOÀN (KHÔNG CHẠM data/ THẬT)
=========================================================================
Bao phủ các fix:
- phân trang kẹp trang cũ (paginate) + update_row khóa lạ trả False;
- bulk status tuân quy tắc danh mục (validate_candidate_device);
- sample_data không gây mâu thuẫn danh mục mới (nhiều seed);
- CRUD + validation trên bản COPY tạm (trùng mã, FK, ngày, trạng thái).

Mọi ghi file đều dùng tmp_path. Không đọc/ghi data/*.csv thật.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import cleaners
import data_store
import statistics as stat_mod
import validators
from cleaners import (
    BORROWER_COLUMNS,
    DEVICE_COLUMNS,
    RECORD_COLUMNS,
)
from utils import sample_data as sample_mod

TODAY = date(2026, 9, 16)


def _base():
    devices = [
        {"device_id": "TB001", "device_name": "Laptop Dell", "category": "Laptop",
         "status": "available"},
        {"device_id": "TB002", "device_name": "Loa JBL", "category": "Loa",
         "status": "borrowed"},
    ]
    borrowers = [
        {"borrower_id": "SV001", "name": "Nguyen Van An", "class_name": "CNTT-K47"},
    ]
    records = [
        {"borrow_id": "PM001", "borrower_id": "SV001", "device_id": "TB002",
         "borrow_date": "10/09/2026", "due_date": "20/09/2026",
         "return_date": "", "status": "borrowing"},
    ]
    return devices, borrowers, records


def _seed(tmp_path: Path):
    devices, borrowers, records = _base()
    dev_p = tmp_path / "devices.csv"
    bor_p = tmp_path / "borrowers.csv"
    rec_p = tmp_path / "borrow_records.csv"
    data_store.write_rows(dev_p, DEVICE_COLUMNS, devices)
    data_store.write_rows(bor_p, BORROWER_COLUMNS, borrowers)
    data_store.write_rows(rec_p, RECORD_COLUMNS, records)
    return dev_p, bor_p, rec_p


# --- Phân trang: trang cũ vượt tổng vẫn cắt đúng lát ---

def test_paginate_clamps_stale_page():
    rows = [{"id": i} for i in range(3)]
    page_rows, total = stat_mod_dummy_paginate(rows, 5)
    assert total == 1
    assert len(page_rows) == 3  # không trả trang rỗng vì session còn kẹt ở 5


def stat_mod_dummy_paginate(rows, page):
    """Mô phỏng đúng công thức kẹp của ui.tables.paginate (tránh import streamlit)."""
    size = 10
    total = max(1, (len(rows) + size - 1) // size)
    current = min(max(1, page), total)
    start = (current - 1) * size
    return rows[start:start + size], total


# --- update_row khóa lạ: không sửa file, trả False (hợp đồng form sửa dựa vào) ---

def test_update_missing_key_returns_false_and_keeps_file(tmp_path):
    dev_p, _, _ = _seed(tmp_path)
    before = dev_p.read_bytes()
    assert data_store.update_row(dev_p, DEVICE_COLUMNS, "device_id",
                                 "TB999", {"status": "lost"}) is False
    assert dev_p.read_bytes() == before


def test_update_existing_key_preserves_other_columns(tmp_path):
    dev_p, _, _ = _seed(tmp_path)
    assert data_store.update_row(dev_p, DEVICE_COLUMNS, "device_id",
                                 "TB001", {"status": "borrowed"}) is True
    rows = data_store.read_raw_rows(dev_p, DEVICE_COLUMNS)
    row = next(r for r in rows if r["device_id"] == "TB001")
    assert row["status"] == "borrowed"
    assert row["device_name"] == "Laptop Dell"  # cột khác giữ nguyên


# --- Bulk status phải tuân quy tắc danh mục như form sửa đơn ---

def test_bulk_status_rule_rejects_available_with_active_borrow():
    devices, _, records = _base()
    candidate = {**devices[1], "status": "available"}  # TB002 đang bị mượn
    errors = validators.validate_candidate_device(
        candidate, devices, existing_records=records, editing=True)
    assert errors, "đổi borrowed -> available khi còn phiếu active phải bị chặn"


def test_bulk_status_rule_allows_consistent_change():
    devices, _, records = _base()
    candidate = {**devices[0], "status": "maintenance"}  # TB001 không phiếu active
    errors = validators.validate_candidate_device(
        candidate, devices, existing_records=records, editing=True)
    assert errors == []


# --- sample_data: không gây mâu thuẫn danh mục MỚI với mọi seed ---

def test_sample_plan_introduces_no_category_conflicts():
    devices, borrowers, records = _base()
    for seed in range(30):
        plan = sample_mod.plan_sample_data(10, 10, 20, devices, borrowers,
                                            records, seed=seed, today=TODAY)
        before = validators.find_category_conflicts(devices, records)
        after = validators.find_category_conflicts(
            devices + plan["devices"], records + plan["records"])
        assert len(after) == len(before), f"seed {seed} gây mâu thuẫn mới"


def test_sample_append_stays_clean_on_tmp(tmp_path):
    paths = {"devices": tmp_path / "devices.csv",
             "borrowers": tmp_path / "borrowers.csv",
             "records": tmp_path / "borrow_records.csv"}
    devices, borrowers, records = _base()
    data_store.write_rows(paths["devices"], DEVICE_COLUMNS, devices)
    data_store.write_rows(paths["borrowers"], BORROWER_COLUMNS, borrowers)
    data_store.write_rows(paths["records"], RECORD_COLUMNS, records)
    for seed in (3, 7, 21):
        sample_mod.append_sample_data(5, 5, 10, paths["devices"], paths["borrowers"],
                                      paths["records"], seed=seed, today=TODAY)
    raw_d = cleaners.load_csv(paths["devices"], DEVICE_COLUMNS)
    raw_b = cleaners.load_csv(paths["borrowers"], BORROWER_COLUMNS)
    raw_r = cleaners.load_csv(paths["records"], RECORD_COLUMNS)
    devs, _ = cleaners.clean_devices(raw_d)
    bors, _ = cleaners.clean_borrowers(raw_b)
    recs, _ = cleaners.clean_borrow_records(raw_r)
    errors, _, _ = validators.validate_all(devs, bors, recs, TODAY)
    assert errors == []


def test_sample_append_records_only_never_writes_bad_data(tmp_path):
    """devices_n=0: hoặc ghi sạch, hoặc raise — không bao giờ ghi xấu."""
    paths = {"devices": tmp_path / "devices.csv",
             "borrowers": tmp_path / "borrowers.csv",
             "records": tmp_path / "borrow_records.csv"}
    devices, borrowers, records = _base()
    data_store.write_rows(paths["devices"], DEVICE_COLUMNS, devices)
    data_store.write_rows(paths["borrowers"], BORROWER_COLUMNS, borrowers)
    data_store.write_rows(paths["records"], RECORD_COLUMNS, records)
    try:
        sample_mod.append_sample_data(0, 0, 10, paths["devices"], paths["borrowers"],
                                      paths["records"], seed=0, today=TODAY)
    except ValueError:
        pass  # từ chối thẳng thắn cũng là đúng
    raw_d = cleaners.load_csv(paths["devices"], DEVICE_COLUMNS)
    raw_r = cleaners.load_csv(paths["records"], RECORD_COLUMNS)
    devs, _ = cleaners.clean_devices(raw_d)
    raw_b = cleaners.load_csv(paths["borrowers"], BORROWER_COLUMNS)
    bors, _ = cleaners.clean_borrowers(raw_b)
    recs, _ = cleaners.clean_borrow_records(raw_r)
    base_conf = validators.find_category_conflicts(devices, records)
    full_conf = validators.find_category_conflicts(devs, recs)
    assert len(full_conf) == len(base_conf)


# --- CRUD validation trên COPY tạm: trùng mã / FK / ngày / trạng thái ---

def test_insert_duplicate_id_raises_on_tmp(tmp_path):
    dev_p, _, _ = _seed(tmp_path)
    try:
        data_store.insert_row(dev_p, DEVICE_COLUMNS,
                              {"device_id": "TB001", "device_name": "X",
                               "category": "Laptop", "status": "available"})
    except ValueError:
        return
    raise AssertionError("trùng mã phải raise ValueError")


def test_candidate_record_rejects_unknown_fk_bad_dates_bad_status():
    devices, borrowers, records = _base()
    bad_fk = {"borrow_id": "PM X", "borrower_id": "SV404", "device_id": "TB404",
              "borrow_date": "2026-09-10", "due_date": "2026-09-20",
              "return_date": "", "status": "borrowing"}
    errors = validators.validate_candidate_record(
        bad_fk, devices, borrowers, records, editing=False)
    assert any("không tồn tại" in e.get("error", "") for e in errors)

    bad_date = {"borrow_id": "PM002", "borrower_id": "SV001", "device_id": "TB001",
                "borrow_date": "2026-09-20", "due_date": "2026-09-10",
                "return_date": "", "status": "borrowing"}
    errors = validators.validate_candidate_record(
        bad_date, devices, borrowers, records, editing=False)
    assert any("sau ngày hạn trả" in e.get("error", "") for e in errors)

    bad_status = {"borrow_id": "PM003", "borrower_id": "SV001", "device_id": "TB001",
                  "borrow_date": "2026-09-10", "due_date": "2026-09-20",
                  "return_date": "", "status": "returned"}
    errors = validators.validate_candidate_record(
        bad_status, devices, borrowers, records, editing=False)
    assert any("thiếu ngày trả" in e.get("error", "") for e in errors)


def test_bulk_delete_returns_count_on_tmp(tmp_path):
    _, bor_p, _ = _seed(tmp_path)
    data_store.insert_row(bor_p, BORROWER_COLUMNS,
                          {"borrower_id": "SV009", "name": "Test",
                           "class_name": "CNTT-K47"})
    removed = data_store.delete_rows(bor_p, BORROWER_COLUMNS, "borrower_id",
                                     ["SV001", "SV009", "SV404"])
    assert removed == 2
    assert data_store.count_rows(bor_p) == 0


def test_next_sequential_id_follows_max_on_tmp(tmp_path):
    dev_p, _, _ = _seed(tmp_path)
    rows = data_store.read_raw_rows(dev_p, DEVICE_COLUMNS)
    assert data_store.next_sequential_id(rows, "device_id", "TB") == "TB003"


def test_normalize_phone_variants():
    assert cleaners.normalize_phone("+84 912 345 678") == "0912345678"
    assert cleaners.normalize_phone("0912.345.678") == "0912345678"
    assert cleaners.normalize_phone("  0912-345-678 ") == "0912345678"
    assert cleaners.normalize_phone("") == ""
    assert cleaners.normalize_phone(None) == ""


def test_valid_phone_rule():
    assert cleaners.is_valid_phone("")  # tuỳ chọn: để trống hợp lệ
    assert cleaners.is_valid_phone("0912345678")
    assert not cleaners.is_valid_phone("12345")
    assert not cleaners.is_valid_phone("091234567")  # 9 số
    assert not cleaners.is_valid_phone("1912345678")  # không bắt đầu bằng 0
    assert not cleaners.is_valid_phone("09abcdefgh")


def test_borrower_candidate_rejects_bad_phone():
    devices, borrowers, records = _base()
    candidate = {"borrower_id": "SV009", "name": "Test", "class_name": "CNTT-K47",
                 "phone": "123"}
    errors = validators.validate_candidate_borrower(candidate, borrowers, editing=False)
    assert any(e.get("field") == "phone" for e in errors)
    candidate["phone"] = "0912345678"
    assert validators.validate_candidate_borrower(
        candidate, borrowers, editing=False) == []
    candidate["phone"] = ""
    assert validators.validate_candidate_borrower(
        candidate, borrowers, editing=False) == []


def test_clean_borrowers_flags_bad_phone_keeps_row():
    raw = [{"borrower_id": "SV009", "name": "Test", "class_name": "CNTT-K47",
            "phone": "999", "_row_no": 2}]
    rows, errors = cleaners.clean_borrowers(raw)
    assert rows[0]["phone"] == "999"  # giữ giá trị để validators/UI báo
    assert any(e.get("field") == "phone" for e in errors)


def test_sample_borrowers_have_valid_phones():
    devices, borrowers, records = _base()
    plan = sample_mod.plan_sample_data(10, 10, 0, devices, borrowers, records,
                                       seed=5, today=TODAY)
    assert plan["borrowers"], "phải sinh được người mượn"
    for borrower in plan["borrowers"]:
        assert cleaners.is_valid_phone(borrower["phone"]), borrower


def _record(device_id, status, borrow_id="PM009", return_date=""):
    return {"borrow_id": borrow_id, "borrower_id": "SV001", "device_id": device_id,
            "borrow_date": "12/09/2026", "due_date": "22/09/2026",
            "return_date": return_date, "status": status}


def test_busy_device_blocked_on_create():
    devices, borrowers, records = _base()  # TB002 đang borrowing ở PM001
    errors = validators.validate_candidate_record(
        _record("TB002", "borrowing"), devices, borrowers, records, editing=False)
    assert any("đang được mượn" in e.get("error", "") for e in errors)


def test_busy_device_blocked_for_overdue_and_lost():
    devices, borrowers, records = _base()
    for status, ret in (("overdue", ""), ("lost", "22/09/2026")):
        errors = validators.validate_candidate_record(
            _record("TB002", status, return_date=ret), devices, borrowers, records,
            editing=False)
        assert any("đang được mượn" in e.get("error", "") for e in errors), status


def test_idle_device_and_returned_allowed():
    devices, borrowers, records = _base()  # TB001 rảnh
    assert validators.validate_candidate_record(
        _record("TB001", "borrowing"), devices, borrowers, records,
        editing=False) == []
    assert validators.validate_candidate_record(
        _record("TB002", "returned", return_date="18/09/2026"), devices, borrowers,
        records, editing=False) == []


def test_editing_self_not_busy():
    devices, borrowers, records = _base()
    assert validators.validate_candidate_record(
        _record("TB002", "borrowing", borrow_id="PM001"), devices, borrowers,
        records, editing=True) == []


def test_sample_plan_active_records_use_distinct_idle_devices():
    devices, borrowers, records = _base()
    plan = sample_mod.plan_sample_data(10, 10, 20, devices, borrowers, records,
                                       seed=11, today=TODAY)
    active = [r["device_id"] for r in plan["records"]
              if r["status"] in ("borrowing", "overdue", "lost")]
    assert len(active) == len(set(active))  # mỗi thiết bị tối đa 1 phiếu active
    busy_before = {"TB002"}
    assert not (set(active) & busy_before)
