# -*- coding: utf-8 -*-
"""
ui/filters.py — FILTER TOOLBAR
==============================
Chịu trách nhiệm: trình bày bộ lọc (Thời gian / Loại thiết bị / Trạng thái /
Tìm kiếm / Đặt lại) và trả về lựa chọn của người dùng dưới dạng `FilterState`.

KHÔNG thay đổi thuật toán lọc: app.py vẫn gọi statistics.filter_* /
validators.find_* / search_records y như bản gốc trên tập dữ liệu đã lọc theo
thời gian. Module này thuần tuý là presentation + state của widget.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import streamlit as st

from ui.layout import card_header
from utils.helpers import device_category_options

#: Tuỳ chọn của các selectbox (giữ nguyên danh sách của bản gốc).
TIME_OPTIONS: List[str] = ["Tất cả", "7 ngày", "30 ngày", "3 tháng", "Tùy chỉnh"]
STATUS_OPTIONS: List[str] = ["Tất cả", "Đang mượn", "Đã trả", "Quá hạn", "Thất thoát"]

#: Khoá session_state của từng widget — dùng để reset thật sự.
FILTER_KEYS: List[str] = [
    "filter_time",
    "filter_category",
    "filter_status",
    "filter_search",
    "filter_range",
]

DEFAULT_RANGE_DAYS = 30


@dataclass
class FilterState:
    """Lựa chọn hiện tại của người dùng trên bộ lọc."""

    time_filter: str = TIME_OPTIONS[0]
    category_filter: str = "Tất cả"
    status_filter: str = "Tất cả"
    search_query: str = ""
    custom_start: Optional[date] = None
    custom_end: Optional[date] = None


def reset_filters() -> None:
    """Xoá toàn bộ giá trị widget trong session_state rồi render lại."""
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)
    st.rerun()


def _active_conditions() -> int:
    """
    Số điều kiện lọc đang thực sự có hiệu lực.

    Đọc trực tiếp từ session_state (giá trị widget) nên chip trên card header
    đúng ngay ở lần render này, không phải chờ thêm một vòng rerun.
    """
    active = 0
    for key in ("filter_time", "filter_category", "filter_status"):
        if str(st.session_state.get(key, "Tất cả")) != "Tất cả":
            active += 1
    if str(st.session_state.get("filter_search", "")).strip():
        active += 1
    if st.session_state.get("filter_range") and str(st.session_state.get("filter_time", "")) == "Tùy chỉnh":
        active += 1
    return active


def render_filter_bar(devices: List[Dict[str, Any]]) -> FilterState:
    """
    Render toolbar bộ lọc gọn trên một hàng (desktop) và trả về FilterState.

    Ở màn hình hẹp, st.columns tự động xếp dọc nên không bị tràn ngang.
    """
    state = FilterState()

    # `key` sinh class `.st-key-filter_row` để CSS cho phép các cột tự xuống
    # dòng trên màn hình hẹp (không tràn ngang, không chữ bị cắt).
    with st.container(border=True, key="filter_row"):
        active = _active_conditions()
        card_header(
            "Bộ lọc",
            "Áp dụng cho toàn bộ chỉ số, biểu đồ và bảng dữ liệu bên dưới.",
            chip=f"{active} điều kiện" if active else "",
        )

        columns = st.columns([1.15, 1.25, 1.15, 1.95, 1.0], gap="medium", vertical_alignment="bottom")

        with columns[0]:
            state.time_filter = st.selectbox("Thời gian", TIME_OPTIONS, index=0, key="filter_time")
        with columns[1]:
            state.category_filter = st.selectbox(
                "Loại thiết bị", device_category_options(devices), index=0, key="filter_category"
            )
        with columns[2]:
            state.status_filter = st.selectbox("Trạng thái", STATUS_OPTIONS, index=0, key="filter_status")
        with columns[3]:
            state.search_query = st.text_input(
                "Tìm kiếm thiết bị / người mượn",
                placeholder="Tìm mã thiết bị hoặc người mượn…",
                key="filter_search",
            )
        with columns[4]:
            st.button(
                "Đặt lại",
                width="stretch",
                on_click=reset_filters,
                key="filter_reset",
                help="Xoá toàn bộ điều kiện lọc và tìm kiếm.",
            )

        if state.time_filter == "Tùy chỉnh":
            picked = st.date_input(
                "Khoảng thời gian",
                value=(date.today() - timedelta(days=DEFAULT_RANGE_DAYS), date.today()),
                min_value=date(2000, 1, 1),
                max_value=date.today(),
                key="filter_range",
            )
            if isinstance(picked, (tuple, list)) and len(picked) == 2:
                state.custom_start, state.custom_end = picked

    return state
