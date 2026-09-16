# -*- coding: utf-8 -*-
"""
ui/app_shell.py — "SAAS SHELL" CỦA ỨNG DỤNG
===========================================
Chịu trách nhiệm duy nhất:
  - khởi tạo trang (page config + design system);
  - nạp kết quả pipeline (cache theo mtime của 3 file CSV, tự vô hiệu khi
    dữ liệu thay đổi do CRUD);
  - chặn render khi dữ liệu lỗi (error state thân thiện).

KHÔNG chứa business logic (pipeline nằm ở main.py).
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

import streamlit as st

import main
from ui import layout
from ui.states import render_error_state

#: Khoá session_state cho trang đang xem và dòng đang chọn trên bảng.
PAGE_KEY = "page"
SELECTED_KEY = "selected_row"

#: Khoá query param cho deep-link trang: /?page=borrowing
QUERY_KEY = "page"

#: Trang mở đầu tiên khi chưa có lựa chọn nào.
DEFAULT_PAGE = "overview"


def init_app() -> None:
    """Cấu hình trang + nạp design system. Gọi một lần ở đầu entrypoint."""
    layout.setup_page()
    layout.inject_global_styles()


def _data_signature() -> Tuple[Tuple[str, int], ...]:
    """
    Chữ ký dữ liệu = (đường dẫn, mtime_ns) của 3 file CSV.

    Nhờ vậy kết quả pipeline được cache nhưng TỰ ĐỘNG làm mới ngay khi file
    CSV thay đổi (ví dụ sau khi tạo/sửa/xoá bản ghi ở trang CRUD).
    """
    signature = []
    for path in (main.DEVICES_CSV, main.BORROWERS_CSV, main.RECORDS_CSV):
        try:
            signature.append((str(path), path.stat().st_mtime_ns))
        except OSError:
            signature.append((str(path), 0))
    return tuple(signature)


@st.cache_data(show_spinner=False)
def _run_pipeline_cached(signature: Tuple[Tuple[str, int], ...]) -> Dict[str, Any]:
    """Chạy pipeline và cache theo `signature` (tham số chỉ để tạo khoá cache)."""
    return main.run_pipeline()


def load_analysis() -> Dict[str, Any]:
    """Kết quả pipeline mới nhất (cached theo mtime file CSV)."""
    return _run_pipeline_cached(_data_signature())


def clear_data_cache() -> None:
    """Xoá cache sau thao tác CRUD để lần render kế tiếp đọc lại CSV."""
    _run_pipeline_cached.clear()


def has_error(analysis: Dict[str, Any]) -> bool:
    return bool(analysis.get("error"))


def retry_load() -> None:
    """Đọc lại dữ liệu từ đầu — CTA "Thử lại" của error state."""
    clear_data_cache()
    st.rerun()


def render_data_error(analysis: Dict[str, Any]) -> None:
    """Hiển thị error state của pipeline (không bao giờ lộ traceback)."""
    render_error_state(
        str(analysis.get("error", "Không tải được dữ liệu.")), on_retry=retry_load
    )


def goto_page(slug: str) -> None:
    """
    Chuyển sang một module khác.

    Dùng chung cho sidebar và các CTA hướng dẫn trong trang, nên chỉ có MỘT
    nơi định nghĩa cách đổi trang (session_state + query param để có URL riêng).
    """
    st.session_state[PAGE_KEY] = slug
    st.session_state.pop(SELECTED_KEY, None)
    st.query_params[QUERY_KEY] = slug


def current_page() -> str:
    """
    Trang đang mở: session_state (điều hướng trong app) -> query param -> mặc định.

    Nhờ query param, mỗi trang có URL riêng (?page=...), tải lại trình duyệt
    vẫn ở đúng trang và có thể chia sẻ liên kết tới từng module.
    """
    if PAGE_KEY not in st.session_state:
        query_value = st.query_params.get(QUERY_KEY)
        if query_value:
            st.session_state[PAGE_KEY] = str(query_value)
    return str(st.session_state.get(PAGE_KEY, DEFAULT_PAGE))


def selected_row_key() -> str:
    """Giá trị dòng đang chọn trên bảng CRUD (rỗng nếu chưa chọn)."""
    return str(st.session_state.get(SELECTED_KEY, ""))


def set_selected_row(value: str) -> None:
    st.session_state[SELECTED_KEY] = value
