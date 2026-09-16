# -*- coding: utf-8 -*-
"""
pages/csv_data.py — TRANG DỮ LIỆU CSV
=====================================
Quản lý dữ liệu đầu vào: trạng thái từng file, preview dữ liệu thô, kết quả
làm sạch/kiểm tra và thay thế file bằng bản tải lên (có xác nhận).

Không có database, không cloud: ghi trực tiếp vào `data/*.csv` qua
`data_store` (atomic). File tải lên PHẢI có đủ cột chuẩn của cleaners — thiếu
cột thì hệ thống từ chối thay vì ghi dữ liệu sai cấu trúc.
"""
from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Sequence, Tuple

import streamlit as st
from cleaners import normalize_text

import data_store
import main
from pages.common import CSV_FILES, CSV_LABELS
from ui.app_shell import clear_data_cache
from ui.badges import status_badge
from ui.dialogs import confirm_dialog, open_dialog, render_pending_dialog
from ui.forms import info_notice, render_flash, set_flash
from ui.layout import card_header, page_header
from ui.metrics import MetricCard, render_kpi_grid
from ui.states import render_empty_state, render_hint
from utils.helpers import esc, format_timestamp

#: Khoá page -> tên bảng trong error records của pipeline.
TABLE_NAMES: Dict[str, str] = {
    "devices": "devices",
    "borrowers": "borrowers",
    "records": "borrow_records",
}

#: Số dòng preview của mỗi file.
PREVIEW_ROWS = 5

#: Số lỗi tối đa liệt kê cho mỗi file.
ERROR_LIMIT = 5


def _path_for(key: str):
    return {
        "devices": main.DEVICES_CSV,
        "borrowers": main.BORROWERS_CSV,
        "records": main.RECORDS_CSV,
    }[key]


def _columns_for(key: str) -> List[str]:
    for file_key, _, columns in CSV_FILES:
        if file_key == key:
            return list(columns)
    return []


def _parse_upload(data: bytes, columns: Sequence[str]) -> Tuple[List[Dict[str, str]], List[str]]:
    """
    Đọc file tải lên thành các dòng theo cột chuẩn.

    Trả về (rows, missing_columns): nếu thiếu cột bắt buộc thì trả về danh sách
    rỗng kèm tên các cột còn thiếu (UI hiển thị lỗi thay vì ghi file sai).
    """
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        return [], list(columns)

    index_by_name = {normalize_text(cell).lower(): position for position, cell in enumerate(header)}
    missing = [column for column in columns if column.lower() not in index_by_name]
    if missing:
        return [], missing

    rows: List[Dict[str, str]] = []
    for raw in reader:
        if not any(cell.strip() for cell in raw):
            continue
        rows.append(
            {
                column: (raw[index_by_name[column.lower()]] if index_by_name[column.lower()] < len(raw) else "")
                for column in columns
            }
        )
    return rows, []


def _render_errors(key: str, errors: Sequence[Dict[str, Any]]) -> None:
    table_name = TABLE_NAMES.get(key, key)
    relevant = [error for error in errors if str(error.get("table", "")) == table_name]
    if not relevant:
        st.markdown(
            f'<div class="meta-row"><span class="meta-label">Kết quả kiểm tra</span>'
            f'<span class="meta-value">{status_badge("Hợp lệ")}</span></div>',
            unsafe_allow_html=True,
        )
        return

    items = "".join(
        f'<li>dòng {esc(error.get("row", "?"))} · trường <strong>{esc(error.get("field", ""))}</strong>: '
        f'{esc(error.get("error", ""))}</li>'
        for error in list(relevant)[:ERROR_LIMIT]
    )
    st.markdown(
        f'<div class="notice error">'
        f'<div class="notice-title">{len(relevant)} bản ghi cần kiểm tra '
        f'{status_badge("Dữ liệu lỗi")}</div>'
        f'<ul class="notice-list">{items}</ul></div>',
        unsafe_allow_html=True,
    )
    remaining = len(relevant) - ERROR_LIMIT
    if remaining > 0:
        st.markdown(
            f'<div class="table-footnote">Còn {remaining} bản ghi lỗi khác — xem đầy đủ ở trang Cảnh báo.</div>',
            unsafe_allow_html=True,
        )


def _render_uploader(key: str) -> None:
    """Khu vực thay thế file bằng bản tải lên (có kiểm tra cột + xác nhận)."""
    columns = _columns_for(key)
    filename = CSV_LABELS.get(key, key)
    uploaded = st.file_uploader(
        f"Tải lên {filename} để thay thế",
        type=["csv"],
        key=f"csv_upload_{key}",
        help=f"File phải có đủ các cột: {', '.join(columns)}.",
    )
    if uploaded is None:
        return

    rows, missing = _parse_upload(uploaded.getvalue(), columns)
    if missing:
        info_notice(
            "File tải lên không đúng cấu trúc.",
            f"Thiếu các cột: {', '.join(missing)}. Cần đủ các cột: {', '.join(columns)}.",
        )
        return

    if not rows:
        info_notice("File tải lên không có dòng dữ liệu nào.", "Kiểm tra lại nội dung file CSV.")
        return

    st.markdown(
        f'<div class="meta-row"><span class="meta-label">Xem trước</span>'
        f'<span class="meta-value">{len(rows)} dòng · {len(columns)} cột</span></div>',
        unsafe_allow_html=True,
    )
    st.dataframe(rows[:PREVIEW_ROWS], width="stretch", hide_index=True, key=f"csv_preview_{key}")

    if st.button(
        f"Ghi đè {filename}",
        key=f"csv_replace_{key}",
        type="primary",
        width="stretch",
        help="Ghi nội dung đang xem trước vào file dữ liệu (có bước xác nhận).",
    ):
        open_dialog("csv_replace", target=key, rows=rows, filename=filename)


def _render_file_card(
    key: str, analysis: Dict[str, Any], errors: Sequence[Dict[str, Any]]
) -> None:
    columns = _columns_for(key)
    path = _path_for(key)
    raw_rows = data_store.read_raw_rows(path, columns)
    raw_count = data_store.count_rows(path)
    cleaned_counts = {
        "devices": len(analysis.get("devices", [])),
        "borrowers": len(analysis.get("borrowers", [])),
        "records": len(analysis.get("records", [])),
    }

    with st.container(border=True):
        card_header(
            CSV_LABELS.get(key, key),
            f"Cột chuẩn: {', '.join(columns)}",
            chip=f"{raw_count} dòng",
        )

        meta_items = [
            ("Dòng dữ liệu (thô)", str(raw_count)),
            ("Dòng hợp lệ sau làm sạch", str(cleaned_counts.get(key, 0))),
            ("Cập nhật gần nhất", format_timestamp(data_store.last_modified(path))),
            ("Cột", str(len(columns))),
        ]
        meta_html = "".join(
            f'<div class="meta-item"><span class="meta-label">{esc(label)}</span>'
            f'<span class="meta-value">{esc(value)}</span></div>'
            for label, value in meta_items
        )
        st.markdown(f'<div class="meta-grid">{meta_html}</div>', unsafe_allow_html=True)

        _render_errors(key, errors)

        if raw_rows:
            with st.expander("Xem trước dữ liệu thô"):
                st.dataframe(
                    raw_rows[:PREVIEW_ROWS],
                    width="stretch",
                    hide_index=True,
                    key=f"csv_raw_{key}",
                )
        else:
            render_empty_state(
                "File chưa có dữ liệu.",
                "File rỗng hoặc chưa tồn tại trên đĩa.",
                "database",
                compact=True,
            )

        with st.expander("Thay thế bằng file tải lên"):
            _render_uploader(key)


def render(analysis: Dict[str, Any]) -> None:
    errors: List[Dict[str, Any]] = analysis.get("errors", [])
    total_rows = sum(data_store.count_rows(_path_for(key)) for key, _, _ in CSV_FILES)
    valid_rows = (
        len(analysis.get("devices", []))
        + len(analysis.get("borrowers", []))
        + len(analysis.get("records", []))
    )

    page_header(
        "Dữ liệu CSV",
        "Quản lý dữ liệu đầu vào của hệ thống.",
        meta=f"{len(CSV_FILES)} file dữ liệu · làm sạch và kiểm tra tự động khi nạp.",
    )

    render_flash()

    render_kpi_grid(
        [
            MetricCard("File dữ liệu", len(CSV_FILES), "devices · borrowers · borrow_records", "database"),
            MetricCard("Dòng dữ liệu", total_rows, "Đang có trên đĩa", "receipt"),
            MetricCard("Dòng hợp lệ", valid_rows, "Sau làm sạch", "box"),
            MetricCard(
                "Bản ghi cần kiểm tra",
                len(errors),
                "Hợp lệ toàn bộ" if not errors else "Xem chi tiết ở trang Cảnh báo",
                "alert",
            ),
        ]
    )

    render_hint(
        "Đây là nguồn dữ liệu duy nhất của hệ thống: mọi thao tác thêm/sửa/xóa ở các "
        "trang nghiệp vụ đều ghi trực tiếp vào ba file dưới đây.",
        "database",
    )

    for key, _, _ in CSV_FILES:
        _render_file_card(key, analysis, errors)

    render_pending_dialog({"csv_replace": lambda payload: _dialog_csv_replace(payload, analysis)})


def _dialog_csv_replace(payload: Dict[str, Any], analysis: Dict[str, Any]) -> None:
    key = str(payload.get("target", ""))
    rows: List[Dict[str, str]] = list(payload.get("rows", []))
    filename = str(payload.get("filename", CSV_LABELS.get(key, key)))
    columns = _columns_for(key)

    def _confirm() -> None:
        data_store.write_rows(_path_for(key), columns, rows)
        clear_data_cache()
        set_flash(f"Đã ghi đè {filename} bằng {len(rows)} dòng từ file tải lên.")

    confirm_dialog(
        f"Ghi đè {filename}",
        f"Toàn bộ nội dung hiện tại của {filename} sẽ được thay bằng {len(rows)} dòng vừa tải lên. "
        "Thao tác này không thể hoàn tác.",
        f"Ghi đè {filename}",
        _confirm,
        detail_rows=[
            ("File", filename),
            ("Số dòng mới", str(len(rows))),
            ("Cột ghi vào file", ", ".join(columns)),
        ],
    )
