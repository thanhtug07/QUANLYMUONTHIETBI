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
from ui.dialogs import close_dialog, confirm_dialog, open_dialog, render_pending_dialog
from ui.forms import info_notice, render_flash, set_flash
from ui.layout import card_header, page_header
from ui.metrics import MetricCard, render_kpi_grid
from ui.states import render_empty_state, render_hint
from utils import sample_data as sample_mod
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
            ("Dòng dữ liệu", str(raw_count)),
            ("Dòng dùng được", str(cleaned_counts.get(key, 0))),
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
            with st.expander("Xem trước dữ liệu"):
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
        meta=f"{len(CSV_FILES)} file dữ liệu · tự kiểm tra khi nạp.",
    )

    render_flash()

    render_kpi_grid(
        [
            MetricCard("File dữ liệu", len(CSV_FILES), "devices · borrowers · borrow_records", "database"),
            MetricCard("Dòng dữ liệu", total_rows, "Đang có trên đĩa", "receipt"),
            MetricCard("Dòng dùng được", valid_rows, "Đủ thông tin để dùng", "box"),
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

    _render_sample_card(analysis)

    file_names = {key: name for key, name, _ in CSV_FILES}
    selected = st.segmented_control(
        "File dữ liệu",
        options=[key for key, _, _ in CSV_FILES],
        format_func=lambda key: file_names.get(key, key),
        default=[key for key, _, _ in CSV_FILES][0],
        key="csv_file_selector",
        help="Chọn một file để xem chi tiết, xem trước và thay thế.",
    )
    if selected not in file_names:
        selected = [key for key, _, _ in CSV_FILES][0]
    _render_file_card(selected, analysis, errors)

    render_pending_dialog(
        {
            "csv_replace": lambda payload: _dialog_csv_replace(payload, analysis),
            "sample_add": lambda payload: _dialog_sample_add(analysis),
            "sample_restore": lambda payload: _dialog_sample_restore(analysis),
        }
    )


def _render_sample_card(analysis: Dict[str, Any]) -> None:
    """Card quản lý dữ liệu mẫu: thêm nhanh + khôi phục từ sao lưu."""
    devices = analysis.get("devices", [])
    borrowers = analysis.get("borrowers", [])
    has_backup = sample_mod.has_backup(main.DATA_DIR)
    with st.container(border=True):
        card_header(
            "Dữ liệu mẫu",
            "Thêm nhanh dữ liệu mẫu để kiểm thử dashboard, biểu đồ và CRUD. "
            "Dữ liệu được ghi nối trực tiếp vào 3 file CSV.",
            chip=f"{len(devices)} TB · {len(borrowers)} SV",
        )
        add_col, restore_col = st.columns([1.4, 1], gap="medium")
        with add_col:
            st.button(
                "+ Thêm dữ liệu mẫu",
                key="sample_add_open",
                type="primary",
                width="stretch",
                help="Chọn số lượng và loại dữ liệu trong bước xác nhận.",
                on_click=open_dialog,
                kwargs={"kind": "sample_add"},
            )
        with restore_col:
            st.button(
                "Khôi phục dữ liệu mẫu",
                key="sample_restore_open",
                width="stretch",
                disabled=not has_backup,
                help=(
                    "Hoàn tác lần thêm mẫu gần nhất từ bản sao lưu."
                    if has_backup
                    else "Chưa có bản sao lưu (được tạo tự động khi thêm mẫu)."
                ),
                on_click=open_dialog,
                kwargs={"kind": "sample_restore"},
            )
        if not has_backup:
            render_hint(
                "Bản sao lưu được tạo tự động trước mỗi lần thêm mẫu — "
                "dùng nút Khôi phục để hoàn tác nếu cần.",
                "database",
            )


def _sample_counts(quantity: int, want_devices: bool,
                   want_borrowers: bool, want_records: bool) -> Dict[str, int]:
    """Số dòng sẽ thêm theo lựa chọn (phiếu gấp đôi để đủ variation)."""
    return {
        "devices": quantity if want_devices else 0,
        "borrowers": quantity if want_borrowers else 0,
        "records": quantity * 2 if want_records else 0,
    }


def _dialog_sample_add(analysis: Dict[str, Any]) -> None:
    """Dialog chọn số lượng/loại dữ liệu mẫu, xem tổng rồi xác nhận ghi."""
    @st.dialog("Thêm dữ liệu mẫu")
    def _wrap() -> None:
        st.markdown(
            '<p class="dialog-text">Dữ liệu mới được ghi NỐI vào file hiện tại '
            "(mã nối tiếp, không trùng, không mất dòng cũ) và kiểm tra bằng "
            "đúng quy tắc validators trước khi ghi.</p>",
            unsafe_allow_html=True,
        )
        quantity = st.radio(
            "Số lượng mỗi loại",
            options=list(sample_mod.SAMPLE_QUANTITIES),
            index=1,
            horizontal=True,
            key="sample_quantity",
            help="Phiếu mượn được sinh gấp đôi số này để đủ tình huống demo.",
        )
        type_cols = st.columns(3, gap="small")
        with type_cols[0]:
            want_devices = st.checkbox("Thiết bị", value=True, key="sample_want_devices")
        with type_cols[1]:
            want_borrowers = st.checkbox("Người mượn", value=True, key="sample_want_borrowers")
        with type_cols[2]:
            want_records = st.checkbox("Phiếu mượn", value=True, key="sample_want_records")

        counts = _sample_counts(quantity, want_devices, want_borrowers, want_records)
        total = sum(counts.values())
        st.markdown(
            '<div class="detail-table">'
            f'<div class="detail-row"><span class="detail-label">Thiết bị</span>'
            f'<span class="detail-value">+{counts["devices"]}</span></div>'
            f'<div class="detail-row"><span class="detail-label">Người mượn</span>'
            f'<span class="detail-value">+{counts["borrowers"]}</span></div>'
            f'<div class="detail-row"><span class="detail-label">Phiếu mượn</span>'
            f'<span class="detail-value">+{counts["records"]}</span></div>'
            f'<div class="detail-row"><span class="detail-label"><strong>Tổng</strong></span>'
            f'<span class="detail-value"><strong>+{total}</strong></span></div>'
            "</div>",
            unsafe_allow_html=True,
        )

        cancel_col, confirm_col = st.columns(2, gap="medium")
        if cancel_col.button("Huỷ", key="sample_add_cancel", width="stretch"):
            close_dialog()
            return
        if not confirm_col.button(
            "Xác nhận thêm", key="sample_add_confirm", type="primary", width="stretch"
        ):
            return
        if total == 0:
            info_notice("Chưa chọn loại dữ liệu nào.", "Tick ít nhất một loại để thêm.")
            return
        with st.spinner("Đang sinh và ghi dữ liệu mẫu..."):
            try:
                added = sample_mod.append_sample_data(
                    counts["devices"], counts["borrowers"], counts["records"],
                    main.DEVICES_CSV, main.BORROWERS_CSV, main.RECORDS_CSV,
                )
            except ValueError as exc:
                info_notice("Không thể thêm dữ liệu mẫu.", str(exc))
                return
        clear_data_cache()
        set_flash(
            f"Đã thêm {added['devices']} thiết bị, {added['borrowers']} người mượn "
            f"và {added['records']} phiếu mượn."
        )
        close_dialog()

    _wrap()


def _dialog_sample_restore(analysis: Dict[str, Any]) -> None:
    """Xác nhận khôi phục 3 CSV từ bản sao lưu gần nhất (có cảnh báo rõ)."""
    backups = sample_mod.backup_paths(main.DATA_DIR)
    modified = max(
        (data_store.last_modified(path) for path in backups.values()),
        default=None,
    )

    def _confirm() -> None:
        try:
            sample_mod.restore_sample_backup(
                main.DEVICES_CSV, main.BORROWERS_CSV, main.RECORDS_CSV
            )
        except ValueError as exc:
            set_flash(f"Không thể khôi phục: {exc}")
            return
        clear_data_cache()
        set_flash("Đã khôi phục dữ liệu từ bản sao lưu gần nhất.")

    confirm_dialog(
        "Khôi phục dữ liệu mẫu?",
        "Thao tác này sẽ THAY THẾ toàn bộ dữ liệu hiện tại bằng bản sao lưu "
        "được tạo trước lần thêm mẫu gần nhất. Mọi thay đổi sau thời điểm đó "
        "(kể cả thao tác CRUD) sẽ mất. Không thể hoàn tác.",
        "Khôi phục",
        _confirm,
        detail_rows=[
            ("Bản sao lưu lúc", format_timestamp(modified)),
            ("File sao lưu", ", ".join(path.name for path in backups.values())),
        ],
    )


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
