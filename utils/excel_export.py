# -*- coding: utf-8 -*-
"""
utils/excel_export.py — XUẤT BÁO CÁO EXCEL (.xlsx)
==================================================
Dựng workbook nhiều sheet từ kết quả pipeline (`main.run_pipeline`):

    Tổng hợp · Phiếu mượn · Thiết bị · Người mượn · Quá hạn · Theo loại · Xếp hạng

Chỉ dùng số liệu ĐÃ TÍNH trong `analysis["stats"]` / dữ liệu đã làm sạch —
không tính lại thống kê (tránh lệch số với dashboard và report.txt).
Hàm thuần, trả về bytes để `st.download_button` dùng trực tiếp và test được.
"""
from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List, Sequence, Tuple

import pandas as pd

from utils.helpers import format_date, status_label

#: Màu tiêu đề cột (primary của palette sáng) — file Excel luôn nền trắng.
HEADER_FILL = "0054A3"
HEADER_FONT = "FFFFFF"


def _frame(rows: Sequence[Dict[str, Any]], columns: Sequence[Tuple[str, str]]) -> pd.DataFrame:
    """DataFrame với cột (khoá nguồn -> tiêu đề tiếng Việt), bỏ field nội bộ."""
    data = [{title: row.get(key, "") for key, title in columns} for row in rows]
    return pd.DataFrame(data, columns=[title for _, title in columns])


def _summary_rows(analysis: Dict[str, Any]) -> List[Tuple[str, Any]]:
    stats = analysis.get("stats") or {}
    today = analysis.get("today")
    return [
        ("Ngày tham chiếu", format_date(today) if today else ""),
        ("Tổng thiết bị", stats.get("total_devices", len(analysis.get("devices", [])))),
        ("Tổng người mượn", stats.get("total_borrowers", len(analysis.get("borrowers", [])))),
        ("Tổng lượt mượn", stats.get("total_borrows", 0)),
        ("Đang mượn", stats.get("currently_borrowed", 0)),
        ("Đã trả", stats.get("returned_count", 0)),
        ("Quá hạn", stats.get("overdue_count", 0)),
        ("Quá hạn lâu nhất (ngày)", stats.get("overdue_max_days", 0)),
        ("Quá hạn trung bình (ngày)", stats.get("overdue_avg_days", 0)),
        ("Thất thoát", stats.get("lost_count", 0)),
        ("Tỷ lệ trả đúng hạn (%)", stats.get("on_time_rate", 0)),
        ("Tỷ lệ sử dụng thiết bị (%)", stats.get("utilization_rate", 0)),
        ("Bản ghi dữ liệu lỗi", len(analysis.get("errors", []))),
    ]


def build_sheets(analysis: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    """Các sheet của báo cáo (tên sheet -> DataFrame), theo thứ tự hiển thị."""
    stats = analysis.get("stats") or {}
    devices_by_id = stats.get("devices_by_id") or {}
    borrowers_by_id = stats.get("borrowers_by_id") or {}

    joined = [
        {
            **row,
            "borrow_date": format_date(row.get("borrow_date")),
            "due_date": format_date(row.get("due_date")),
            "return_date": format_date(row.get("return_date")) if row.get("return_date") else "",
            "status": status_label(row.get("status", "")),
        }
        for row in stats.get("joined_records", analysis.get("records", []))
    ]
    overdue = [
        {
            **row,
            "device_name": devices_by_id.get(str(row.get("device_id", "")), {}).get("device_name", ""),
            "name": borrowers_by_id.get(str(row.get("borrower_id", "")), {}).get("name", ""),
            "phone": borrowers_by_id.get(str(row.get("borrower_id", "")), {}).get("phone", ""),
            "due_date": format_date(row.get("due_date")),
        }
        for row in stats.get("overdue_days", [])
    ]
    devices = [{**d, "status": status_label(d.get("status", ""))} for d in analysis.get("devices", [])]

    top_devices = [
        {
            "rank": index,
            "device_id": device_id,
            "device_name": devices_by_id.get(str(device_id), {}).get("device_name", ""),
            "count": count,
        }
        for index, (device_id, count) in enumerate(stats.get("top_devices", []), start=1)
    ]
    top_borrowers = [
        {
            "rank": index,
            "borrower_id": borrower_id,
            "name": borrowers_by_id.get(str(borrower_id), {}).get("name", ""),
            "count": count,
        }
        for index, (borrower_id, count) in enumerate(stats.get("top_borrowers", []), start=1)
    ]

    return {
        "Tổng hợp": pd.DataFrame(_summary_rows(analysis), columns=["Chỉ số", "Giá trị"]),
        "Phiếu mượn": _frame(
            joined,
            [
                ("borrow_id", "Mã phiếu"), ("device_id", "Mã thiết bị"), ("device_name", "Tên thiết bị"),
                ("category", "Loại thiết bị"), ("borrower_id", "Mã người mượn"), ("name", "Người mượn"),
                ("class_name", "Lớp"), ("borrow_date", "Ngày mượn"), ("due_date", "Hạn trả"),
                ("return_date", "Ngày trả"), ("status", "Trạng thái"),
            ],
        ),
        "Thiết bị": _frame(
            devices,
            [("device_id", "Mã thiết bị"), ("device_name", "Tên thiết bị"), ("category", "Loại thiết bị"), ("status", "Trạng thái")],
        ),
        "Người mượn": _frame(
            analysis.get("borrowers", []),
            [("borrower_id", "Mã người mượn"), ("name", "Họ tên"), ("class_name", "Lớp"), ("phone", "Số điện thoại")],
        ),
        "Quá hạn": _frame(
            overdue,
            [
                ("borrow_id", "Mã phiếu"), ("device_id", "Mã thiết bị"), ("device_name", "Tên thiết bị"),
                ("borrower_id", "Mã người mượn"), ("name", "Người mượn"), ("phone", "Số điện thoại"),
                ("due_date", "Hạn trả"), ("days_overdue", "Số ngày quá hạn"),
            ],
        ),
        "Theo loại": pd.DataFrame(stats.get("borrows_by_category", []), columns=["Loại thiết bị", "Số lượt mượn"]),
        "Top thiết bị": _frame(
            top_devices,
            [("rank", "Hạng"), ("device_id", "Mã thiết bị"), ("device_name", "Tên thiết bị"), ("count", "Số lượt")],
        ),
        "Top người mượn": _frame(
            top_borrowers,
            [("rank", "Hạng"), ("borrower_id", "Mã người mượn"), ("name", "Họ tên"), ("count", "Số lượt")],
        ),
    }


def build_workbook(analysis: Dict[str, Any]) -> bytes:
    """Workbook .xlsx (bytes): tiêu đề cột tô màu, cố định hàng đầu, độ rộng cột vừa nội dung."""
    from openpyxl.styles import Alignment, Font, PatternFill

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, frame in build_sheets(analysis).items():
            frame.to_excel(writer, sheet_name=name, index=False)
            sheet = writer.sheets[name]
            sheet.freeze_panes = "A2"
            for cell in sheet[1]:
                cell.font = Font(bold=True, color=HEADER_FONT)
                cell.fill = PatternFill("solid", fgColor=HEADER_FILL)
                cell.alignment = Alignment(vertical="center")
            for column_cells in sheet.columns:
                width = max(len(str(cell.value or "")) for cell in column_cells)
                sheet.column_dimensions[column_cells[0].column_letter].width = min(max(width + 2, 10), 48)
            if frame.shape[0]:
                sheet.auto_filter.ref = sheet.dimensions
    return buffer.getvalue()
