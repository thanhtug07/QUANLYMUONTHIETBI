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
from typing import Any, Dict, List, Sequence

import statistics as stat_mod
import streamlit as st
import validators

from pages.common import record_detail_rows
from ui.badges import severity_badge, severity_label, status_badge
from ui.dialogs import detail_dialog, open_dialog, render_pending_dialog
from ui.layout import card_header, page_header, two_column_grid
from ui.metrics import MetricCard, render_kpi_grid
from ui.states import render_empty_state
from utils.helpers import esc, format_date, status_label

#: Số mục tối đa hiển thị trong mỗi nhóm.
ITEM_LIMIT = 8


def _alert_item_html(
    title: str, meta: str, details: Sequence[str], badge: str
) -> str:
    detail_html = ""
    for index, text in enumerate(details):
        if index:
            detail_html += '<span class="alert-sep">•</span>'
        detail_html += f"<span>{text}</span>"
    return (
        f'<div class="alert-item">'
        f'<div class="alert-top">'
        f'<div class="alert-type"><span class="alert-marker"></span>{esc(title)}</div>'
        f'<div class="alert-meta">{esc(meta)}</div>'
        f"</div>"
        f'<div class="alert-body">{detail_html}{badge}</div>'
        f"</div>"
    )


def _render_group(
    items: Sequence[Dict[str, Any]],
    empty_title: str,
    empty_hint: str,
) -> None:
    """Render danh sách cảnh báo: mỗi mục là một dòng + nút xem chi tiết."""
    if not items:
        render_empty_state(empty_title, empty_hint, "alert", compact=True)
        return

    for index, item in enumerate(list(items)[:ITEM_LIMIT]):
        item_col, action_col = st.columns([4, 1.5], gap="small", vertical_alignment="center")
        with item_col:
            st.markdown(
                _alert_item_html(
                    item["title"], item["meta"], item["details"], item["badge_html"]
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


    remaining = len(items) - ITEM_LIMIT
    if remaining > 0:
        st.markdown(
            f'<div class="table-footnote">Còn {remaining} cảnh báo khác trong nhóm này.</div>',
            unsafe_allow_html=True,
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
                    f"Hạn trả {esc(format_date(record.get('due_date')))}",
                ],
                "badge_html": status_badge(label),
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
            MetricCard("Dữ liệu cần kiểm tra", len(errors), "Lỗi làm sạch / kiểm tra", "database"),
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

    left, right = two_column_grid()

    with left:
        with st.container(border=True):
            card_header(
                "Quá hạn",
                "Phiếu chưa trả và đã vượt hạn trả.",
                chip=str(len(overdue_records)),
            )
            _render_group(
                overdue_items,
                "Không có phiếu quá hạn.",
                "Mọi phiếu đang mượn đều còn trong hạn trả.",
            )

    with right:
        with st.container(border=True):
            card_header(
                "Thất thoát",
                "Thiết bị đang mượn nhưng không còn trong danh mục quản lý.",
                chip=str(len(lost_ids)),
            )
            _render_group(
                lost_items,
                "Không có thiết bị thất thoát.",
                "Mọi thiết bị đang mượn đều tồn tại trong danh mục.",
            )

    with st.container(border=True):
        card_header(
            "Cần kiểm tra",
            "Bản ghi lỗi khi làm sạch hoặc khi kiểm tra dữ liệu.",
            chip=str(len(errors)),
        )
        _render_group(
            data_items,
            "Không có bản ghi lỗi.",
            "Dữ liệu hiện tại vượt qua toàn bộ bước làm sạch và kiểm tra.",
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
                    "theo validators.find_overdue_records."
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
