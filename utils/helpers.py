# -*- coding: utf-8 -*-
"""
utils/helpers.py — HELPER DÙNG CHUNG CHO TẦNG UI
================================================
Chỉ chứa hàm thuần (pure), KHÔNG chứa business logic mới:

- `status_label`: đổi mã trạng thái (EN) sang nhãn hiển thị tiếng Việt.
- `device_category_options`: danh sách loại thiết bị cho selectbox.
- `time_filter_records`: lọc phiếu theo mốc thời gian — GIỮ NGUYÊN hành vi
  của `_time_filter_records` trong bản gốc app.py (không đổi thuật toán).
- `format_date`: định dạng ngày ISO -> dd/mm/yyyy để hiển thị.
- `icon`: trả về SVG inline (không phụ thuộc font icon ngoài, không bao giờ
  hiện "literal token" trên UI như :material_xxx:).
- `esc`: escape HTML cho dữ liệu lấy từ CSV trước khi nhúng vào markup.
"""
from __future__ import annotations

import html
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from cleaners import normalize_text, parse_date, to_iso

#: Nhãn tiếng Việt cho mã trạng thái của thiết bị và phiếu mượn.
STATUS_LABELS: Dict[str, str] = {
    "available": "Sẵn sàng",
    "borrowed": "Đang mượn",
    "maintenance": "Bảo trì",
    "lost": "Thất thoát",
    "borrowing": "Đang mượn",
    "returned": "Đã trả",
    "overdue": "Quá hạn",
}

#: Đường dẫn SVG (viewBox 24x24, stroke = currentColor) cho từng icon.
_ICON_PATHS: Dict[str, str] = {
    "dashboard": (
        '<rect x="3" y="3" width="7.5" height="7.5" rx="1.5"/>'
        '<rect x="13.5" y="3" width="7.5" height="7.5" rx="1.5"/>'
        '<rect x="3" y="13.5" width="7.5" height="7.5" rx="1.5"/>'
        '<rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.5"/>'
    ),
    "receipt": (
        '<path d="M6 3h12v18l-2.4-1.7-2.4 1.7-2.4-1.7L8.4 21 6 19.3z"/>'
        '<path d="M9 8.5h6M9 12h6"/>'
    ),
    "monitor": '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8.5 20h7M12 16.5V20"/>',
    "users": (
        '<circle cx="9" cy="8.5" r="3.4"/>'
        '<path d="M3.2 19.5c.7-3.1 3-5 5.8-5s5.1 1.9 5.8 5"/>'
        '<circle cx="17" cy="9.5" r="2.6"/>'
        '<path d="M16.2 14.6c2.3.3 4 1.9 4.6 4.4"/>'
    ),
    "user": '<circle cx="12" cy="8.5" r="3.8"/><path d="M4.8 20c.9-3.5 3.7-5.6 7.2-5.6s6.3 2.1 7.2 5.6"/>',
    "alert": '<path d="M12 4.5L2.8 20h18.4z"/><path d="M12 10.5v4"/><path d="M12 17.2v.01"/>',
    "report": (
        '<path d="M7 3.5h7.5L19 8v12.5H7z"/>'
        '<path d="M14 3.5V8h5"/>'
        '<path d="M10 12.5h5M10 16h5"/>'
    ),
    "database": (
        '<ellipse cx="12" cy="6" rx="7" ry="3"/>'
        '<path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6"/>'
        '<path d="M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"/>'
    ),
    "search": '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.6-4.6"/>',
    "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "box": (
        '<path d="M12 3.5l7.5 4.2v8.6L12 20.5l-7.5-4.2V7.7z"/>'
        '<path d="M4.5 7.7L12 12l7.5-4.3"/>'
        '<path d="M12 12v8.5"/>'
    ),
    "swap": (
        '<path d="M4 7h13"/><path d="M13 3l4 4-4 4"/>'
        '<path d="M20 17H7"/><path d="M11 13l-4 4 4 4"/>'
    ),
    "bell": (
        '<path d="M18.5 16h-13c1.3-1.5 2-2.7 2-6a4.5 4.5 0 019 0c0 3.3.7 4.5 2 6z"/>'
        '<path d="M10.3 19a1.8 1.8 0 003.4 0"/>'
    ),
    "filter": '<path d="M4 5.5h16l-6.2 7.2v5.4l-3.6 1.9v-7.3z"/>',
    "reset": (
        '<path d="M20.5 11.5A8.5 8.5 0 1 1 12 3.5c2.6 0 4.9 1.1 6.5 2.9"/>'
        '<path d="M20.5 3.5V7H17"/>'
    ),
    "check": '<path d="M4.5 12.5l4.8 4.8L19.5 6.7"/>',
    "list": (
        '<path d="M8 6h12M8 12h12M8 18h12"/>'
        '<path d="M4 6v.01M4 12v.01M4 18v.01"/>'
    ),
}

#: Icon dùng khi tên icon không tồn tại trong hệ thống.
_FALLBACK_ICON = "dashboard"


def status_label(value: Any) -> str:
    """
    Đổi mã trạng thái sang nhãn tiếng Việt.

    Giữ nguyên hành vi bản gốc: giá trị lạ được trả về nguyên văn (đã trim)
    để không che mất lỗi dữ liệu thật; giá trị rỗng -> '—'.
    """
    text = normalize_text(value)
    return STATUS_LABELS.get(text.lower(), text or "—")


def device_category_options(devices: List[Dict[str, Any]]) -> List[str]:
    """Danh sách loại thiết bị (đã sắp xếp) kèm lựa chọn 'Tất cả' ở đầu."""
    categories = sorted(
        {normalize_text(d.get("category")) for d in devices if normalize_text(d.get("category"))}
    )
    return ["Tất cả", *categories]


def time_filter_records(
    records: List[Dict[str, Any]],
    mode: str,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """
    Lọc phiếu theo mốc thời gian (giữ nguyên thuật toán của bản gốc app.py).

    Mốc so sánh là ngày mượn, nếu thiếu thì dùng ngày hạn trả; phiếu không
    parse được ngày nào sẽ bị loại khỏi kết quả.
    """
    if mode == "Tất cả":
        return list(records)

    today = date.today()
    if mode == "7 ngày":
        start_dt = today - timedelta(days=7)
        end_dt = today
    elif mode == "30 ngày":
        start_dt = today - timedelta(days=30)
        end_dt = today
    elif mode == "3 tháng":
        start_dt = today - timedelta(days=90)
        end_dt = today
    else:
        start_dt = start or today - timedelta(days=30)
        end_dt = end or today

    out: List[Dict[str, Any]] = []
    for row in records:
        borrow_date = parse_date(row.get("borrow_date"))
        due_date = parse_date(row.get("due_date"))
        ref_date = borrow_date or due_date
        if ref_date is None:
            continue
        if start_dt <= ref_date <= end_dt:
            out.append(row)
    return out


def previous_window(
    mode: str,
    start: Optional[date] = None,
    end: Optional[date] = None,
    today: Optional[date] = None,
) -> Optional[tuple[date, date]]:
    """
    Khoảng kỳ TRƯỚC liền kề cùng độ dài với kỳ của `time_filter_records`.

    Dùng cho pill delta KPI Dashboard (so kỳ hiện tại với kỳ trước). Trả về
    None khi mode "Tất cả" (không có kỳ so sánh) — caller ẨN pill thay vì bịa.
    """
    if mode == "Tất cả":
        return None
    today = today or date.today()
    if mode == "7 ngày":
        cur_start, cur_end = today - timedelta(days=7), today
    elif mode == "30 ngày":
        cur_start, cur_end = today - timedelta(days=30), today
    elif mode == "3 tháng":
        cur_start, cur_end = today - timedelta(days=90), today
    else:
        cur_start = start or today - timedelta(days=30)
        cur_end = end or today
    length = (cur_end - cur_start).days
    prev_end = cur_start - timedelta(days=1)
    return prev_end - timedelta(days=length), prev_end


def format_date(value: Any) -> str:
    """
    Định dạng ngày để hiển thị (dd/mm/yyyy).

    - Ô rỗng -> '—'.
    - Giá trị không parse được -> trả nguyên văn (giữ lại thông tin dữ liệu
      lỗi thay vì âm thầm thay bằng ký tự khác).
    """
    text = normalize_text(value)
    if not text:
        return "—"
    iso = to_iso(text)
    if not iso:
        return text
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def esc(value: Any) -> str:
    """Escape HTML cho dữ liệu người dùng (tránh vỡ markup / chèn thẻ)."""
    return html.escape("" if value is None else str(value), quote=True)


def to_csv_date(value: Any) -> str:
    """
    Đổi ngày (ISO từ form) về đúng định dạng đang dùng trong file CSV (dd/mm/yyyy)
    để file dữ liệu giữ nguyên văn phong gốc sau khi ghi.
    """
    text = normalize_text(value)
    if not text:
        return ""
    iso = to_iso(text)
    if not iso:
        return text
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def month_label(value: Any) -> str:
    """'2026-06' -> '06/2026' để hiển thị trục thời gian."""
    text = normalize_text(value)
    parts = text.split("-")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return f"{parts[1]}/{parts[0]}"
    return text


def format_timestamp(epoch_seconds: Optional[float]) -> str:
    """Thời điểm sửa file gần nhất -> 'dd/mm/yyyy HH:MM' (trống nếu không có)."""
    if not epoch_seconds:
        return "—"
    moment = datetime.fromtimestamp(epoch_seconds)
    return moment.strftime("%d/%m/%Y %H:%M")


def sort_rows(
    rows: List[Dict[str, Any]], key: str, reverse: bool = False
) -> List[Dict[str, Any]]:
    """Sắp xếp danh sách bản ghi theo một trường (chỉ phục vụ hiển thị)."""
    return sorted(rows, key=lambda row: str(row.get(key, "")), reverse=reverse)


def icon_data_uri(name: str, color: str, size: int = 16, stroke_width: float = 1.8) -> str:
    """
    SVG icon dưới dạng data-URI để nhúng vào CSS (nền của button/nav item).

    Dùng cùng bộ icon với `icon()` nên toàn app chỉ có MỘT phong cách icon,
    và màu được nhúng sẵn theo design token truyền vào.
    """
    body = _ICON_PATHS.get(name, _ICON_PATHS[_FALLBACK_ICON])
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_width}" '
        f'stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    )
    return "data:image/svg+xml;utf8," + quote(svg, safe="")


def icon(name: str, size: int = 18, stroke_width: float = 1.8) -> str:
    """
    Trả về SVG inline cho icon (stroke = currentColor).

    Dùng SVG inline thay cho font icon để icon luôn render đúng và không bao
    giờ hiển thị literal token trên UI.
    """
    body = _ICON_PATHS.get(name, _ICON_PATHS[_FALLBACK_ICON])
    return (
        f'<svg class="icon icon-{name}" width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="currentColor" stroke-width="{stroke_width}" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'
        f"{body}</svg>"
    )
