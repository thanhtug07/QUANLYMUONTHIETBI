# -*- coding: utf-8 -*-
"""
pages/equipment.py — TRANG THIẾT BỊ (CRUD)
==========================================
Quản lý danh mục thiết bị trong `data/devices.csv`: danh sách + tìm kiếm +
lọc theo loại/trạng thái + sắp xếp, và CRUD qua dialog.

Cột "Lượt mượn" là số đếm THẬT từ phiếu mượn (không sinh dữ liệu mới).
Kiểm tra dữ liệu dùng `validators.validate_candidate_device`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st
from cleaners import DEVICE_COLUMNS, normalize_text

import data_store
import main
import validators
from pages.common import (
    DEVICE_SORT_OPTIONS,
    DEVICE_STATUS_CHOICES,
    DEVICE_STATUS_FILTERS,
    choice_code,
    choice_index,
    choice_labels,
    count_by,
    device_detail_rows,
    device_rows,
    render_first_run_guide,
)
from ui.app_shell import clear_data_cache
from ui.dialogs import (
    close_dialog,
    confirm_dialog,
    detail_dialog,
    form_dialog,
    open_dialog,
    render_pending_dialog,
)
from ui.forms import form_section, render_flash, set_flash, validation_summary
from ui.layout import card_header, page_header
from ui.states import render_hint
from ui.tables import (
    paginate,
    render_bulk_action_bar,
    render_pagination,
    render_records_table,
    render_row_action_bar,
    render_table_export,
)
from utils.helpers import device_category_options, status_label

#: Cột hiển thị của bảng thiết bị.
TABLE_COLUMNS: List[str] = ["Mã thiết bị", "Tên thiết bị", "Loại thiết bị", "Trạng thái", "Lượt mượn"]

COLUMN_CONFIG: Dict[str, Any] = {
    "Mã thiết bị": st.column_config.TextColumn("Mã thiết bị", width="small"),
    "Tên thiết bị": st.column_config.TextColumn("Tên thiết bị", width="medium"),
    "Loại thiết bị": st.column_config.TextColumn("Loại thiết bị", width="small"),
    "Lượt mượn": st.column_config.NumberColumn("Lượt mượn", width="small"),
}

FILTER_KEYS: List[str] = ["device_search", "device_category", "device_status", "device_sort"]

#: Khoá phân trang của bảng thiết bị.
PAGE_KEY = "device_page"

#: Trường sắp xếp tương ứng từng nhãn (Lượt mượn sắp theo số đếm, giảm dần).
SORT_FIELDS: Dict[str, str] = {
    "Mã thiết bị": "device_id",
    "Tên thiết bị": "device_name",
    "Loại thiết bị": "category",
    "Lượt mượn": "borrow_count",
}


def _reset_filters() -> None:
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)
    st.session_state.pop(PAGE_KEY, None)
    st.rerun()


def _active_filters(filters: Dict[str, Any]) -> int:
    """Số bộ lọc đang thực sự áp dụng (hiển thị trên header của toolbar)."""
    active = 0
    if str(filters.get("search", "")).strip():
        active += 1
    for key in ("category", "status"):
        if str(filters.get(key, "Tất cả")) != "Tất cả":
            active += 1
    if str(filters.get("sort", "")) not in ("", "Mã thiết bị"):
        active += 1
    return active


def _render_toolbar(devices: List[Dict[str, Any]]) -> Dict[str, Any]:
    with st.container(border=True, key="device_filter_row"):
        # Đọc trước lựa chọn để đếm bộ lọc cho chip (session_state là nguồn đúng).
        pre = {
            "search": str(st.session_state.get("device_search", "")),
            "category": str(st.session_state.get("device_category", "Tất cả")),
            "status": str(st.session_state.get("device_status", "Tất cả")),
            "sort": str(st.session_state.get("device_sort", "Mã thiết bị")),
        }
        active = _active_filters(pre)
        card_header(
            "Tìm kiếm & lọc",
            "Áp dụng ngay cho bảng thiết bị bên dưới.",
            chip=f"{active} bộ lọc" if active else "",
        )
        columns = st.columns([1.9, 1.15, 1.15, 1.15, 0.85], gap="medium", vertical_alignment="bottom")
        with columns[0]:
            search = st.text_input(
                "Tìm kiếm",
                placeholder="Tìm mã, tên hoặc loại thiết bị…",
                key="device_search",
            )
        with columns[1]:
            category = st.selectbox(
                "Loại thiết bị",
                device_category_options(devices),
                index=0,
                key="device_category",
            )
        with columns[2]:
            status = st.selectbox("Trạng thái", DEVICE_STATUS_FILTERS, index=0, key="device_status")
        with columns[3]:
            sort = st.selectbox("Sắp xếp theo", DEVICE_SORT_OPTIONS, index=0, key="device_sort")
        with columns[4]:
            st.button(
                "Đặt lại",
                key="device_reset",
                width="stretch",
                on_click=_reset_filters,
                help="Xoá toàn bộ điều kiện lọc.",
            )
    return {"search": search, "category": category, "status": status, "sort": sort}


def _matches(value: Any, query: str) -> bool:
    return query in normalize_text(value).lower()


def _apply_filters(
    devices: List[Dict[str, Any]],
    borrow_counts: Dict[str, int],
    filters: Dict[str, Any],
) -> List[Dict[str, Any]]:
    query = str(filters["search"]).strip().lower()
    result = [
        device
        for device in devices
        if (filters["category"] == "Tất cả" or normalize_text(device.get("category")) == filters["category"])
        and (filters["status"] == "Tất cả" or status_label(device.get("status", "")) == filters["status"])
        and (
            not query
            or _matches(device.get("device_id", ""), query)
            or _matches(device.get("device_name", ""), query)
            or _matches(device.get("category", ""), query)
        )
    ]

    field = SORT_FIELDS.get(str(filters["sort"]), "device_id")
    if field == "borrow_count":
        return sorted(
            result,
            key=lambda device: borrow_counts.get(str(device.get("device_id", "")).strip(), 0),
            reverse=True,
        )
    return sorted(result, key=lambda device: str(device.get(field, "")).lower())


def _find_device(devices: List[Dict[str, Any]], device_id: str) -> Optional[Dict[str, Any]]:
    target = str(device_id).strip().upper()
    for device in devices:
        if str(device.get("device_id", "")).strip().upper() == target:
            return device
    return None


def _device_form(analysis: Dict[str, Any], device: Optional[Dict[str, Any]]) -> None:
    devices: List[Dict[str, Any]] = analysis.get("devices", [])
    records: List[Dict[str, Any]] = analysis.get("records", [])
    editing = device is not None
    categories = [option for option in device_category_options(devices) if option != "Tất cả"]

    default_id = (
        str(device.get("device_id", "")).strip()
        if editing
        else data_store.next_sequential_id(devices, "device_id", "TB")
    )
    default_status = choice_index(DEVICE_STATUS_CHOICES, device.get("status", "")) if editing else 0

    with st.form("device_form"):
        form_section("Thông tin thiết bị", "Mã thiết bị được gợi ý từ danh sách hiện có.")
        first_row = st.columns([1, 1.6], gap="medium")
        device_id = first_row[0].text_input("Mã thiết bị", value=default_id)
        device_name = first_row[1].text_input(
            "Tên thiết bị", value=str(device.get("device_name", "")) if editing else ""
        )

        form_section("Phân loại & trạng thái", "Loại thiết bị dùng để nhóm thống kê lượt mượn.")
        second_row = st.columns(2, gap="medium")
        category = second_row[0].text_input(
            "Loại thiết bị",
            value=str(device.get("category", "")) if editing else "",
            help=(
                f"Loại đang có trong dữ liệu: {', '.join(categories)}"
                if categories
                else "Chưa có loại thiết bị nào trong dữ liệu."
            ),
        )
        status_choice = second_row[1].selectbox(
            "Trạng thái", choice_labels(DEVICE_STATUS_CHOICES), index=default_status, key="device_form_status"
        )

        cancel_col, submit_col = st.columns(2, gap="medium")
        cancelled = cancel_col.form_submit_button("Huỷ", width="stretch")
        submitted = submit_col.form_submit_button(
            "Lưu thay đổi" if editing else "Thêm thiết bị", type="primary", width="stretch"
        )

    if cancelled:
        close_dialog()
        return
    if not submitted:
        return

    candidate = {
        "device_id": str(device_id).strip().upper(),
        "device_name": str(device_name).strip(),
        "category": str(category).strip(),
        "status": choice_code(DEVICE_STATUS_CHOICES, status_choice),
    }

    errors = validators.validate_candidate_device(
        candidate, devices, existing_records=records, editing=editing
    )
    if errors:
        validation_summary(errors)
        return

    if editing:
        data_store.update_row(main.DEVICES_CSV, DEVICE_COLUMNS, "device_id", candidate["device_id"], candidate)
        set_flash(f"Đã cập nhật thiết bị {candidate['device_id']}.")
    else:
        data_store.insert_row(main.DEVICES_CSV, DEVICE_COLUMNS, candidate)
        set_flash(f"Đã thêm thiết bị {candidate['device_id']}.")
    clear_data_cache()
    close_dialog()


def _dialog_view(payload: Dict[str, Any], analysis: Dict[str, Any]) -> None:
    device = _find_device(analysis.get("devices", []), payload.get("device_id", ""))
    if device is None:
        detail_dialog("Không tìm thấy thiết bị", [("Mã thiết bị", str(payload.get("device_id", "")))])
        return
    borrow_count = count_by(analysis.get("records", []), "device_id").get(
        str(device.get("device_id", "")).strip(), 0
    )
    detail_dialog(
        f"Thiết bị {device.get('device_id', '')}",
        device_detail_rows(device, borrow_count),
        badges=[status_label(device.get("status", ""))],
    )


def _dialog_edit(payload: Dict[str, Any], analysis: Dict[str, Any]) -> None:
    device = _find_device(analysis.get("devices", []), payload.get("device_id", ""))
    if device is None:
        detail_dialog("Không tìm thấy thiết bị", [("Mã thiết bị", str(payload.get("device_id", "")))])
        return
    form_dialog(f"Sửa thiết bị {device.get('device_id', '')}", lambda: _device_form(analysis, device))


def _dialog_create(analysis: Dict[str, Any]) -> None:
    form_dialog("Thêm thiết bị", lambda: _device_form(analysis, None))


def _dialog_delete(payload: Dict[str, Any], analysis: Dict[str, Any]) -> None:
    device = _find_device(analysis.get("devices", []), payload.get("device_id", ""))
    if device is None:
        detail_dialog("Không tìm thấy thiết bị", [("Mã thiết bị", str(payload.get("device_id", "")))])
        return

    borrow_count = count_by(analysis.get("records", []), "device_id").get(
        str(device.get("device_id", "")).strip(), 0
    )
    message = (
        f"Bạn có chắc muốn xóa thiết bị {device.get('device_id', '')}? "
        "Thao tác này không thể hoàn tác."
    )
    if borrow_count:
        message += (
            f" Thiết bị này đang xuất hiện trong {borrow_count} phiếu mượn — "
            "các phiếu đó sẽ được giữ nguyên và được báo là dữ liệu cần kiểm tra."
        )

    def _confirm() -> None:
        removed = data_store.delete_row(
            main.DEVICES_CSV, DEVICE_COLUMNS, "device_id", str(device.get("device_id", ""))
        )
        clear_data_cache()
        if removed:
            set_flash(f"Đã xóa thiết bị {device.get('device_id', '')}.")
        else:
            set_flash("Không tìm thấy thiết bị để xóa.")

    confirm_dialog(
        "Xóa thiết bị",
        message,
        "Xóa thiết bị",
        _confirm,
        detail_rows=device_detail_rows(device, borrow_count),
    )


def _dialog_bulk_status(payload: Dict[str, Any], analysis: Dict[str, Any]) -> None:
    """
    Đặt trạng thái hàng loạt cho thiết bị đang chọn.

    Chỉ đổi trường `status` của thiết bị (field có thật trong schema), dữ liệu
    khác giữ nguyên; ghi qua data_store.update_row nên dòng không chọn không
    bị động đến.
    """
    device_ids = [str(value).strip() for value in payload.get("device_ids", []) if str(value).strip()]
    if not device_ids:
        detail_dialog("Chưa chọn thiết bị", [("Số mục chọn", "0")])
        return

    valid_ids = {str(d.get("device_id", "")).strip() for d in analysis.get("devices", [])}
    targets = [device_id for device_id in device_ids if device_id in valid_ids]

    @st.dialog("Đặt trạng thái thiết bị", width="small")
    def _wrap() -> None:
        if not targets:
            st.markdown('<p class="dialog-text">Không còn thiết bị nào trong danh mục.</p>', unsafe_allow_html=True)
            if st.button("Đóng", key="bulk_status_close", width="stretch"):
                close_dialog()
            return

        st.markdown(
            f'<p class="dialog-text">Chọn trạng thái mới cho <strong>{len(targets)}</strong> '
            "thiết bị đang chọn.</p>",
            unsafe_allow_html=True,
        )
        labels = choice_labels(DEVICE_STATUS_CHOICES)
        selected_label = st.selectbox("Trạng thái", labels, index=0, key="bulk_status_value")
        confirm_col, apply_col = st.columns(2, gap="medium")
        if confirm_col.button("Huỷ", key="bulk_status_cancel", width="stretch"):
            close_dialog()
        if apply_col.button("Áp dụng", key="bulk_status_apply", type="primary", width="stretch"):
            new_status = choice_code(DEVICE_STATUS_CHOICES, selected_label)
            changed = 0
            for device_id in targets:
                if data_store.update_row(
                    main.DEVICES_CSV, DEVICE_COLUMNS, "device_id", device_id, {"status": new_status}
                ):
                    changed += 1
            clear_data_cache()
            close_dialog()
            if changed:
                set_flash(f"Đã đặt {changed} thiết bị sang “{selected_label}”.")
            else:
                set_flash("Không có thiết bị nào được cập nhật.")

    _wrap()


def _dialog_bulk_delete(payload: Dict[str, Any], analysis: Dict[str, Any]) -> None:
    device_ids = [str(value).strip() for value in payload.get("device_ids", []) if str(value).strip()]
    if not device_ids:
        detail_dialog("Chưa chọn thiết bị", [("Số mục chọn", "0")])
        return

    borrow_counts = count_by(analysis.get("records", []), "device_id")
    linked_count = sum(1 for device_id in device_ids if borrow_counts.get(device_id, 0))
    existing_ids = {
        str(device.get("device_id", "")).strip()
        for device in analysis.get("devices", [])
    }

    def _confirm() -> None:
        removed = data_store.delete_rows(main.DEVICES_CSV, DEVICE_COLUMNS, "device_id", device_ids)
        clear_data_cache()
        if removed == len(device_ids):
            set_flash(f"Đã xóa {removed} thiết bị.")
        else:
            set_flash(f"Đã xóa {removed}/{len(device_ids)} thiết bị; một số bản ghi không còn tồn tại.")

    confirm_dialog(
        "Xóa nhiều thiết bị",
        (
            f"Xóa {len(device_ids)} thiết bị? Hành động này sẽ xóa các bản ghi đã chọn. "
            "Các phiếu mượn liên quan được giữ nguyên và sẽ được báo là dữ liệu cần kiểm tra."
        ),
        "Xóa thiết bị đã chọn",
        _confirm,
        detail_rows=[
            ("Số thiết bị đã chọn", str(len(device_ids))),
            ("Mã thiết bị", ", ".join(device_ids[:12]) + ("..." if len(device_ids) > 12 else "")),
            ("Có phiếu mượn liên quan", str(linked_count)),
            ("Bản ghi còn tồn tại", str(sum(1 for value in device_ids if value in existing_ids))),
        ],
    )


def render(analysis: Dict[str, Any]) -> None:
    devices: List[Dict[str, Any]] = analysis.get("devices", [])
    records: List[Dict[str, Any]] = analysis.get("records", [])
    borrow_counts = count_by(records, "device_id")

    page_header(
        "Thiết bị",
        "Quản lý danh sách và tình trạng thiết bị.",
        meta=f"{len(devices)} thiết bị trong danh mục.",
        action_label="+ Thêm thiết bị",
        action_key="device_create",
        on_action=lambda: open_dialog("create"),
        action_help="Mở form thêm thiết bị mới.",
    )

    render_flash()

    if render_first_run_guide(analysis):
        return

    filters = _render_toolbar(devices)
    filtered = _apply_filters(devices, borrow_counts, filters)
    all_rows = device_rows(filtered, borrow_counts)
    page_rows, total_pages = paginate(all_rows, PAGE_KEY)

    with st.container(border=True):
        card_header(
            "Danh sách thiết bị",
            "Chọn một dòng để xem, sửa hoặc xóa thiết bị.",
            chip=f"{len(all_rows)}/{len(devices)}",
        )
        selected_indices = render_records_table(
            page_rows,
            TABLE_COLUMNS,
            key="device_table",
            selection=True,
            column_config=COLUMN_CONFIG,
            on_empty_reset=_reset_filters,
        )
        if all_rows:
            render_pagination(PAGE_KEY, total_pages, len(page_rows), len(all_rows), "thiết bị")
            render_table_export(
                all_rows,
                TABLE_COLUMNS,
                "equipment_export.csv",
                key="device_export_visible",
            )

        selected_rows = [page_rows[index] for index in selected_indices if 0 <= index < len(page_rows)]
        if selected_rows:
            selected_ids = [row["Mã thiết bị"] for row in selected_rows]
            render_bulk_action_bar(
                len(selected_rows),
                len(page_rows),
                selected_rows,
                TABLE_COLUMNS,
                "equipment_export.csv",
                "device_bulk_delete",
                lambda: open_dialog("bulk_delete", device_ids=selected_ids),
                "device_export_selected",
                extra_action=(
                    "Đặt trạng thái",
                    "device_bulk_status",
                    lambda: open_dialog("bulk_status", device_ids=selected_ids),
                ),
            )

        if len(selected_rows) == 1:
            selected_row = selected_rows[0]
            device_id = selected_row["Mã thiết bị"]
            render_row_action_bar(
                f'Đang chọn <strong>{device_id}</strong> · {selected_row["Tên thiết bị"]} · '
                f'{selected_row["Trạng thái"]}',
                [
                    ("Xem", "device_action_view", lambda: open_dialog("view", device_id=device_id), ""),
                    ("Sửa", "device_action_edit", lambda: open_dialog("edit", device_id=device_id), ""),
                    ("Xóa", "device_action_delete", lambda: open_dialog("delete", device_id=device_id), ""),
                ],
            )
        elif len(selected_rows) > 1:
            render_hint(
                "Đang chọn nhiều thiết bị — dùng thanh thao tác hàng loạt ở trên để xuất hoặc xóa.",
                "list",
            )
        else:
            render_hint(
                "Bấm vào một dòng trong bảng để xem, sửa hoặc xóa thiết bị.",
                "list",
            )

    render_pending_dialog(
        {
            "create": lambda payload: _dialog_create(analysis),
            "view": lambda payload: _dialog_view(payload, analysis),
            "edit": lambda payload: _dialog_edit(payload, analysis),
            "delete": lambda payload: _dialog_delete(payload, analysis),
            "bulk_delete": lambda payload: _dialog_bulk_delete(payload, analysis),
            "bulk_status": lambda payload: _dialog_bulk_status(payload, analysis),
        }
    )
