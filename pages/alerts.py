# -*- coding: utf-8 -*-
"""
pages/alerts.py — TRANG CẢNH BÁO
================================
Trang giám sát vận hành (không phải CRUD): gom các vấn đề cần xử lý thành 3
nhóm, mỗi mục có mức độ, thiết bị, người mượn, hạn trả, trạng thái và hành
động "Xem chi tiết".

Nguồn dữ liệu (đều là kết quả nghiệp vụ có thật):
  - quá hạn  : validators.find_overdue_records (kèm số ngày quá hạn);
  - thất thoát: validators.find_lost_devices (ngưỡng nghiệp vụ trong validators);
  - cần kiểm tra: `errors` của pipeline (cleaning + validation).

Không có cơ chế đánh dấu "đã xử lý" vì schema CSV không có trường lưu trạng
thái xử lý — hệ thống không tự thêm dữ liệu ngoài dữ liệu hiện có.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Sequence, Tuple

import statistics as stat_mod
import streamlit as st
import validators

from pages.common import record_detail_rows
from ui.badges import severity_badge, severity_label, status_badge
from ui.tables import paginate, render_pagination, render_table_export
from ui.dialogs import detail_dialog, open_dialog, render_pending_dialog
from ui.layout import card_header, page_header, two_column_grid
from ui.metrics import MetricCard, render_kpi_grid
from ui.states import render_empty_state
from utils.helpers import esc, format_date, status_label

#: Số mục mỗi trang trong từng nhóm (quá số này thì sang trang, không kéo dài).
ALERT_PAGE_SIZE = 5


def _alert_item_html(
    title: str, meta: str, details: Sequence[str], badge: str, severity: str = ""
) -> str:
    # Hàng compact 1 dòng để scan nhanh: marker + tiêu đề + mã + chi tiết + badge.
    # Chữ/mức độ vẫn là tín hiệu chính (marker/badge chỉ hỗ trợ scan, kèm dot+chữ
    # theo design system nên đạt accessibility). `details` đã được esc() ở nơi tạo.
    detail_html = '<span class="alert-sep">•</span>'.join(f"<span>{text}</span>" for text in details)
    sev_class = f" sev-{severity}" if severity in ("danger", "warning", "info") else ""
    return (
        f'<div class="alert-item alert-compact{sev_class}">'
        f'<div class="alert-line">'
        f'<span class="alert-marker" aria-hidden="true"></span>'
        f'<span class="alert-title">{esc(title)}</span>'
        f'<span class="alert-meta">{esc(meta)}</span>'
        f'<span class="alert-sep" aria-hidden="true">•</span>'
        f'<span class="alert-desc">{detail_html}</span>'
        f"{badge}"
        f"</div>"
        f"</div>"
    )


#: Mức độ lọc: nhãn hiển thị -> severity nội bộ của item.
SEVERITY_OPTIONS: Tuple[str, ...] = ("Tất cả", "Cao", "Trung bình")

_SEVERITY_MAP: Dict[str, str] = {"Cao": "danger", "Trung bình": "warning"}

#: Khoá session_state của toolbar lọc + phân trang cảnh báo (để "Đặt lại"
#: đưa cả trang về 1).
FILTER_KEYS: Tuple[str, ...] = ("alert_search", "alert_severity")


#: Khoá phân trang của từng nhóm cảnh báo.
OVERDUE_PAGE_KEY = "alert_page_overdue"
LOST_PAGE_KEY = "alert_page_lost"
DATA_PAGE_KEY = "alert_page_data"


def _reset_filters() -> None:
    for key in (*FILTER_KEYS, OVERDUE_PAGE_KEY, LOST_PAGE_KEY, DATA_PAGE_KEY, DISMISSED_KEY):
        st.session_state.pop(key, None)
    st.rerun()


def filter_alert_items(
    items: Sequence[Dict[str, Any]], search: str = "", severity: str = "Tất cả"
) -> List[Dict[str, Any]]:
    """
    Lọc cảnh báo theo từ khoá (tiêu đề/mã/chi tiết) + mức độ.

    Hàm thuần (không chạm Streamlit) để test được: "Cao" khớp severity danger
    (quá hạn nặng/thất thoát/dữ liệu lỗi), "Trung bình" khớp warning.
    """
    needle = str(search or "").strip().lower()
    want = _SEVERITY_MAP.get(str(severity or "Tất cả"), "")
    result: List[Dict[str, Any]] = []
    for item in items:
        if want and str(item.get("severity", "")) != want:
            continue
        if needle:
            haystack = " ".join([
                str(item.get("title", "")),
                str(item.get("meta", "")),
                *[str(detail) for detail in item.get("details", [])],
            ]).lower()
            if needle not in haystack:
                continue
        result.append(item)
    return result


#: Nhãn mức độ cho file export (severity nội bộ -> chữ hiển thị).
_SEVERITY_EXPORT: Dict[str, str] = {"danger": "Cao", "warning": "Trung bình"}


def alert_export_rows(
    overdue_items: Sequence[Dict[str, Any]],
    lost_items: Sequence[Dict[str, Any]],
    data_items: Sequence[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """Dòng export CSV của các cảnh báo đang hiển thị (đã lọc)."""
    import html as _html

    rows: List[Dict[str, str]] = []
    for group, items in (
        ("Quá hạn", overdue_items),
        ("Thất thoát", lost_items),
        ("Cần kiểm tra", data_items),
    ):
        for item in items:
            details = " • ".join(
                _html.unescape(str(detail)) for detail in item.get("details", [])
            )
            rows.append(
                {
                    "Nhóm": group,
                    "Tiêu đề": _html.unescape(str(item.get("title", ""))),
                    "Mã": _html.unescape(str(item.get("meta", ""))),
                    "Chi tiết": details,
                    "Mức độ": _SEVERITY_EXPORT.get(str(item.get("severity", "")), "—"),
                }
            )
    return rows


def _render_toolbar(export_rows: Sequence[Dict[str, str]]) -> Dict[str, str]:
    """Toolbar tìm kiếm + lọc mức độ + xuất CSV, áp dụng cho cả 3 nhóm."""
    with st.container(border=True, key="alert_filter_row"):
        card_header(
            "Tìm kiếm & lọc",
            "Áp dụng ngay cho cả 3 nhóm cảnh báo bên dưới.",
        )
        columns = st.columns([2.0, 1.2, 0.9, 1.1], gap="medium", vertical_alignment="bottom")
        with columns[0]:
            search = st.text_input(
                "Tìm kiếm",
                placeholder="Tìm mã phiếu, thiết bị, người mượn…",
                key="alert_search",
            )
        with columns[1]:
            severity = st.selectbox("Mức độ", list(SEVERITY_OPTIONS), index=0, key="alert_severity")
        with columns[2]:
            st.button(
                "Đặt lại",
                key="alert_reset",
                width="stretch",
                on_click=_reset_filters,
                help="Xoá điều kiện tìm kiếm và mức độ.",
            )
        with columns[3]:
            render_table_export(
                list(export_rows),
                ["Nhóm", "Tiêu đề", "Mã", "Chi tiết", "Mức độ"],
                "alerts_export.csv",
                key="alert_export",
                label="Xuất CSV",
            )
    return {"search": search, "severity": severity}


#: Khoá session_state giữ các cảnh báo đã xử lý trong phiên (ẩn khỏi danh
#: sách; Đặt lại sẽ hiện lại). Không lưu vào CSV vì schema không có trường
#: trạng thái xử lý — xử lý triệt để vẫn là sửa/xoá bản ghi gốc ở trang CRUD.
DISMISSED_KEY = "alerts_dismissed"


def _dismiss_alert(item_key: str) -> None:
    """Đánh dấu một cảnh báo đã xử lý (ẩn trong phiên hiện tại)."""
    dismissed = st.session_state.get(DISMISSED_KEY)
    if not isinstance(dismissed, set):
        dismissed = set()
    dismissed.add(str(item_key))
    st.session_state[DISMISSED_KEY] = dismissed


def _dismissed_keys() -> set:
    dismissed = st.session_state.get(DISMISSED_KEY)
    return set(dismissed) if isinstance(dismissed, set) else set()


def _render_group(
    items: Sequence[Dict[str, Any]],
    empty_title: str,
    empty_hint: str,
    page_key: str,
    noun: str = "cảnh báo",
) -> None:
    """Render danh sách cảnh báo theo trang (5 mục/trang) + nút xem chi tiết."""
    if not items:
        render_empty_state(empty_title, empty_hint, "alert", compact=True)
        return

    page_rows, total_pages = paginate(list(items), page_key, ALERT_PAGE_SIZE)
    for index, item in enumerate(page_rows):
        # Tỉ lệ 5:2 để 2 nút hành động không bị cắt chữ ("Chi tiết" từng hiện
        # "Chi t..." ở tỉ lệ 6:1).
        item_col, action_col = st.columns([5, 2], gap="small", vertical_alignment="center")
        with item_col:
            st.markdown(
                _alert_item_html(
                    item["title"], item["meta"], item["details"],
                    item["badge_html"], item.get("severity", ""),
                ),
                unsafe_allow_html=True,
            )
        with action_col:
            st.button(
                "Chi tiết",
                key=item["key"],
                width="stretch",
                on_click=item["on_click"],
                help=f"Xem chi tiết cảnh báo #{index + 1}",
            )
            st.button(
                "✓ Đã xử lý",
                key=f"handled_{item['key']}",
                width="stretch",
                on_click=_dismiss_alert,
                args=(item["key"],),
                help="Ẩn cảnh báo này trong phiên hiện tại.",
            )
    # Ô trống bù cho đủ 5 hàng để 2 block cạnh nhau cân chiều cao.
    for _ in range(max(0, ALERT_PAGE_SIZE - len(page_rows))):
        st.markdown('<div class="alert-slot-empty" aria-hidden="true"></div>', unsafe_allow_html=True)
    render_pagination(
        page_key, total_pages, len(page_rows), len(items), noun,
        page_size=ALERT_PAGE_SIZE,
    )


def _overdue_items(
    overdue_records: List[Dict[str, Any]],
    devices_by_id: Dict[str, Dict[str, Any]],
    borrowers_by_id: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for record in overdue_records:
        borrow_id = str(record.get("borrow_id", "")).strip()
        device_id = str(record.get("device_id", "")).strip()
        borrower_id = str(record.get("borrower_id", "")).strip()
        days = int(record.get("days_overdue", 0) or 0)
        label = status_label(record.get("status", ""))
        items.append(
            {
                "title": f"Quá hạn {days} ngày",
                "meta": borrow_id,
                "details": [
                    esc(devices_by_id.get(device_id, {}).get("device_name", "") or device_id),
                    esc(borrowers_by_id.get(borrower_id, {}).get("name", "") or borrower_id),
                    esc(borrowers_by_id.get(borrower_id, {}).get("phone", "") or "—"),
                    f"Hạn trả {esc(format_date(record.get('due_date')))}",
                ],
                "badge_html": status_badge(label),
                # Quá hạn >= ngưỡng thất thoát của validators là mức danger.
                "severity": "danger" if days >= validators.LOST_THRESHOLD_DAYS else "warning",
                "key": f"alert_overdue_{borrow_id}",
                "on_click": lambda record=record: open_dialog("alert_record", record=record),
            }
        )
    return items


def _lost_items(
    lost_ids: Sequence[str],
    devices_by_id: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for device_id in sorted(lost_ids):
        device = devices_by_id.get(str(device_id), {})
        items.append(
            {
                "title": "Thiết bị thất thoát",
                "meta": str(device_id),
                "details": [
                    esc(device.get("device_name", "") or "Không có trong danh mục thiết bị"),
                    esc(device.get("category", "") or "—"),
                ],
                "badge_html": status_badge("Thất thoát"),
                "severity": "danger",
                "key": f"alert_lost_{device_id}",
                "on_click": lambda device_id=device_id: open_dialog("alert_lost", device_id=device_id),
            }
        )
    return items


def _data_items(errors: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for index, error in enumerate(errors):
        field = str(error.get("field", "")).strip() or "dữ liệu"
        value = str(error.get("value", "")).strip()
        table = str(error.get("table", "")).strip() or "csv"
        items.append(
            {
                "title": f"Lỗi {field}",
                "meta": f"{table} · dòng {error.get('row', '?')}",
                "details": [
                    esc(value) if value else "—",
                    esc(str(error.get("error", ""))),
                ],
                "badge_html": severity_badge(severity_label("Dữ liệu lỗi")),
                "severity": "danger",
                "key": f"alert_error_{index}",
                "on_click": lambda error=error: open_dialog("alert_error", error=error),
            }
        )
    return items


def _find_record(records: List[Dict[str, Any]], borrow_id: str) -> Dict[str, Any]:
    target = str(borrow_id).strip().upper()
    for record in records:
        if str(record.get("borrow_id", "")).strip().upper() == target:
            return record
    return {"borrow_id": borrow_id}


def render(analysis: Dict[str, Any]) -> None:
    records: List[Dict[str, Any]] = analysis.get("records", [])
    devices: List[Dict[str, Any]] = analysis.get("devices", [])
    borrowers: List[Dict[str, Any]] = analysis.get("borrowers", [])
    errors: List[Dict[str, Any]] = analysis.get("errors", [])

    devices_by_id = stat_mod.build_devices_by_id(devices)
    borrowers_by_id = stat_mod.build_borrowers_by_id(borrowers)
    today = date.today()
    overdue_records = validators.find_overdue_records(records, today)
    lost_ids = validators.find_lost_devices(records, today)

    page_header(
        "Cảnh báo",
        "Theo dõi các vấn đề cần xử lý.",
        meta=(
            f"{len(overdue_records)} phiếu quá hạn · {len(lost_ids)} thiết bị thất thoát · "
            f"{len(errors)} bản ghi dữ liệu cần kiểm tra"
        ),
    )

    render_kpi_grid(
        [
            MetricCard("Quá hạn", len(overdue_records), "Phiếu chưa trả quá hạn", "clock"),
            MetricCard("Thất thoát", len(lost_ids), "Thiết bị chưa được trả", "alert"),
            MetricCard("Dữ liệu cần kiểm tra", len(errors), "Lỗi cần kiểm tra lại", "database"),
            MetricCard(
                "Tổng cảnh báo",
                len(overdue_records) + len(lost_ids) + len(errors),
                "Cần xử lý",
                "bell",
            ),
        ]
    )

    overdue_items = _overdue_items(overdue_records, devices_by_id, borrowers_by_id)
    lost_items = _lost_items(lost_ids, devices_by_id)
    data_items = _data_items(errors)

    # Ghi chú "đã xử lý": schema CSV không có trường lưu trạng thái xử lý nên
    # hệ thống KHÔNG tự thêm — xử lý = sửa/xoá bản ghi gốc ở các trang CRUD,
    # cảnh báo tương ứng sẽ tự biến mất ở lần tải lại.
    # Đọc giá trị lọc TRƯỚC khi render toolbar (pattern session_state như
    # ui/filters._active_conditions) để nút Xuất CSV tải đúng dữ liệu đang lọc.
    pre_filters = {
        "search": str(st.session_state.get("alert_search", "")),
        "severity": str(st.session_state.get("alert_severity", "Tất cả")),
    }
    preview_filtered = (
        filter_alert_items(overdue_items, **pre_filters),
        filter_alert_items(lost_items, **pre_filters),
        filter_alert_items(data_items, **pre_filters),
    )
    filters = _render_toolbar(alert_export_rows(*preview_filtered))
    overdue_items = filter_alert_items(overdue_items, **filters)
    lost_items = filter_alert_items(lost_items, **filters)
    data_items = filter_alert_items(data_items, **filters)

    # Ẩn các mục đã bấm "Đã xử lý" trong phiên (không xoá dữ liệu gốc).
    dismissed = _dismissed_keys()
    if dismissed:
        overdue_items = [i for i in overdue_items if i["key"] not in dismissed]
        lost_items = [i for i in lost_items if i["key"] not in dismissed]
        data_items = [i for i in data_items if i["key"] not in dismissed]
        st.caption(
            f"Đã ẩn {len(dismissed)} mục đã xử lý trong phiên này "
            "(bấm Đặt lại để hiện lại)."
        )

    left, right = two_column_grid()

    with left:
        with st.container(border=True):
            card_header(
                "Quá hạn",
                "Phiếu chưa trả và đã vượt hạn trả.",
                chip=f"{len(overdue_items)}/{len(overdue_records)}",
            )
            _render_group(
                overdue_items,
                "Không có phiếu quá hạn.",
                "Mọi phiếu đang mượn đều còn trong hạn trả.",
                OVERDUE_PAGE_KEY,
                "phiếu quá hạn",
            )

    with right:
        with st.container(border=True):
            card_header(
                "Thất thoát",
                "Thiết bị đang mượn nhưng không còn trong danh mục quản lý.",
                chip=f"{len(lost_items)}/{len(lost_ids)}",
            )
            _render_group(
                lost_items,
                "Không có thiết bị thất thoát.",
                "Mọi thiết bị đang mượn đều tồn tại trong danh mục.",
                LOST_PAGE_KEY,
                "thiết bị thất thoát",
            )

    with st.container(border=True):
        card_header(
            "Cần kiểm tra",
            "Bản ghi lỗi cần kiểm tra lại.",
            chip=f"{len(data_items)}/{len(errors)}",
        )
        _render_group(
            data_items,
            "Không có bản ghi lỗi.",
            "Dữ liệu hiện tại không có lỗi.",
            DATA_PAGE_KEY,
            "bản ghi lỗi",
        )

    render_pending_dialog(
        {
            "alert_record": lambda payload: detail_dialog(
                f"Phiếu mượn {payload.get('record', {}).get('borrow_id', '')}",
                record_detail_rows(
                    _find_record(records, payload.get("record", {}).get("borrow_id", "")),
                    devices_by_id,
                    borrowers_by_id,
                ),
                badges=[status_label(payload.get("record", {}).get("status", ""))],
                note=(
                    f"Quá hạn {int(payload.get('record', {}).get('days_overdue', 0) or 0)} ngày "
                    "tính từ hạn trả của phiếu."
                    if payload.get("record", {}).get("days_overdue")
                    else ""
                ),
            ),
            "alert_lost": lambda payload: detail_dialog(
                f"Thiết bị {payload.get('device_id', '')}",
                [
                    ("Mã thiết bị", str(payload.get("device_id", ""))),
                    (
                        "Tên thiết bị",
                        str(
                            devices_by_id.get(str(payload.get("device_id", "")), {}).get(
                                "device_name", ""
                            )
                        )
                        or "Không có trong danh mục thiết bị",
                    ),
                    (
                        "Loại thiết bị",
                        str(
                            devices_by_id.get(str(payload.get("device_id", "")), {}).get(
                                "category", ""
                            )
                        )
                        or "—",
                    ),
                ],
                badges=["Thất thoát"],
                note=(
                    "Thiết bị vẫn đang trong phiếu mượn chưa trả nhưng không còn "
                    "trong danh mục thiết bị — cần kiểm tra thực tế."
                ),
            ),
            "alert_error": lambda payload: detail_dialog(
                "Bản ghi dữ liệu cần kiểm tra",
                [
                    ("Bảng", str(payload.get("error", {}).get("table", "")) or "—"),
                    ("Dòng", str(payload.get("error", {}).get("row", "?"))),
                    ("Trường", str(payload.get("error", {}).get("field", "")) or "—"),
                    ("Giá trị", str(payload.get("error", {}).get("value", "")) or "—"),
                    ("Lỗi", str(payload.get("error", {}).get("error", ""))),
                ],
                badges=["Dữ liệu lỗi"],
            ),
        }
    )
