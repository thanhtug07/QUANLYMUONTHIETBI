# -*- coding: utf-8 -*-
"""
pages/borrowing.py — TRANG PHIẾU MƯỢN (CRUD)
============================================
Module CRUD cho bảng trung tâm của nghiệp vụ: `data/borrow_records.csv`.

Luồng thao tác (không rời trang):
    chọn 1 dòng -> action bar (Xem / Sửa / Xóa) -> dialog tương ứng.

Ghi dữ liệu đi qua `data_store` (atomic, giữ nguyên mọi dòng khác) và kiểm tra
bằng `validators.validate_candidate_record` — UI không tự định nghĩa quy tắc
nghiệp vụ, cũng không tạo mã/số liệu ngẫu nhiên.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import statistics as stat_mod
import streamlit as st

import data_store
import main
import validators
from cleaners import RECORD_COLUMNS, parse_date
from pages.common import (
    RECORD_STATUS_CHOICES,
    RECORD_STATUS_FILTERS,
    choice_code,
    choice_index,
    choice_labels,
    filter_records,
    record_detail_rows,
    record_rows,
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
from ui.filters import TIME_OPTIONS
from ui.forms import (
    display_label,
    form_section,
    id_options,
    info_notice,
    option_index,
    render_flash,
    set_flash,
    validation_summary,
)
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
from utils.helpers import status_label, to_csv_date

#: Cột hiển thị của bảng phiếu mượn (toàn bộ đều là field thật của CSV).
TABLE_COLUMNS: List[str] = [
    "Mã phiếu",
    "Mã thiết bị",
    "Tên thiết bị",
    "Người mượn",
    "Lớp",
    "Ngày mượn",
    "Hạn trả",
    "Ngày trả",
    "Trạng thái",
]

COLUMN_CONFIG: Dict[str, Any] = {
    "Mã phiếu": st.column_config.TextColumn("Mã phiếu", width="small"),
    "Mã thiết bị": st.column_config.TextColumn("Mã thiết bị", width="small"),
    "Tên thiết bị": st.column_config.TextColumn("Tên thiết bị", width="medium"),
    "Người mượn": st.column_config.TextColumn("Người mượn", width="medium"),
    "Lớp": st.column_config.TextColumn("Lớp", width="small"),
}

#: Khoá session_state của các widget bộ lọc (để "Đặt lại" hoạt động thật).
FILTER_KEYS: List[str] = ["borrow_search", "borrow_status", "borrow_time"]

#: Khoá session_state của dòng đang chọn.
SELECTED_KEY = "borrow_selected_id"

#: Khoá phân trang của bảng phiếu mượn.
PAGE_KEY = "borrow_page"


# ----------------------------------------------------------------------
# Bộ lọc
# ----------------------------------------------------------------------

def _reset_filters() -> None:
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)
    st.session_state.pop(SELECTED_KEY, None)
    st.session_state.pop(PAGE_KEY, None)
    st.rerun()


def _render_toolbar(devices: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Toolbar lọc của bảng phiếu mượn: từ khoá / trạng thái / khoảng thời gian."""
    with st.container(border=True, key="borrow_filter_row"):
        pre_search = str(st.session_state.get("borrow_search", ""))
        pre_status = str(st.session_state.get("borrow_status", "Tất cả"))
        pre_time = str(st.session_state.get("borrow_time", "Tất cả"))
        active = (
            (1 if pre_search.strip() else 0)
            + (1 if pre_status != "Tất cả" else 0)
            + (1 if pre_time != "Tất cả" else 0)
        )
        card_header(
            "Bộ lọc",
            "Áp dụng ngay cho bảng phiếu mượn bên dưới.",
            chip=f"{active} bộ lọc" if active else "",
        )

        columns = st.columns([1.9, 1.15, 1.15, 0.9], gap="medium", vertical_alignment="bottom")
        with columns[0]:
            search = st.text_input(
                "Tìm kiếm",
                placeholder="Tìm mã phiếu, mã thiết bị, tên thiết bị hoặc người mượn…",
                key="borrow_search",
            )
        with columns[1]:
            status = st.selectbox("Trạng thái", RECORD_STATUS_FILTERS, index=0, key="borrow_status")
        with columns[2]:
            time_mode = st.selectbox("Khoảng thời gian", TIME_OPTIONS, index=0, key="borrow_time")
        with columns[3]:
            st.button(
                "Đặt lại",
                key="borrow_reset",
                width="stretch",
                on_click=_reset_filters,
                help="Xoá toàn bộ điều kiện lọc và bỏ dòng đang chọn.",
            )

    return {"search": search, "status": status, "time_mode": time_mode}


# ----------------------------------------------------------------------
# Form tạo / sửa
# ----------------------------------------------------------------------

def _find_record(records: List[Dict[str, Any]], borrow_id: str) -> Optional[Dict[str, Any]]:
    target = str(borrow_id).strip().upper()
    for record in records:
        if str(record.get("borrow_id", "")).strip().upper() == target:
            return record
    return None


def _record_form(analysis: Dict[str, Any], record: Optional[Dict[str, Any]]) -> None:
    """Form tạo/sửa phiếu mượn (đặt trong dialog)."""
    devices: List[Dict[str, Any]] = analysis.get("devices", [])
    borrowers: List[Dict[str, Any]] = analysis.get("borrowers", [])
    records: List[Dict[str, Any]] = analysis.get("records", [])
    editing = record is not None

    device_options = id_options(devices, "device_id", ("device_name", "category"))
    borrower_options = id_options(borrowers, "borrower_id", ("name", "class_name"))

    # Không thể tạo phiếu nếu danh mục thiếu: báo rõ thay vì render form rỗng.
    if not device_options or not borrower_options:
        info_notice(
            "Chưa thể tạo phiếu mượn.",
            "Cần có ít nhất một thiết bị và một người mượn trong dữ liệu "
            "(xem trang Thiết bị / Người mượn).",
        )
        return

    default_id = (
        str(record.get("borrow_id", "")).strip()
        if editing
        else data_store.next_sequential_id(records, "borrow_id", "PM")
    )
    default_status = (
        choice_index(RECORD_STATUS_CHOICES, record.get("status", "")) if editing else 0
    )
    borrow_default = None
    due_default = None
    return_default = None
    if editing:
        borrow_default = parse_date(record.get("borrow_date"))
        due_default = parse_date(record.get("due_date"))
        return_default = parse_date(record.get("return_date"))
    else:
        borrow_default = date.today()

    with st.form("borrow_record_form"):
        form_section("Thông tin phiếu", "Mã phiếu được gợi ý từ dữ liệu hiện có, có thể sửa.")
        first_row = st.columns([1, 1.6, 1.6], gap="medium")
        borrow_id = first_row[0].text_input("Mã phiếu", value=default_id)
        device_id = first_row[1].selectbox(
            "Thiết bị",
            options=[value for value, _ in device_options],
            format_func=lambda value: display_label(device_options, value),
            index=option_index(device_options, str(record.get("device_id", "")) if editing else ""),
            key="borrow_form_device",
        )
        borrower_id = first_row[2].selectbox(
            "Người mượn",
            options=[value for value, _ in borrower_options],
            format_func=lambda value: display_label(borrower_options, value),
            index=option_index(
                borrower_options, str(record.get("borrower_id", "")) if editing else ""
            ),
            key="borrow_form_borrower",
        )

        form_section("Thời gian", "Ô ngày trả để trống khi thiết bị chưa được trả.")
        second_row = st.columns(3, gap="medium")
        borrow_date = second_row[0].date_input("Ngày mượn", value=borrow_default)
        due_date = second_row[1].date_input("Hạn trả", value=due_default)
        return_date = second_row[2].date_input("Ngày trả", value=return_default)

        form_section("Trạng thái", "Quy tắc trạng thái được kiểm tra khi lưu.")
        status_choice = st.selectbox(
            "Trạng thái phiếu",
            choice_labels(RECORD_STATUS_CHOICES),
            index=default_status,
            key="borrow_form_status",
        )

        cancel_col, submit_col = st.columns(2, gap="medium")
        cancelled = cancel_col.form_submit_button("Huỷ", width="stretch")
        submitted = submit_col.form_submit_button(
            "Lưu thay đổi" if editing else "Tạo phiếu", type="primary", width="stretch"
        )

    if cancelled:
        close_dialog()
        return

    if not submitted:
        return

    candidate = {
        "borrow_id": str(borrow_id).strip().upper(),
        "borrower_id": str(borrower_id).strip(),
        "device_id": str(device_id).strip(),
        "borrow_date": borrow_date.isoformat() if borrow_date else "",
        "due_date": due_date.isoformat() if due_date else "",
        "return_date": return_date.isoformat() if return_date else "",
        "status": choice_code(RECORD_STATUS_CHOICES, status_choice),
    }

    errors = validators.validate_candidate_record(
        candidate, devices, borrowers, records, editing=editing
    )
    if errors:
        validation_summary(errors)
        return

    # Ghi ra CSV theo đúng định dạng ngày dd/mm/yyyy đang dùng trong file dữ liệu;
    # giá trị vẫn là ISO ở bước validation phía trên (khớp bản ghi đã làm sạch).
    row = {
        **candidate,
        "borrow_date": to_csv_date(candidate["borrow_date"]),
        "due_date": to_csv_date(candidate["due_date"]),
        "return_date": to_csv_date(candidate["return_date"]),
    }
    if editing:
        data_store.update_row(
            main.RECORDS_CSV, RECORD_COLUMNS, "borrow_id", row["borrow_id"], row
        )
        set_flash(f"Đã cập nhật phiếu mượn {row['borrow_id']}.")
    else:
        data_store.insert_row(main.RECORDS_CSV, RECORD_COLUMNS, row)
        set_flash(f"Đã tạo phiếu mượn {row['borrow_id']}.")
    clear_data_cache()
    close_dialog()


# ----------------------------------------------------------------------
# Dialog handlers
# ----------------------------------------------------------------------

def _dialog_view(payload: Dict[str, Any], analysis: Dict[str, Any]) -> None:
    records = analysis.get("records", [])
    record = _find_record(records, payload.get("borrow_id", ""))
    if record is None:
        detail_dialog("Không tìm thấy phiếu mượn", [("Mã phiếu", str(payload.get("borrow_id", "")))])
        return
    stats = stat_mod.compute_all(
        analysis.get("devices", []),
        analysis.get("borrowers", []),
        records,
        today=date.today(),
    )
    detail_dialog(
        f"Phiếu mượn {record.get('borrow_id', '')}",
        record_detail_rows(record, stats.get("devices_by_id", {}), stats.get("borrowers_by_id", {})),
        badges=[status_label(record.get("status", ""))],
    )


def _dialog_edit(payload: Dict[str, Any], analysis: Dict[str, Any]) -> None:
    record = _find_record(analysis.get("records", []), payload.get("borrow_id", ""))
    if record is None:
        detail_dialog("Không tìm thấy phiếu mượn", [("Mã phiếu", str(payload.get("borrow_id", "")))])
        return
    form_dialog(f"Sửa phiếu mượn {record.get('borrow_id', '')}", lambda: _record_form(analysis, record))


def _dialog_create(analysis: Dict[str, Any]) -> None:
    form_dialog("Tạo phiếu mượn", lambda: _record_form(analysis, None))


def _dialog_delete(payload: Dict[str, Any], analysis: Dict[str, Any]) -> None:
    record = _find_record(analysis.get("records", []), payload.get("borrow_id", ""))
    if record is None:
        detail_dialog("Không tìm thấy phiếu mượn", [("Mã phiếu", str(payload.get("borrow_id", "")))])
        return

    def _confirm() -> None:
        removed = data_store.delete_row(
            main.RECORDS_CSV, RECORD_COLUMNS, "borrow_id", str(record.get("borrow_id", ""))
        )
        clear_data_cache()
        if removed:
            set_flash(f"Đã xóa phiếu mượn {record.get('borrow_id', '')}.")
        else:
            set_flash("Không tìm thấy phiếu mượn để xóa.")

    confirm_dialog(
        "Xóa phiếu mượn",
        f"Bạn có chắc muốn xóa phiếu mượn {record.get('borrow_id', '')}? Thao tác này không thể hoàn tác.",
        "Xóa phiếu mượn",
        _confirm,
        detail_rows=record_detail_rows(
            record,
            stat_mod.build_devices_by_id(analysis.get("devices", [])),
            stat_mod.build_borrowers_by_id(analysis.get("borrowers", [])),
        ),
    )


def _dialog_bulk_delete(payload: Dict[str, Any], analysis: Dict[str, Any]) -> None:
    borrow_ids = [str(value).strip() for value in payload.get("borrow_ids", []) if str(value).strip()]
    if not borrow_ids:
        detail_dialog("Chưa chọn phiếu mượn", [("Số mục chọn", "0")])
        return

    existing_ids = {
        str(record.get("borrow_id", "")).strip()
        for record in analysis.get("records", [])
    }

    def _confirm() -> None:
        removed = data_store.delete_rows(main.RECORDS_CSV, RECORD_COLUMNS, "borrow_id", borrow_ids)
        clear_data_cache()
        if removed == len(borrow_ids):
            set_flash(f"Đã xóa {removed} phiếu mượn.")
        else:
            set_flash(f"Đã xóa {removed}/{len(borrow_ids)} phiếu mượn; một số bản ghi không còn tồn tại.")

    confirm_dialog(
        "Xóa nhiều phiếu mượn",
        f"Xóa {len(borrow_ids)} phiếu mượn? Hành động này sẽ xóa các bản ghi đã chọn.",
        "Xóa phiếu đã chọn",
        _confirm,
        detail_rows=[
            ("Số phiếu đã chọn", str(len(borrow_ids))),
            ("Mã phiếu", ", ".join(borrow_ids[:12]) + ("..." if len(borrow_ids) > 12 else "")),
            ("Bản ghi còn tồn tại", str(sum(1 for value in borrow_ids if value in existing_ids))),
        ],
    )


# ----------------------------------------------------------------------
# Render page
# ----------------------------------------------------------------------

def render(analysis: Dict[str, Any]) -> None:
    base_records: List[Dict[str, Any]] = analysis.get("records", [])
    devices = analysis.get("devices", [])
    borrowers = analysis.get("borrowers", [])

    can_create = bool(devices) and bool(borrowers)
    page_header(
        "Phiếu mượn",
        "Theo dõi và quản lý các phiếu mượn thiết bị.",
        meta=f"{len(base_records)} phiếu mượn trong hệ thống.",
        action_label="+ Tạo phiếu mượn" if can_create else "",
        action_key="borrow_create",
        on_action=lambda: open_dialog("create"),
        action_help="Mở form tạo phiếu mượn mới.",
    )

    render_flash()

    if render_first_run_guide(analysis):
        return

    filters = _render_toolbar(devices)
    devices_by_id = stat_mod.build_devices_by_id(devices)
    borrowers_by_id = stat_mod.build_borrowers_by_id(borrowers)

    filtered = filter_records(
        base_records,
        search=filters["search"],
        status=filters["status"],
        time_mode=filters["time_mode"],
        devices_by_id=devices_by_id,
        borrowers_by_id=borrowers_by_id,
    )
    all_rows = record_rows(filtered, devices_by_id, borrowers_by_id)
    page_rows, total_pages = paginate(all_rows, PAGE_KEY)

    with st.container(border=True):
        card_header(
            "Danh sách phiếu mượn",
            "Chọn một dòng để xem, sửa hoặc xóa phiếu.",
            chip=f"{len(all_rows)}/{len(base_records)}",
        )
        selected_indices = render_records_table(
            page_rows,
            TABLE_COLUMNS,
            key="borrow_table",
            selection=True,
            column_config=COLUMN_CONFIG,
            on_empty_reset=_reset_filters,
        )

        if all_rows:
            render_pagination(PAGE_KEY, total_pages, len(page_rows), len(all_rows), "phiếu mượn")
            render_table_export(
                all_rows,
                TABLE_COLUMNS,
                "borrowing_export.csv",
                key="borrow_export_visible",
            )

        selected_rows = [page_rows[index] for index in selected_indices if 0 <= index < len(page_rows)]
        if selected_rows:
            selected_ids = [row["Mã phiếu"] for row in selected_rows]
            render_bulk_action_bar(
                len(selected_rows),
                len(page_rows),
                selected_rows,
                TABLE_COLUMNS,
                "borrowing_export.csv",
                "borrow_bulk_delete",
                lambda: open_dialog("bulk_delete", borrow_ids=selected_ids),
                "borrow_export_selected",
            )

        if len(selected_rows) == 1:
            selected_row = selected_rows[0]
            borrow_id = selected_row["Mã phiếu"]
            st.session_state[SELECTED_KEY] = borrow_id
            render_row_action_bar(
                f'Đang chọn <strong>{borrow_id}</strong> · {selected_row["Tên thiết bị"]} · '
                f'{selected_row["Người mượn"]}',
                [
                    ("Xem", "borrow_action_view", lambda: open_dialog("view", borrow_id=borrow_id), ""),
                    ("Sửa", "borrow_action_edit", lambda: open_dialog("edit", borrow_id=borrow_id), ""),
                    ("Xóa", "borrow_action_delete", lambda: open_dialog("delete", borrow_id=borrow_id), ""),
                ],
            )
        elif len(selected_rows) > 1:
            render_hint(
                "Đang chọn nhiều phiếu mượn — dùng thanh thao tác hàng loạt ở trên để xuất hoặc xóa.",
                "list",
            )
        else:
            render_hint(
                "Bấm vào một dòng trong bảng để xem, sửa hoặc xóa phiếu mượn.",
                "list",
            )

    render_pending_dialog(
        {
            "create": lambda payload: _dialog_create(analysis),
            "view": lambda payload: _dialog_view(payload, analysis),
            "edit": lambda payload: _dialog_edit(payload, analysis),
            "delete": lambda payload: _dialog_delete(payload, analysis),
            "bulk_delete": lambda payload: _dialog_bulk_delete(payload, analysis),
        }
    )
