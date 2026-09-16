# -*- coding: utf-8 -*-
"""
tests/test_sample_data.py — KIỂM TRA CHỨC NĂNG DỮ LIỆU MẪU
=========================================================
Bao phủ: sinh dữ liệu hợp lệ, không trùng ID, FK hợp lệ, ngày/trạng thái
đúng luật, ghi nối giữ nguyên dòng cũ, cập nhật đúng số dòng, backup/restore,
và luồng end-to-end qua cleaners + validators + statistics.
"""
from __future__ import annotations

import random
import shutil
from datetime import date
from pathlib import Path
from typing import Dict, List

import cleaners
import data_store
import statistics as stat_mod
import validators
from cleaners import (
    BORROWER_COLUMNS,
    DEVICE_COLUMNS,
    DEVICE_STATUSES,
    RECORD_COLUMNS,
    RECORD_STATUSES,
)
from utils import sample_data as sample_mod

TODAY = date(2026, 9, 16)
SEED = 7


def _existing() -> Dict[str, List[Dict[str, str]]]:
    devices = [
        {"device_id": "TB001", "device_name": "Laptop Dell", "category": "Laptop",
         "status": "available"},
        {"device_id": "TB002", "device_name": "Loa JBL", "category": "Loa",
         "status": "available"},
    ]
    borrowers = [
        {"borrower_id": "SV001", "name": "Nguyen Van An", "class_name": "CNTT-K47"},
        {"borrower_id": "SV002", "name": "Tran Thi Binh", "class_name": "KHMT-K45"},
    ]
    records = [
        {"borrow_id": "PM001", "borrower_id": "SV001", "device_id": "TB001",
         "borrow_date": "01/06/2026", "due_date": "10/06/2026",
         "return_date": "09/06/2026", "status": "returned"},
    ]
    return {"devices": devices, "borrowers": borrowers, "records": records}


def _seed_csvs(tmp_path: Path) -> Dict[str, Path]:
    base = _existing()
    paths = {"devices": tmp_path / "devices.csv",
             "borrowers": tmp_path / "borrowers.csv",
             "records": tmp_path / "borrow_records.csv"}
    data_store.write_rows(paths["devices"], DEVICE_COLUMNS, base["devices"])
    data_store.write_rows(paths["borrowers"], BORROWER_COLUMNS, base["borrowers"])
    data_store.write_rows(paths["records"], RECORD_COLUMNS, base["records"])
    return paths


# --- Sinh thiết bị ---

def test_generate_sample_devices():
    rows = sample_mod.generate_sample_devices(10, _existing()["devices"], random.Random(SEED))
    assert len(rows) == 10
    for row in rows:
        assert set(row) == set(DEVICE_COLUMNS)
        assert row["device_id"] and row["device_name"] and row["category"]
        assert row["status"] in DEVICE_STATUSES


def test_generate_sample_borrowers():
    rows = sample_mod.generate_sample_borrowers(10, _existing()["borrowers"], random.Random(SEED))
    assert len(rows) == 10
    for row in rows:
        assert set(row) == set(BORROWER_COLUMNS)
        assert row["borrower_id"] and row["name"] and row["class_name"]


def test_generate_sample_borrow_records():
    rows = sample_mod.generate_sample_records(
        20, ["TB001", "TB002"], ["SV001", "SV002"],
        _existing()["records"], TODAY, random.Random(SEED))
    assert len(rows) == 20
    statuses = {row["status"] for row in rows}
    assert {"returned", "borrowing", "overdue", "lost"} <= statuses  # đủ variation demo
    for row in rows:
        assert set(row) == set(RECORD_COLUMNS)
        assert row["status"] in RECORD_STATUSES


# --- Không trùng ID ---

def test_no_duplicate_device_ids():
    old = _existing()["devices"]
    new = sample_mod.generate_sample_devices(10, old, random.Random(SEED))
    ids = [d["device_id"] for d in old + new]
    assert len(set(ids)) == len(ids)
    assert min(d["device_id"] for d in new) > max(d["device_id"] for d in old)


def test_no_duplicate_borrower_ids():
    old = _existing()["borrowers"]
    new = sample_mod.generate_sample_borrowers(10, old, random.Random(SEED))
    ids = [b["borrower_id"] for b in old + new]
    assert len(set(ids)) == len(ids)


def test_no_duplicate_borrow_ids():
    old = _existing()["records"]
    new = sample_mod.generate_sample_records(
        20, ["TB001"], ["SV001"], old, TODAY, random.Random(SEED))
    ids = [r["borrow_id"] for r in old + new]
    assert len(set(ids)) == len(ids)


# --- FK / ngày / trạng thái ---

def test_borrow_record_references_existing_device():
    plan = sample_mod.plan_sample_data(5, 5, 10, _existing()["devices"],
                                       _existing()["borrowers"], _existing()["records"],
                                       seed=SEED, today=TODAY)
    valid = {d["device_id"] for d in _existing()["devices"]} | {d["device_id"] for d in plan["devices"]}
    assert all(r["device_id"] in valid for r in plan["records"])


def test_borrow_record_references_existing_borrower():
    plan = sample_mod.plan_sample_data(5, 5, 10, _existing()["devices"],
                                       _existing()["borrowers"], _existing()["records"],
                                       seed=SEED, today=TODAY)
    valid = {b["borrower_id"] for b in _existing()["borrowers"]} | {b["borrower_id"] for b in plan["borrowers"]}
    assert all(r["borrower_id"] in valid for r in plan["records"])


def test_generated_dates_are_valid():
    plan = sample_mod.plan_sample_data(5, 5, 20, _existing()["devices"],
                                       _existing()["borrowers"], _existing()["records"],
                                       seed=SEED, today=TODAY)
    for row in plan["records"]:
        borrow = cleaners.parse_date(row["borrow_date"])
        due = cleaners.parse_date(row["due_date"])
        assert borrow is not None and due is not None
        assert borrow <= due
        if row["status"] in ("returned", "lost"):
            assert cleaners.parse_date(row["return_date"]) is not None
        else:
            assert not row["return_date"].strip()


def test_generated_statuses_are_valid():
    plan = sample_mod.plan_sample_data(5, 5, 20, _existing()["devices"],
                                       _existing()["borrowers"], _existing()["records"],
                                       seed=SEED, today=TODAY)
    assert all(d["status"] in DEVICE_STATUSES for d in plan["devices"])
    assert all(r["status"] in RECORD_STATUSES for r in plan["records"])


def test_generated_batch_passes_validators():
    base = _existing()
    plan = sample_mod.plan_sample_data(10, 10, 20, base["devices"], base["borrowers"],
                                       base["records"], seed=SEED, today=TODAY)
    all_devices = base["devices"] + plan["devices"]
    all_borrowers = base["borrowers"] + plan["borrowers"]
    all_records = base["records"] + plan["records"]
    errors = []
    for device in plan["devices"]:
        rest = [d for d in all_devices if d is not device]
        errors += validators.validate_candidate_device(device, rest, None, False)
    for borrower in plan["borrowers"]:
        rest = [b for b in all_borrowers if b is not borrower]
        errors += validators.validate_candidate_borrower(borrower, rest, False)
    for record in plan["records"]:
        rest = [r for r in all_records if r is not record]
        errors += validators.validate_candidate_record(
            record, all_devices, all_borrowers, rest, False)
    errors += validators.find_category_conflicts(plan["devices"], all_records)
    assert errors == []


# --- Ghi nối / số dòng / backup ---

def test_add_sample_data_preserves_existing_rows(tmp_path):
    paths = _seed_csvs(tmp_path)
    before = {key: paths[key].read_bytes() for key in paths}
    sample_mod.append_sample_data(5, 5, 10, paths["devices"], paths["borrowers"],
                                  paths["records"], seed=SEED, today=TODAY)
    for key in paths:  # dòng cũ giữ nguyên thứ tự + nội dung (prefix byte)
        assert paths[key].read_bytes().startswith(before[key])


def test_add_sample_data_updates_row_count(tmp_path):
    paths = _seed_csvs(tmp_path)
    added = sample_mod.append_sample_data(5, 5, 10, paths["devices"], paths["borrowers"],
                                          paths["records"], seed=SEED, today=TODAY)
    assert added == {"devices": 5, "borrowers": 5, "records": 10}
    assert data_store.count_rows(paths["devices"]) == 2 + 5
    assert data_store.count_rows(paths["borrowers"]) == 2 + 5
    assert data_store.count_rows(paths["records"]) == 1 + 10


def test_add_sample_data_rejects_empty_selection(tmp_path):
    paths = _seed_csvs(tmp_path)
    try:
        sample_mod.append_sample_data(0, 0, 0, paths["devices"], paths["borrowers"],
                                      paths["records"], seed=SEED, today=TODAY)
    except ValueError:
        return
    raise AssertionError("Phải raise ValueError khi không chọn loại nào.")


def test_backup_and_restore_roundtrip(tmp_path):
    paths = _seed_csvs(tmp_path)
    before = {key: paths[key].read_bytes() for key in paths}
    assert not sample_mod.has_backup(tmp_path)
    sample_mod.append_sample_data(5, 5, 10, paths["devices"], paths["borrowers"],
                                  paths["records"], seed=SEED, today=TODAY)
    assert sample_mod.has_backup(tmp_path)
    counts = sample_mod.restore_sample_backup(paths["devices"], paths["borrowers"], paths["records"])
    assert counts == {"devices": 2, "borrowers": 2, "records": 1}
    for key in paths:
        assert paths[key].read_bytes() == before[key]


def test_app_csv_sample_data_flow(tmp_path):
    """Luồng end-to-end: ghi nối -> cleaners -> validators -> statistics."""
    paths = _seed_csvs(tmp_path)
    sample_mod.append_sample_data(10, 10, 20, paths["devices"], paths["borrowers"],
                                  paths["records"], seed=SEED, today=TODAY)
    raw_d = cleaners.load_csv(paths["devices"], DEVICE_COLUMNS)
    raw_b = cleaners.load_csv(paths["borrowers"], BORROWER_COLUMNS)
    raw_r = cleaners.load_csv(paths["records"], RECORD_COLUMNS)
    devices, _ = cleaners.clean_devices(raw_d)
    borrowers, _ = cleaners.clean_borrowers(raw_b)
    records, _ = cleaners.clean_borrow_records(raw_r)
    errors, overdue, lost = validators.validate_all(devices, borrowers, records, TODAY)
    assert errors == []
    stats = stat_mod.compute_all(devices, borrowers, records,
                                 overdue_records=overdue, lost_devices=lost, today=TODAY)
    assert stats["total_devices"] == 12
    assert stats["total_borrowers"] == 12
    assert stats["total_borrows"] == 21
    assert stats["currently_borrowed"] > 0 and stats["overdue_count"] > 0
