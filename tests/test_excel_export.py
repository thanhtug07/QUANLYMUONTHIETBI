# -*- coding: utf-8 -*-
"""Kiểm thử xuất báo cáo Excel (utils/excel_export.py)."""
from io import BytesIO

import openpyxl

import main
from utils.excel_export import build_sheets, build_workbook


def test_workbook_has_all_sheets_and_real_counts():
    analysis = main.run_pipeline()
    stats = analysis["stats"]
    data = build_workbook(analysis)
    assert data[:2] == b"PK"  # .xlsx là file zip

    book = openpyxl.load_workbook(BytesIO(data))
    assert book.sheetnames == list(build_sheets(analysis).keys())
    assert book["Phiếu mượn"].max_row - 1 == len(stats["joined_records"])
    assert book["Thiết bị"].max_row - 1 == len(analysis["devices"])
    assert book["Quá hạn"].max_row - 1 == len(stats["overdue_days"])

    summary = {row[0]: row[1] for row in book["Tổng hợp"].iter_rows(min_row=2, values_only=True)}
    assert summary["Tổng lượt mượn"] == stats["total_borrows"]
    assert summary["Quá hạn"] == stats["overdue_count"]
    # Trạng thái được ghi bằng nhãn tiếng Việt, không phải mã nội bộ
    statuses = {row[10] for row in book["Phiếu mượn"].iter_rows(min_row=2, values_only=True)}
    assert "Đã trả" in statuses
    assert "returned" not in statuses


def test_sheets_handle_empty_analysis():
    sheets = build_sheets({"devices": [], "borrowers": [], "records": [], "errors": [], "stats": {}})
    assert all(frame.empty or name == "Tổng hợp" for name, frame in sheets.items())
    assert build_workbook({"stats": {}})[:2] == b"PK"
