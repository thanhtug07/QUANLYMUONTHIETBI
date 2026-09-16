# -*- coding: utf-8 -*-
"""
pages/common.py — HELPER DÙNG CHUNG CHO CÁC PAGE
===============================================
Chứa những phần mà nhiều page cần giống nhau:

- bảng chọn trạng thái (mã EN <-> nhãn VI) cho form/filter;
- chuyển bản ghi nghiệp vụ thành dòng hiển thị của data table;
- lọc phiếu mượn bằng ĐÚNG các hàm nghiệp vụ hiện có (statistics + validators).

Không định nghĩa lại quy tắc nghiệp vụ và không tạo dữ liệu mới — mọi giá trị
đưa lên UI đều bắt nguồn từ CSV/ kết quả pipeline.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple

import statistics as stat_mod
import validators
from cleaners import BORROWER_COLUMNS, DEVICE_COLUMNS, RECORD_COLUMNS
from ui.app_shell import goto_page
from ui.states import render_first_run
from utils.helpers import format_date, format_timestamp, status_label, time_filter_records

#: Cột chuẩn của từng file CSV (dùng cho CRUD + trang Dữ liệu).
CSV_FILES: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    ("devices", "devices.csv", tuple(DEVICE_COLUMNS)),
    ("borrowers", "borrowers.csv", tuple(BORROWER_COLUMNS)),
    ("records", "borrow_records.csv", tuple(RECORD_COLUMNS)),
)

#: Nhãn file theo khoá (dùng cho thông báo).
CSV_LABELS: Dict[str, str] = {key: name for key, name, _ in CSV_FILES}

#: Ba bước khởi đầu khi hệ thống hoàn toàn chưa có dữ liệu.
FIRST_RUN_STEPS: Tuple[str, ...] = (
    "Mở trang Dữ liệu CSV và kiểm tra 3 file dữ liệu.",
    "Thay file mẫu bằng dữ liệu thật của bạn nếu cần.",
    "Quay lại đây — chỉ số, biểu đồ và bảng sẽ tự cập nhật.",
)


def render_first_run_guide(analysis: Dict[str, Any]) -> bool:
    """
    Hướng dẫn khởi đầu khi hệ thống chưa có bản ghi nào.

    Trả về True nếu đã hiển thị hướng dẫn (trang nên dừng render phần còn lại),
    nhờ vậy người dùng mới không phải đối diện một dashboard toàn số 0 mà không
    biết bắt đầu từ đâu.
    """
    if analysis.get("devices") or analysis.get("borrowers") or analysis.get("records"):
        return False
    render_first_run(
        "Hệ thống chưa có dữ liệu",
        "Nạp danh mục thiết bị, người mượn và phiếu mượn để bắt đầu theo dõi.",
        FIRST_RUN_STEPS,
        "Mở trang Dữ liệu CSV",
        "first_run_csv",
        lambda: goto_page("csv"),
        "database",
    )
    return True


#: Lựa chọn trạng thái THIẾT BỊ (mã trong CSV -> nhãn hiển thị).
DEVICE_STATUS_CHOICES: Tuple[Tuple[str, str], ...] = (
    ("available", "Sẵn sàng"),
    ("borrowed", "Đang mượn"),
    ("maintenance", "Bảo trì"),
    ("lost", "Thất thoát"),
)

#: Lựa chọn trạng thái PHIẾU MƯỢN.
RECORD_STATUS_CHOICES: Tuple[Tuple[str, str], ...] = (
    ("borrowing", "Đang mượn"),
    ("returned", "Đã trả"),
    ("overdue", "Quá hạn"),
    ("lost", "Thất thoát"),
)

#: Tuỳ chọn bộ lọc trạng thái (dùng lại đúng danh sách của dashboard gốc).
RECORD_STATUS_FILTERS: List[str] = ["Tất cả", "Đang mượn", "Đã trả", "Quá hạn", "Thất thoát"]
DEVICE_STATUS_FILTERS: List[str] = ["Tất cả", "Sẵn sàng", "Đang mượn", "Bảo trì", "Thất thoát"]

#: Thứ tự nhóm trạng thái thiết bị hiển thị trên biểu đồ (giữ nguyên bản gốc).
DEVICE_STATUS_BUCKETS: Tuple[str, ...] = ("Sẵn sàng", "Đang mượn", "Bảo trì", "Thất thoát")

#: Tuỳ chọn sắp xếp của các bảng danh mục.
DEVICE_SORT_OPTIONS: List[str] = ["Mã thiết bị", "Tên thiết bị", "Loại thiết bị", "Lượt mượn"]
BORROWER_SORT_OPTIONS: List[str] = ["Mã sinh viên", "Họ tên", "Lớp", "Lượt mượn"]


# ----------------------------------------------------------------------
# Lựa chọn trạng thái cho form
# ----------------------------------------------------------------------

def choice_labels(choices: Sequence[Tuple[str, str]]) -> List[str]:
    """Danh sách nhãn hiển thị của các lựa chọn trạng thái."""
    return [label for _, label in choices]


def choice_index(choices: Sequence[Tuple[str, str]], code: Any, default: int = 0) -> int:
    """Vị trí của một mã trạng thái trong danh sách lựa chọn."""
    target = str(code).strip().lower()
    for index, (option_code, _) in enumerate(choices):
        if option_code == target:
            return index
    return default


def choice_code(choices: Sequence[Tuple[str, str]], label: str) -> str:
    """Nhãn trạng thái -> mã lưu trong CSV."""
    for code, option_label in choices:
        if option_label == label:
            return code
    return ""


# ----------------------------------------------------------------------
# Đếm & chuyển dữ liệu sang dòng bảng
# ----------------------------------------------------------------------

def count_by(rows: Sequence[Dict[str, Any]], field: str) -> Dict[str, int]:
    """Đếm số bản ghi theo một trường (dùng cho cột phái sinh như Lượt mượn)."""
    counts: Dict[str, int] = {}
    for row in rows:
        key = str(row.get(field, "")).strip()
        if key:
            counts[key] = counts.get(key, 0) + 1
    return counts


def device_status_counts(devices: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    """
    Đếm thiết bị theo nhóm trạng thái hiển thị (giữ nguyên logic bản gốc).

    Trạng thái ngoài 4 nhóm quen thuộc bị bỏ qua — không tự tạo nhóm mới.
    """
    counts: Dict[str, int] = {label: 0 for label in DEVICE_STATUS_BUCKETS}
    for device in devices:
        label = status_label(device.get("status", ""))
        if label in counts:
            counts[label] += 1
    return counts


def record_rows(
    records: Sequence[Dict[str, Any]],
    devices_by_id: Dict[str, Dict[str, Any]],
    borrowers_by_id: Dict[str, Dict[str, Any]],
) -> List[Dict[str, str]]:
    """Dòng hiển thị của bảng PHIẾU MƯỢN (chỉ field có thật trong schema)."""
    rows: List[Dict[str, str]] = []
    for record in records:
        device_id = str(record.get("device_id", "")).strip()
        borrower_id = str(record.get("borrower_id", "")).strip()
        device = devices_by_id.get(device_id, {})
        borrower = borrowers_by_id.get(borrower_id, {})
        rows.append(
            {
                "Mã phiếu": str(record.get("borrow_id", "")).strip(),
                "Mã thiết bị": device_id or "—",
                "Tên thiết bị": str(device.get("device_name", "")).strip() or "—",
                "Người mượn": str(borrower.get("name", "")).strip() or borrower_id or "—",
                "Lớp": str(borrower.get("class_name", "")).strip() or "—",
                "Ngày mượn": format_date(record.get("borrow_date")),
                "Hạn trả": format_date(record.get("due_date")),
                "Ngày trả": format_date(record.get("return_date")),
                "Trạng thái": status_label(record.get("status", "")),
            }
        )
    return rows


def device_rows(
    devices: Sequence[Dict[str, Any]], borrow_counts: Optional[Dict[str, int]] = None
) -> List[Dict[str, str]]:
    """Dòng hiển thị của bảng THIẾT BỊ (Lượt mượn là số đếm thật từ phiếu mượn)."""
    borrow_counts = borrow_counts or {}
    return [
        {
            "Mã thiết bị": str(device.get("device_id", "")).strip(),
            "Tên thiết bị": str(device.get("device_name", "")).strip(),
            "Loại thiết bị": str(device.get("category", "")).strip(),
            "Trạng thái": status_label(device.get("status", "")),
            "Lượt mượn": str(borrow_counts.get(str(device.get("device_id", "")).strip(), 0)),
        }
        for device in devices
    ]


def borrower_rows(
    borrowers: Sequence[Dict[str, Any]],
    borrow_counts: Optional[Dict[str, int]] = None,
    active_counts: Optional[Dict[str, int]] = None,
) -> List[Dict[str, str]]:
    """Dòng hiển thị của bảng NGƯỜI MƯỢN (số lượt + đang mượn là số đếm thật)."""
    borrow_counts = borrow_counts or {}
    active_counts = active_counts or {}
    return [
        {
            "Mã sinh viên": str(borrower.get("borrower_id", "")).strip(),
            "Họ tên": str(borrower.get("name", "")).strip(),
            "Lớp": str(borrower.get("class_name", "")).strip(),
            "Điện thoại": str(borrower.get("phone", "") or "").strip() or "—",
            "Lượt mượn": str(borrow_counts.get(str(borrower.get("borrower_id", "")).strip(), 0)),
            "Đang mượn": str(active_counts.get(str(borrower.get("borrower_id", "")).strip(), 0)),
        }
        for borrower in borrowers
    ]


# ----------------------------------------------------------------------
# Lọc phiếu mượn — dùng lại đúng hàm nghiệp vụ hiện có
# ----------------------------------------------------------------------

def filter_records(
    records: Sequence[Dict[str, Any]],
    search: str = "",
    status: str = "Tất cả",
    time_mode: str = "Tất cả",
    custom_start: Optional[date] = None,
    custom_end: Optional[date] = None,
    devices_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
    borrowers_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Lọc phiếu mượn theo thời gian / trạng thái / từ khoá.

    Toàn bộ phép lọc đều gọi statistics.* và validators.* như bản gốc:
    'Quá hạn' dùng statistics.filter_overdue, 'Thất thoát' dùng
    validators.find_lost_devices — không tự viết lại điều kiện nghiệp vụ.
    """
    devices_by_id = devices_by_id or {}
    borrowers_by_id = borrowers_by_id or {}

    result = time_filter_records(list(records), time_mode, custom_start, custom_end)
    if status == "Đang mượn":
        result = stat_mod.filter_by_status(result, "borrowing")
    elif status == "Đã trả":
        result = stat_mod.filter_by_status(result, "returned")
    elif status == "Quá hạn":
        result = stat_mod.filter_overdue(result, date.today())
    elif status == "Thất thoát":
        lost_device_ids = set(validators.find_lost_devices(result, date.today()))
        result = [
            row for row in result if str(row.get("device_id", "")).strip() in lost_device_ids
        ]
    return stat_mod.search_records(
        result, search, devices_by_id=devices_by_id, borrowers_by_id=borrowers_by_id
    )


def apply_listing_filters(
    records: Sequence[Dict[str, Any]],
    category: str = "Tất cả",
    status: str = "Tất cả",
    search: str = "",
    devices_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
    borrowers_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
    today: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """
    Lọc loại thiết bị + trạng thái + tìm kiếm (KHÔNG gồm thời gian).

    Dùng chung cho kỳ hiện tại và kỳ trước (pill delta KPI ở Tổng quan): cả hai
    kỳ chịu cùng điều kiện phi thời gian nên delta so sánh công bằng. Muốn lọc
    cả thời gian thì dùng `filter_records` — không copy block này sang page.
    """
    devices_by_id = devices_by_id or {}
    borrowers_by_id = borrowers_by_id or {}
    today = today or date.today()

    result = list(records)
    if category != "Tất cả":
        result = stat_mod.filter_by_category(result, category, devices_by_id)

    if status == "Đang mượn":
        result = stat_mod.filter_by_status(result, "borrowing")
    elif status == "Đã trả":
        result = stat_mod.filter_by_status(result, "returned")
    elif status == "Quá hạn":
        result = stat_mod.filter_overdue(result, today)
    elif status == "Thất thoát":
        lost_device_ids = set(validators.find_lost_devices(result, today))
        result = [
            row for row in result if str(row.get("device_id", "")).strip() in lost_device_ids
        ]

    return stat_mod.search_records(
        result, search, devices_by_id=devices_by_id, borrowers_by_id=borrowers_by_id
    )


# ----------------------------------------------------------------------
# Nhãn & chi tiết bản ghi (dùng cho dialog)
# ----------------------------------------------------------------------

def record_detail_rows(
    record: Dict[str, Any],
    devices_by_id: Dict[str, Dict[str, Any]],
    borrowers_by_id: Dict[str, Dict[str, Any]],
) -> List[Tuple[str, str]]:
    """Các cặp (nhãn, giá trị) của một phiếu mượn — chỉ field thật."""
    device_id = str(record.get("device_id", "")).strip()
    borrower_id = str(record.get("borrower_id", "")).strip()
    device = devices_by_id.get(device_id, {})
    borrower = borrowers_by_id.get(borrower_id, {})
    return [
        ("Mã phiếu", str(record.get("borrow_id", "")).strip()),
        ("Thiết bị", f"{device_id} · {device.get('device_name', '')}".strip(" ·")),
        ("Loại thiết bị", str(device.get("category", "")).strip() or "—"),
        ("Người mượn", f"{borrower_id} · {borrower.get('name', '')}".strip(" ·")),
        ("Lớp", str(borrower.get("class_name", "")).strip() or "—"),
        ("Ngày mượn", format_date(record.get("borrow_date"))),
        ("Hạn trả", format_date(record.get("due_date"))),
        ("Ngày trả", format_date(record.get("return_date"))),
        ("Trạng thái", status_label(record.get("status", ""))),
    ]


def device_detail_rows(
    device: Dict[str, Any], borrow_count: int
) -> List[Tuple[str, str]]:
    """Các cặp (nhãn, giá trị) của một thiết bị."""
    return [
        ("Mã thiết bị", str(device.get("device_id", "")).strip()),
        ("Tên thiết bị", str(device.get("device_name", "")).strip()),
        ("Loại thiết bị", str(device.get("category", "")).strip()),
        ("Trạng thái", status_label(device.get("status", ""))),
        ("Lượt mượn", str(borrow_count)),
    ]


def borrower_detail_rows(
    borrower: Dict[str, Any], borrow_count: int, active_count: int
) -> List[Tuple[str, str]]:
    """Các cặp (nhãn, giá trị) của một người mượn."""
    return [
        ("Mã sinh viên", str(borrower.get("borrower_id", "")).strip()),
        ("Họ tên", str(borrower.get("name", "")).strip()),
        ("Lớp", str(borrower.get("class_name", "")).strip()),
        ("Điện thoại", str(borrower.get("phone", "") or "").strip() or "—"),
        ("Tổng lượt mượn", str(borrow_count)),
        ("Đang mượn", str(active_count)),
    ]


def file_meta_rows(key: str, row_count: int, columns: Sequence[str], modified: Optional[float]) -> List[Tuple[str, str]]:
    """Metadata của một file CSV (trang Dữ liệu)."""
    return [
        ("File", CSV_LABELS.get(key, key)),
        ("Số dòng dữ liệu", str(row_count)),
        ("Số cột", str(len(columns))),
        ("Cập nhật gần nhất", format_timestamp(modified)),
    ]
