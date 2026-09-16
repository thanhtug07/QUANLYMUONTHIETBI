# -*- coding: utf-8 -*-
"""
ui/states.py — TRẠNG THÁI GIAO DIỆN
===================================
Chịu trách nhiệm: loading / empty / no-data / error state, dải gợi ý (hint) và
trạng thái khởi đầu khi hệ thống chưa có dữ liệu.

Nguyên tắc: không bao giờ để vùng trắng trống vô nghĩa — mỗi trạng thái đều nói
rõ ĐANG XẢY RA CHUYỆN GÌ và NGƯỜI DÙNG NÊN LÀM GÌ TIẾP (CTA thật, không phải
chữ chết). Đây là lý do các hàm ở đây nhận callback thay vì chỉ nhận chữ.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Iterator, Optional, Sequence

import streamlit as st

from utils.helpers import esc, icon

#: Khoá container bọc CTA trong các khối trạng thái — CSS căn giữa và giới hạn
#: bề rộng nút nên nút không kéo dài hết card.
ACTION_KEY = "state_action"


def _action_button(
    label: str,
    key: str,
    on_action: Optional[Callable[[], None]],
    help_text: str = "",
) -> None:
    """CTA của khối trạng thái (chỉ hiện khi có hành động thật để thực hiện)."""
    if not label or on_action is None:
        return
    with st.container(key=ACTION_KEY):
        st.button(
            label,
            key=key,
            on_click=on_action,
            type="primary",
            help=help_text or None,
        )


def render_empty_state(
    title: str,
    hint: str = "",
    icon_name: str = "database",
    compact: bool = False,
    action_label: str = "",
    action_key: str = "",
    on_action: Optional[Callable[[], None]] = None,
    action_help: str = "",
) -> None:
    """Khối empty state căn giữa: icon + tiêu đề + gợi ý + CTA tuỳ chọn."""
    css_class = "state-block compact" if compact else "state-block"
    hint_html = f'<div class="state-hint">{esc(hint)}</div>' if hint else ""
    st.markdown(
        f'<div class="{css_class}" role="status">'
        f'<div class="state-icon">{icon(icon_name, 20)}</div>'
        f'<div class="state-title">{esc(title)}</div>'
        f"{hint_html}</div>",
        unsafe_allow_html=True,
    )
    _action_button(action_label, action_key, on_action, action_help)


def render_no_results(
    on_reset: Optional[Callable[[], None]] = None,
    reset_label: str = "Đặt lại bộ lọc",
    reset_key: str = "state_reset_filters",
    phrase: str = "Không tìm thấy dữ liệu phù hợp.",
) -> None:
    """
    Không có bản ghi nào khớp bộ lọc hiện tại.

    Kèm CTA đặt lại bộ lọc (nếu trang truyền vào) để người dùng thoát khỏi
    ngõ cụt ngay tại chỗ thay vì phải tự đoán nên nới điều kiện nào.
    """
    render_empty_state(
        phrase,
        "Thử nới rộng mốc thời gian, loại thiết bị, trạng thái hoặc từ khoá tìm kiếm.",
        "search",
        action_label=reset_label,
        action_key=reset_key,
        on_action=on_reset,
        action_help="Xoá toàn bộ điều kiện lọc và tìm kiếm đang áp dụng.",
    )


def render_error_state(
    message: str,
    on_retry: Optional[Callable[[], None]] = None,
) -> None:
    """Error card khi pipeline không thể đọc/parse dữ liệu (kèm CTA thử lại)."""
    st.markdown(
        f'<div class="error-card" role="alert">'
        f'<div class="error-icon">{icon("alert", 20)}</div>'
        f"<div>"
        f'<div class="error-title">Không tải được dữ liệu</div>'
        f'<p class="error-detail">{esc(message)}</p>'
        f'<p class="error-detail">Kiểm tra lại các file CSV ở trang Dữ liệu CSV '
        f"rồi thử lại.</p>"
        f"</div></div>",
        unsafe_allow_html=True,
    )
    _action_button(
        "Thử lại",
        "state_retry",
        on_retry,
        "Đọc lại dữ liệu CSV từ đầu.",
    )


def render_hint(text: str, icon_name: str = "filter") -> None:
    """
    Dải gợi ý một dòng ngay dưới bảng/toolbar: nói rõ thao tác cần làm.

    Dùng khi người dùng chưa biết phải bấm vào đâu (ví dụ chọn dòng để sửa) —
    thay cho caption mờ nhạt, vốn dễ bị bỏ qua.
    """
    st.markdown(
        f'<div class="hint-bar" role="note">{icon(icon_name, 16)}'
        f"<span>{esc(text)}</span></div>",
        unsafe_allow_html=True,
    )


def render_first_run(
    title: str,
    hint: str,
    steps: Sequence[str],
    action_label: str,
    action_key: str,
    on_action: Callable[[], None],
    icon_name: str = "database",
) -> None:
    """
    Trạng thái khởi đầu: hệ thống chưa có dữ liệu nào.

    Thay vì hiển thị một dashboard toàn số 0, chỉ rõ đúng việc cần làm đầu tiên
    và cho người dùng đi thẳng tới đó bằng một nút.
    """
    steps_html = "".join(f"<li>{esc(step)}</li>" for step in steps)
    st.markdown(
        f'<div class="start-card" role="status">'
        f'<div class="state-icon">{icon(icon_name, 20)}</div>'
        f'<div class="state-title">{esc(title)}</div>'
        f'<div class="state-hint">{esc(hint)}</div>'
        f'<ol class="start-steps">{steps_html}</ol></div>',
        unsafe_allow_html=True,
    )
    _action_button(action_label, action_key, on_action)


@contextmanager
def render_loading(label: str = "Đang tải dữ liệu…") -> Iterator[None]:
    """Spinner nhẹ trong lúc chạy pipeline đọc CSV."""
    with st.spinner(label):
        yield
