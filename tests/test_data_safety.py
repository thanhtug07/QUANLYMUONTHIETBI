# -*- coding: utf-8 -*-
"""
tests/test_data_safety.py — CSV LỖI KHÔNG ĐƯỢC CRASH APP
========================================================
Bao phủ checklist mục VII của brief: file thiếu, file rỗng, sai encoding,
thiếu cột, trùng mã, ID không tồn tại, ngày sai format, trạng thái không
hợp lệ. Mọi case đều chạy trên tmp_path — không chạm data thật.
"""
from __future__ import annotations

from pathlib import Path

import cleaners
import data_store
import main
from cleaners import DEVICE_COLUMNS

DEV = "device_id,device_name,category,status\nTB001,Máy chiếu Epson,Máy chiếu,available\n"
BOR = "borrower_id,name,class_name,phone\nSV001,Nguyễn Văn An,CNTT-K47,0912345678\n"
REC = ("borrow_id,borrower_id,device_id,borrow_date,due_date,return_date,status\n"
       "PM001,SV001,TB001,01/06/2026,10/06/2026,09/06/2026,returned\n")


def _trio(tmp_path: Path, dev: str = DEV, bor: str = BOR, rec: str = REC):
    d, b, r = tmp_path / "d.csv", tmp_path / "b.csv", tmp_path / "r.csv"
    d.write_text(dev, encoding="utf-8")
    b.write_text(bor, encoding="utf-8")
    r.write_text(rec, encoding="utf-8")
    return d, b, r


def test_missing_files_no_crash(tmp_path):
    result = main.run_pipeline(tmp_path / "no1.csv", tmp_path / "no2.csv", tmp_path / "no3.csv")
    assert result["error"] == main.MSG_NO_DATA


def test_empty_files_no_crash(tmp_path):
    d, b, r = tmp_path / "d.csv", tmp_path / "b.csv", tmp_path / "r.csv"
    for p in (d, b, r):
        p.write_text("", encoding="utf-8")
    result = main.run_pipeline(d, b, r)
    assert result["error"] == main.MSG_NO_DATA


def test_bad_encoding_no_crash(tmp_path):
    d, b, r = _trio(tmp_path)
    d.write_bytes(b"device_id,device_name\nTB001,May chi\xe9u\n")
    assert cleaners.load_csv(d, DEVICE_COLUMNS) == []
    assert cleaners.missing_columns(d, DEVICE_COLUMNS) == []
    assert data_store.read_raw_rows(d, DEVICE_COLUMNS) == []
    assert data_store.count_rows(d) == 0
    assert data_store.file_columns(d) == []
    result = main.run_pipeline(d, b, r)
    # File lỗi coi như rỗng: phiếu còn lại vẫn phân tích, FK treo được ghi nhận.
    assert result["error"] is None
    assert any("không tồn tại" in str(e.get("error", "")) for e in result["errors"])


def test_missing_column_friendly_error(tmp_path):
    d, b, r = _trio(tmp_path, dev="device_id,device_name\nTB001,X\n")
    result = main.run_pipeline(d, b, r)
    assert result["error"] is not None and "devices.csv" in result["error"]


def test_duplicate_ids_reported_not_crashed(tmp_path):
    dup = ("borrow_id,borrower_id,device_id,borrow_date,due_date,return_date,status\n"
           "PM001,SV001,TB001,01/06/2026,10/06/2026,09/06/2026,returned\n"
           "PM001,SV001,TB001,02/06/2026,11/06/2026,10/06/2026,returned\n")
    d, b, r = _trio(tmp_path, rec=dup)
    result = main.run_pipeline(d, b, r)
    assert any("Trùng mã" in str(e.get("error", "")) for e in result["errors"])


def test_unknown_ids_reported_not_crashed(tmp_path):
    bad = ("borrow_id,borrower_id,device_id,borrow_date,due_date,return_date,status\n"
           "PM001,SV999,TB999,01/06/2026,10/06/2026,09/06/2026,returned\n")
    d, b, r = _trio(tmp_path, rec=bad)
    result = main.run_pipeline(d, b, r)
    assert any("không tồn tại" in str(e.get("error", "")) for e in result["errors"])


def test_bad_date_reported_not_crashed(tmp_path):
    bad = ("borrow_id,borrower_id,device_id,borrow_date,due_date,return_date,status\n"
           "PM001,SV001,TB001,abc,10/06/2026,,borrowing\n")
    d, b, r = _trio(tmp_path, rec=bad)
    result = main.run_pipeline(d, b, r)
    assert any("Invalid date" in str(e.get("error", "")) for e in result["errors"])


def test_invalid_status_reported_not_crashed(tmp_path):
    bad = ("borrow_id,borrower_id,device_id,borrow_date,due_date,return_date,status\n"
           "PM001,SV001,TB001,01/06/2026,10/06/2026,,hong\n")
    d, b, r = _trio(tmp_path, rec=bad)
    result = main.run_pipeline(d, b, r)
    assert result["error"] is None  # status suy diễn borrowing, app vẫn chạy
    assert any(e.get("field") == "status" for e in result["errors"])


def test_header_only_records_no_crash(tmp_path):
    hdr = "borrow_id,borrower_id,device_id,borrow_date,due_date,return_date,status\n"
    d, b, r = _trio(tmp_path, rec=hdr)
    result = main.run_pipeline(d, b, r)
    assert result["error"] == main.MSG_NO_VALID


def test_whitespace_only_file_friendly_error(tmp_path):
    d, b, r = _trio(tmp_path, rec="   \n  \n")
    result = main.run_pipeline(d, b, r)
    assert result["error"] is not None  # coi như sai cấu trúc, không crash


def test_malformed_quote_and_extra_column_no_crash(tmp_path):
    broken = (REC.splitlines()[0] + "\n"
              'PM001,SV001,TB001,"01/06/2026,10/06/2026,,borrowing\n')
    d, b, r = _trio(tmp_path, rec=broken)
    result = main.run_pipeline(d, b, r)
    assert "error" in result  # ngoặc kép chưa đóng: không crash, pipeline vẫn trả dict
    extra = (REC.splitlines()[0] + "\n"
             "PM001,SV001,TB001,01/06/2026,10/06/2026,09/06/2026,returned,EXTRA\n")
    d, b, r = _trio(tmp_path, rec=extra)
    result = main.run_pipeline(d, b, r)
    assert result["error"] is None and len(result["records"]) == 1
