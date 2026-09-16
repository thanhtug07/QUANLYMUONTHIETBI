# -*- coding: utf-8 -*-
"""
ui/forms.py — THÀNH PHẦN FORM DÙNG CHUNG
========================================
Chịu trách nhiệm: nhóm field trong form, hiển thị lỗi validation và thông báo
kết quả. KHÔNG chứa quy tắc nghiệp vụ (quy tắc nằm ở validators.py).
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence, Tuple

import streamlit as st

from utils.helpers import esc, icon


def form_section(title: str, description: str = "") -> None:
    """Tiêu đề nhóm field trong form (tạo nhịp thị giác rõ ràng)."""
    description_html = f'<div class="form-section-desc">{esc(description)}</div>' if description else ""
    st.markdown(
        f'<div class="form-section"><span class="form-section-title">{esc(title)}</span>'
        f"{description_html}</div>",
        unsafe_allow_html=True,
    )


def validation_summary(errors: Sequence[Dict[str, Any]]) -> None:
    """
    Hiển thị danh sách lỗi validation thân thiện (không lộ traceback).

    Mỗi lỗi là dict theo định dạng chuẩn của cleaners.make_error
    ({row, field, value, error}) nên UI không cần suy diễn gì thêm.
    """
    if not errors:
        return
    items = []
    for error in errors:
        field = str(error.get("field", "")).strip() or "dữ liệu"
        message = str(error.get("error", "")).strip()
        value = str(error.get("value", "")).strip()
        value_html = f' <span class="mono">“{esc(value)}”</span>' if value else ""
        items.append(f"<li><strong>{esc(field)}</strong>: {esc(message)}{value_html}</li>")
    st.markdown(
        f'<div class="notice error" role="alert">'
        f'<div class="notice-title">Không lưu được — vui lòng kiểm tra lại</div>'
        f'<ul class="notice-list">{"".join(items)}</ul></div>',
        unsafe_allow_html=True,
    )


def success_notice(message: str) -> None:
    """Thông báo thành công sau thao tác CRUD (State: success, kèm icon xác nhận)."""
    st.markdown(
        f'<div class="notice success" role="status">'
        f'<div class="notice-title">{icon("check", 16)}<span>{esc(message)}</span></div></div>',
        unsafe_allow_html=True,
    )


def info_notice(message: str, hint: str = "") -> None:
    """Thông báo thông tin trung tính (State: info)."""
    hint_html = f'<div class="notice-desc">{esc(hint)}</div>' if hint else ""
    st.markdown(
        f'<div class="notice info"><div class="notice-title">{esc(message)}</div>{hint_html}</div>',
        unsafe_allow_html=True,
    )


def id_options(
    rows: Iterable[Dict[str, Any]],
    id_field: str,
    label_fields: Sequence[str] = (),
    unknown_label: str = "(không rõ)",
    unknown_id: str = "",
) -> List[Tuple[str, str]]:
    """
    Danh sách (mã, nhãn) cho selectbox, nhãn ghép từ các trường thật hiện có.

    Nếu `unknown_id` khác rỗng, thêm một lựa chọn đại diện cho mã đang có
    trong phiếu nhưng không tồn tại trong danh mục (giữ nguyên dữ liệu
    tham chiếu lỗi thay vì âm thầm đổi sang mã khác).
    """
    options: List[Tuple[str, str]] = []
    for row in rows:
        row_id = str(row.get(id_field, "")).strip()
        if not row_id:
            continue
        parts = [str(row.get(field, "")).strip() for field in label_fields]
        parts = [part for part in parts if part]
        label = f"{row_id} · {' · '.join(parts)}" if parts else row_id
        options.append((row_id, label))
    if unknown_id:
        options.append((unknown_id, f"{unknown_id} · {unknown_label}"))
    return options


def option_index(options: Sequence[Tuple[str, str]], value: str) -> int:
    """Vị trí của `value` trong danh sách option (0 nếu không tìm thấy)."""
    for index, (option_value, _) in enumerate(options):
        if option_value == value:
            return index
    return 0


def display_label(options: Sequence[Tuple[str, str]], value: str, fallback: str = "—") -> str:
    """Nhãn hiển thị của một mã (dùng cho panel chi tiết)."""
    for option_value, option_label in options:
        if option_value == value:
            return option_label
    return str(value).strip() or fallback


def confirm_hint(key_label: str, key_value: str) -> str:
    """Câu hỏi xác nhận xoá — luôn nêu rõ bản ghi sắp xoá."""
    return f"{key_label} {key_value}"


# ----------------------------------------------------------------------
# FLASH MESSAGE — thông báo sống qua một lần rerun
# ----------------------------------------------------------------------
#: Khoá session_state giữ thông báo kết quả thao tác.
FLASH_KEY = "flash_message"


def set_flash(message: str) -> None:
    """
    Ghi thông báo thành công để hiển thị ở lần render kế tiếp.

    Dialog CRUD đóng bằng `st.rerun()` nên thông báo cần sống qua một vòng
    render: đây là lý do dùng session_state thay vì render trực tiếp.
    """
    st.session_state[FLASH_KEY] = message


def render_flash() -> None:
    """
    Hiển thị (và xoá) thông báo kết quả thao tác gần nhất.

    Gồm hai lớp phản hồi: notice trong luồng trang (đọc được, lưu lại) và toast
    ở góc màn hình (thấy ngay cả khi người dùng đang ở vị trí khác trên trang).
    """
    message = st.session_state.pop(FLASH_KEY, "")
    if not message:
        return
    text = str(message)
    success_notice(text)
    st.toast(text, icon="✅")
