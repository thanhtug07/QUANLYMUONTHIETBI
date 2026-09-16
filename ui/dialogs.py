# -*- coding: utf-8 -*-
"""
ui/dialogs.py — MODAL / DIALOG DÙNG CHUNG
=========================================
Chịu trách nhiệm: panel chi tiết, form modal (create/edit) và xác nhận xoá.

Quy ước điều khiển: một dialog đang mở được lưu trong
`st.session_state["dialog"] = {"kind": ..., ...}`. Trang CRUD gọi
`open_dialog(...)`; `render_pending_dialog(...)` ở cuối trang sẽ dựng dialog
tương ứng. Nhờ vậy người dùng không phải rời trang chỉ để sửa một bản ghi.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Sequence, Tuple

import streamlit as st

from ui.badges import status_badge
from utils.helpers import esc

#: Khoá session_state giữ dialog đang mở.
DIALOG_KEY = "dialog"


def open_dialog(kind: str, **payload: Any) -> None:
    """Mở dialog và render lại trang."""
    st.session_state[DIALOG_KEY] = {"kind": kind, **payload}
    st.rerun()


def close_dialog() -> None:
    """Đóng dialog và render lại trang."""
    st.session_state.pop(DIALOG_KEY, None)
    st.rerun()


def pending_dialog() -> Optional[Dict[str, Any]]:
    dialog = st.session_state.get(DIALOG_KEY)
    return dict(dialog) if isinstance(dialog, dict) else None


def detail_dialog(
    title: str,
    rows: Sequence[Tuple[str, str]],
    badges: Sequence[str] = (),
    note: str = "",
) -> None:
    """
    Panel chi tiết một bản ghi (dạng nhãn — giá trị).

    `rows` chỉ chứa field THẬT của bản ghi; `note` dùng cho cảnh báo nghiệp vụ
    (ví dụ số ngày quá hạn do validators tính).
    """
    badge_html = "".join(status_badge(status) for status in badges if status)
    note_html = f'<div class="detail-note">{esc(note)}</div>' if note else ""
    row_html = "".join(
        f'<div class="detail-row"><span class="detail-label">{esc(label)}</span>'
        f'<span class="detail-value">{esc(value) if value not in (None, "") else "—"}</span></div>'
        for label, value in rows
    )

    @st.dialog(title, width="large")
    def _wrap() -> None:
        if badge_html:
            st.markdown(f'<div class="detail-badges">{badge_html}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="detail-table">{row_html}</div>{note_html}', unsafe_allow_html=True)
        if st.button("Đóng", key="dlg_detail_close", width="stretch"):
            close_dialog()

    _wrap()


def form_dialog(title: str, build: Callable[[], None], width: str = "large") -> None:
    """
    Modal chứa form do trang CRUD tự dựng (`build`).

    Form vẫn là st.form thật nên Enter/Submit hoạt động đúng chuẩn.
    """
    @st.dialog(title, width=width)  # type: ignore[arg-type]
    def _wrap() -> None:
        build()

    _wrap()


def confirm_dialog(
    title: str,
    message: str,
    confirm_label: str,
    on_confirm: Callable[[], None],
    detail_rows: Sequence[Tuple[str, str]] = (),
) -> None:
    """
    Xác nhận trước khi thực hiện thao tác không thể hoàn tác (xoá bản ghi).

    Không bao giờ xoá ngay: luôn có bước xác nhận rõ ràng.
    """
    rows_html = "".join(
        f'<div class="detail-row"><span class="detail-label">{esc(label)}</span>'
        f'<span class="detail-value">{esc(value) if value not in (None, "") else "—"}</span></div>'
        for label, value in detail_rows
    )

    @st.dialog(title)
    def _wrap() -> None:
        st.markdown(
            f'<p class="dialog-text">{esc(message)}</p>'
            + (f'<div class="detail-table">{rows_html}</div>' if rows_html else ""),
            unsafe_allow_html=True,
        )
        cancel_col, confirm_col = st.columns(2, gap="medium")
        if cancel_col.button("Huỷ", key="dlg_cancel", width="stretch"):
            close_dialog()
        if confirm_col.button(confirm_label, key="dlg_confirm", type="primary", width="stretch"):
            on_confirm()
            close_dialog()

    _wrap()


def render_pending_dialog(handlers: Dict[str, Callable[[Dict[str, Any]], None]]) -> None:
    """
    Dựng dialog đang mở nếu trang hiện tại đăng ký `handlers` cho loại đó.

    Trang CRUD chỉ cần khai báo: {"delete": ..., "edit": ..., "create": ...}.
    """
    dialog = pending_dialog()
    if not dialog:
        return
    handler = handlers.get(str(dialog.get("kind", "")))
    if handler is None:
        return
    handler(dialog)
