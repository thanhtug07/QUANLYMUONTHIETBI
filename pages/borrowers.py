# -*- coding: utf-8 -*-
"""
pages/borrowers.py — TRANG NGƯỜI MƯỢN (CRUD)
============================================
Quản lý danh sách người mượn trong `data/borrowers.csv`.

Cột "Lượt mượn" và "Đang mượn" là số đếm THẬT suy ra từ phiếu mượn
(tổng lượt và số phiếu đang ở trạng thái borrowing). Kiểm tra dữ liệu dùng
`validators.validate_candidate_borrower`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st
from cleaners import BORROWER_COLUMNS, normalize_phone, normalize_text

import data_store
import main
import validators
from pages.common import (
    BORROWER_SORT_OPTIONS,
    borrower_detail_rows,
    borrower_rows,
    count_by,
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

#: Cột hiển thị của bảng người mượn.
TABLE_COLUMNS: List[str] = ["Mã sinh viên", "Họ tên", "Lớp", "Điện thoại", "Lượt mượn", "Đang mượn"]

COLUMN_CONFIG: Dict[str, Any] = {
    "Mã sinh viên": st.column_config.TextColumn("Mã sinh viên", width="small"),
    "Họ tên": st.column_config.TextColumn("Họ tên", width="medium"),
    "Lớp": st.column_config.TextColumn("Lớp", width="small"),
    "Điện thoại": st.column_config.TextColumn("Điện thoại", width="small"),
    "Lượt mượn": st.column_config.NumberColumn("Lượt mượn", width="small"),
    "Đang mượn": st.column_config.NumberColumn("Đang mượn", width="small"),
}

FILTER_KEYS: List[str] = ["borrower_search", "borrower_class", "borrower_sort"]

SORT_FIELDS: Dict[str, str] = {
    "Mã sinh viên": "borrower_id",
    "Họ tên": "name",
    "Lớp": "class_name",
    "Lượt mượn": "borrow_count",
}

#: Khoá phân trang của bảng người mượn.
PAGE_KEY = "borrower_page"


def _reset_filters() -> None:
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)
    st.session_state.pop(PAGE_KEY, None)
    st.rerun()


def _class_options(borrowers: List[Dict[str, Any]]) -> List[str]:
    """Danh sách lớp có thật trong dữ liệu (sắp xếp) + lựa chọn 'Tất cả'."""
    classes = sorted(
        {
            normalize_text(borrower.get("class_name"))
            for borrower in borrowers
            if normalize_text(borrower.get("class_name"))
        }
    )
    return ["Tất cả", *classes]


def _render_toolbar(borrowers: List[Dict[str, Any]]) -> Dict[str, Any]:
    with st.container(border=True, key="borrower_filter_row"):
        pre_search = str(st.session_state.get("borrower_search", ""))
        pre_class = str(st.session_state.get("borrower_class", "Tất cả"))
        pre_sort = str(st.session_state.get("borrower_sort", "Mã sinh viên"))
        active = (
            (1 if pre_search.strip() else 0)
            + (1 if pre_class != "Tất cả" else 0)
            + (1 if pre_sort not in ("", "Mã sinh viên") else 0)
        )
        card_header(
            "Tìm kiếm & lọc",
            "Áp dụng ngay cho bảng người mượn bên dưới.",
            chip=f"{active} bộ lọc" if active else "",
        )
        columns = st.columns([2.1, 1.3, 1.3, 1.0], gap="medium", vertical_alignment="bottom")
        with columns[0]:
            search = st.text_input(
                "Tìm kiếm",
                placeholder="Tìm mã, họ tên, lớp hoặc SĐT…",
                key="borrower_search",
            )
        with columns[1]:
            class_filter = st.selectbox("Lớp", _class_options(borrowers), index=0, key="borrower_class")
        with columns[2]:
            sort = st.selectbox("Sắp xếp theo", BORROWER_SORT_OPTIONS, index=0, key="borrower_sort")
        with columns[3]:
            st.button(
                "Đặt lại",
                key="borrower_reset",
                width="stretch",
                on_click=_reset_filters,
                help="Xoá toàn bộ điều kiện lọc.",
            )
    return {"search": search, "class_filter": class_filter, "sort": sort}


def _active_counts(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """Số phiếu đang mượn theo người mượn (status borrowing, đúng như dữ liệu)."""
    active = [
        record for record in records if str(record.get("status", "")).strip() == "borrowing"
    ]
    return count_by(active, "borrower_id")


def _apply_filters(
    borrowers: List[Dict[str, Any]],
    borrow_counts: Dict[str, int],
    filters: Dict[str, Any],
) -> List[Dict[str, Any]]:
    query = str(filters["search"]).strip().lower()
    result = [
        borrower
        for borrower in borrowers
        if (
            filters["class_filter"] == "Tất cả"
            or normalize_text(borrower.get("class_name")) == filters["class_filter"]
        )
        and (
            not query
            or query in normalize_text(borrower.get("borrower_id", "")).lower()
            or query in normalize_text(borrower.get("name", "")).lower()
            or query in normalize_text(borrower.get("class_name", "")).lower()
            or query in normalize_phone(borrower.get("phone", "")).lower()
        )
    ]

    field = SORT_FIELDS.get(str(filters["sort"]), "borrower_id")
    if field == "borrow_count":
        return sorted(
            result,
            key=lambda borrower: borrow_counts.get(str(borrower.get("borrower_id", "")).strip(), 0),
            reverse=True,
        )
    return sorted(result, key=lambda borrower: str(borrower.get(field, "")).lower())


def _find_borrower(borrowers: List[Dict[str, Any]], borrower_id: str) -> Optional[Dict[str, Any]]:
    target = str(borrower_id).strip().upper()
    for borrower in borrowers:
        if str(borrower.get("borrower_id", "")).strip().upper() == target:
            return borrower
    return None


def _borrower_form(analysis: Dict[str, Any], borrower: Optional[Dict[str, Any]]) -> None:
    borrowers: List[Dict[str, Any]] = analysis.get("borrowers", [])
    editing = borrower is not None
    existing_classes = [option for option in _class_options(borrowers) if option != "Tất cả"]

    default_id = (
        str(borrower.get("borrower_id", "")).strip()
        if editing
        else data_store.next_sequential_id(borrowers, "borrower_id", "SV")
    )

    with st.form("borrower_form"):
        form_section("Thông tin người mượn", "Mã sinh viên được gợi ý từ danh sách hiện có.")
        first_row = st.columns([1, 2], gap="medium")
        borrower_id = first_row[0].text_input(
            "Mã sinh viên",
            value=default_id,
            # Khoá mã khi sửa (xem chú thích tương tự ở trang Phiếu mượn).
            disabled=editing,
        )
        name = first_row[1].text_input(
            "Họ tên", value=str(borrower.get("name", "")) if editing else ""
        )

        form_section("Đơn vị", "Lớp / phòng ban dùng để nhóm thống kê.")
        second_row = st.columns([1.4, 1], gap="medium")
        class_name = second_row[0].text_input(
            "Lớp / phòng ban",
            value=str(borrower.get("class_name", "")) if editing else "",
            help=(
                f"Lớp đang có trong dữ liệu: {', '.join(existing_classes)}"
                if existing_classes
                else "Chưa có lớp nào trong dữ liệu."
            ),
        )
        phone = second_row[1].text_input(
            "Điện thoại",
            value=str(borrower.get("phone", "") or "") if editing else "",
            placeholder="09xxxxxxxx",
            help="Không bắt buộc. Nếu nhập phải đủ 10 số, bắt đầu bằng 0.",
        )

        cancel_col, submit_col = st.columns(2, gap="medium")
        cancelled = cancel_col.form_submit_button("Huỷ", width="stretch")
        submitted = submit_col.form_submit_button(
            "Lưu thay đổi" if editing else "Thêm người mượn", type="primary", width="stretch"
        )

    if cancelled:
        close_dialog()
        return
    if not submitted:
        return

    candidate = {
        "borrower_id": str(borrower_id).strip().upper(),
        "name": str(name).strip(),
        "class_name": str(class_name).strip(),
        "phone": normalize_phone(phone),
    }

    errors = validators.validate_candidate_borrower(candidate, borrowers, editing=editing)
    if errors:
        validation_summary(errors)
        return

    if editing:
        data_store.update_row(
            main.BORROWERS_CSV, BORROWER_COLUMNS, "borrower_id", candidate["borrower_id"], candidate
        )
        set_flash(f"Đã cập nhật người mượn {candidate['borrower_id']}.")
    else:
        data_store.insert_row(main.BORROWERS_CSV, BORROWER_COLUMNS, candidate)
        set_flash(f"Đã thêm người mượn {candidate['borrower_id']}.")
    clear_data_cache()
    close_dialog()


def _dialog_view(payload: Dict[str, Any], analysis: Dict[str, Any]) -> None:
    borrower = _find_borrower(analysis.get("borrowers", []), payload.get("borrower_id", ""))
    if borrower is None:
        detail_dialog(
            "Không tìm thấy người mượn", [("Mã sinh viên", str(payload.get("borrower_id", "")))]
        )
        return
    records = analysis.get("records", [])
    borrower_id = str(borrower.get("borrower_id", "")).strip()
    detail_dialog(
        f"Người mượn {borrower_id}",
        borrower_detail_rows(
            borrower,
            count_by(records, "borrower_id").get(borrower_id, 0),
            _active_counts(records).get(borrower_id, 0),
        ),
    )


def _dialog_edit(payload: Dict[str, Any], analysis: Dict[str, Any]) -> None:
    borrower = _find_borrower(analysis.get("borrowers", []), payload.get("borrower_id", ""))
    if borrower is None:
        detail_dialog(
            "Không tìm thấy người mượn", [("Mã sinh viên", str(payload.get("borrower_id", "")))]
        )
        return
    form_dialog(
        f"Sửa người mượn {borrower.get('borrower_id', '')}",
        lambda: _borrower_form(analysis, borrower),
    )


def _dialog_create(analysis: Dict[str, Any]) -> None:
    form_dialog("Thêm người mượn", lambda: _borrower_form(analysis, None))


def _dialog_delete(payload: Dict[str, Any], analysis: Dict[str, Any]) -> None:
    borrower = _find_borrower(analysis.get("borrowers", []), payload.get("borrower_id", ""))
    if borrower is None:
        detail_dialog(
            "Không tìm thấy người mượn", [("Mã sinh viên", str(payload.get("borrower_id", "")))]
        )
        return

    records = analysis.get("records", [])
    borrower_id = str(borrower.get("borrower_id", "")).strip()
    borrow_count = count_by(records, "borrower_id").get(borrower_id, 0)
    message = (
        f"Bạn có chắc muốn xóa người mượn {borrower_id}? Thao tác này không thể hoàn tác."
    )
    if borrow_count:
        message += (
            f" Người này đang có {borrow_count} phiếu mượn — các phiếu đó được giữ nguyên "
            "và sẽ được báo là dữ liệu cần kiểm tra."
        )

    def _confirm() -> None:
        removed = data_store.delete_row(
            main.BORROWERS_CSV, BORROWER_COLUMNS, "borrower_id", borrower_id
        )
        clear_data_cache()
        if removed:
            set_flash(f"Đã xóa người mượn {borrower_id}.")
        else:
            set_flash("Không tìm thấy người mượn để xóa.")

    confirm_dialog(
        "Xóa người mượn",
        message,
        "Xóa người mượn",
        _confirm,
        detail_rows=borrower_detail_rows(
            borrower, borrow_count, _active_counts(records).get(borrower_id, 0)
        ),
    )


def _dialog_bulk_delete(payload: Dict[str, Any], analysis: Dict[str, Any]) -> None:
    borrower_ids = [str(value).strip() for value in payload.get("borrower_ids", []) if str(value).strip()]
    if not borrower_ids:
        detail_dialog("Chưa chọn người mượn", [("Số mục chọn", "0")])
        return

    records = analysis.get("records", [])
    borrow_counts = count_by(records, "borrower_id")
    linked_count = sum(1 for borrower_id in borrower_ids if borrow_counts.get(borrower_id, 0))
    existing_ids = {
        str(borrower.get("borrower_id", "")).strip()
        for borrower in analysis.get("borrowers", [])
    }

    def _confirm() -> None:
        removed = data_store.delete_rows(main.BORROWERS_CSV, BORROWER_COLUMNS, "borrower_id", borrower_ids)
        clear_data_cache()
        if removed == len(borrower_ids):
            set_flash(f"Đã xóa {removed} người mượn.")
        else:
            set_flash(f"Đã xóa {removed}/{len(borrower_ids)} người mượn; một số bản ghi không còn tồn tại.")

    confirm_dialog(
        "Xóa nhiều người mượn",
        (
            f"Xóa {len(borrower_ids)} người mượn? Hành động này sẽ xóa các bản ghi đã chọn. "
            "Các phiếu mượn liên quan được giữ nguyên và sẽ được báo là dữ liệu cần kiểm tra."
        ),
        "Xóa người mượn đã chọn",
        _confirm,
        detail_rows=[
            ("Số người mượn đã chọn", str(len(borrower_ids))),
            ("Mã sinh viên", ", ".join(borrower_ids[:12]) + ("..." if len(borrower_ids) > 12 else "")),
            ("Có phiếu mượn liên quan", str(linked_count)),
            ("Bản ghi còn tồn tại", str(sum(1 for value in borrower_ids if value in existing_ids))),
        ],
    )


def render(analysis: Dict[str, Any]) -> None:
    borrowers: List[Dict[str, Any]] = analysis.get("borrowers", [])
    records: List[Dict[str, Any]] = analysis.get("records", [])
    borrow_counts = count_by(records, "borrower_id")
    active_counts = _active_counts(records)

    page_header(
        "Người mượn",
        "Quản lý danh sách người sử dụng thiết bị.",
        meta=f"{len(borrowers)} người mượn trong danh mục.",
        action_label="+ Thêm người mượn",
        action_key="borrower_create",
        on_action=lambda: open_dialog("create"),
        action_help="Mở form thêm người mượn mới.",
    )

    render_flash()

    if render_first_run_guide(analysis):
        return

    filters = _render_toolbar(borrowers)
    filtered = _apply_filters(borrowers, borrow_counts, filters)
    all_rows = borrower_rows(filtered, borrow_counts, active_counts)
    page_rows, total_pages = paginate(all_rows, PAGE_KEY)

    with st.container(border=True):
        card_header(
            "Danh sách người mượn",
            "Chọn một dòng để xem, sửa hoặc xóa người mượn.",
            chip=f"{len(all_rows)}/{len(borrowers)}",
        )
        selected_indices = render_records_table(
            page_rows,
            TABLE_COLUMNS,
            key="borrower_table",
            selection=True,
            column_config=COLUMN_CONFIG,
            on_empty_reset=_reset_filters,
        )
        if all_rows:
            render_pagination(PAGE_KEY, total_pages, len(page_rows), len(all_rows), "người mượn")
            render_table_export(
                all_rows,
                TABLE_COLUMNS,
                "borrowers_export.csv",
                key="borrower_export_visible",
            )

        selected_rows = [page_rows[index] for index in selected_indices if 0 <= index < len(page_rows)]
        if selected_rows:
            selected_ids = [row["Mã sinh viên"] for row in selected_rows]
            render_bulk_action_bar(
                len(selected_rows),
                len(page_rows),
                selected_rows,
                TABLE_COLUMNS,
                "borrowers_export.csv",
                "borrower_bulk_delete",
                lambda: open_dialog("bulk_delete", borrower_ids=selected_ids),
                "borrower_export_selected",
            )

        if len(selected_rows) == 1:
            selected_row = selected_rows[0]
            borrower_id = selected_row["Mã sinh viên"]
            render_row_action_bar(
                f'Đang chọn <strong>{borrower_id}</strong> · {selected_row["Họ tên"]} · '
                f'{selected_row["Lớp"]}',
                [
                    ("Xem", "borrower_action_view", lambda: open_dialog("view", borrower_id=borrower_id), ""),
                    ("Sửa", "borrower_action_edit", lambda: open_dialog("edit", borrower_id=borrower_id), ""),
                    ("Xóa", "borrower_action_delete", lambda: open_dialog("delete", borrower_id=borrower_id), ""),
                ],
            )
        elif len(selected_rows) > 1:
            render_hint(
                "Đang chọn nhiều người mượn — dùng thanh thao tác hàng loạt ở trên để xuất hoặc xóa.",
                "list",
            )
        else:
            render_hint(
                "Bấm vào một dòng trong bảng để xem, sửa hoặc xóa người mượn.",
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
