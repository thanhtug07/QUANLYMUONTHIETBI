# -*- coding: utf-8 -*-
"""
ui/layout.py — KHUNG TRANG & GRID
=================================
Chịu trách nhiệm: cấu hình trang, nạp design system (tokens + CSS), page
header (kèm primary action), card header và các grid.

KHÔNG chứa business logic.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional, Tuple

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from styles import tokens

STYLES_DIR = Path(__file__).resolve().parents[1] / "styles"
CSS_FILE = STYLES_DIR / "dashboard.css"


def setup_page() -> None:
    """Cấu hình trang — phải gọi TRƯỚC mọi lệnh st.* khác."""
    st.set_page_config(
        page_title="Quản lý mượn thiết bị",
        page_icon="📋",
        layout="wide",
        # "expanded": sidebar luôn mở khi tải trang — người không rành công nghệ
        # vẫn thấy ngay menu điều hướng (không bị gập rồi tưởng mất trang).
        initial_sidebar_state="expanded",
    )


def inject_global_styles(extra_css: str = "") -> None:
    """
    Nạp font + design tokens + dashboard.css (+ CSS động tuỳ chọn).

    Thứ tự trong một thẻ <style>: @import (font) -> biến CSS -> component CSS.
    """
    css = CSS_FILE.read_text(encoding="utf-8")
    st.markdown(
        f"<style>@import url('{tokens.FONT_URL}');\n{tokens.css_variables()}\n{css}\n{extra_css}</style>",
        unsafe_allow_html=True,
    )


def _page_header_html(title: str, subtitle: str, meta: str) -> None:
    meta_html = f'<div class="page-meta">{meta}</div>' if meta else ""
    st.markdown(
        f'<div class="page-header">'
        f'<h1 class="page-title">{title}</h1>'
        f'<p class="page-subtitle">{subtitle}</p>'
        f"{meta_html}</div>",
        unsafe_allow_html=True,
    )


def page_header(
    title: str,
    subtitle: str = "",
    meta: str = "",
    action_label: str = "",
    action_key: str = "",
    on_action: Optional[Callable[[], None]] = None,
    action_help: str = "",
) -> None:
    """
    Tiêu đề trang (28px/700) + mô tả + metadata + primary action tuỳ chọn.

    Primary action là st.button thật (keyboard/aria chuẩn) đặt ngay cạnh tiêu
    đề — không tách sang vùng khác của trang.
    """
    if not action_label:
        _page_header_html(title, subtitle, meta)
        return

    title_col, action_col = st.columns([3, 1], gap="medium", vertical_alignment="center")
    with title_col:
        _page_header_html(title, subtitle, meta)
    with action_col:
        st.button(
            action_label,
            key=action_key,
            on_click=on_action,
            type="primary",
            width="stretch",
            help=action_help or None,
        )


def card_header(title: str, subtitle: str = "", chip: str = "") -> None:
    """
    Header chuẩn của mọi card: tiêu đề (18px/700) + chip số liệu (tuỳ chọn)
    + phụ đề metadata (13px). Dùng chung cho chart card, table card, panel.
    """
    chip_html = f'<span class="card-count">{chip}</span>' if chip else ""
    subtitle_html = f'<div class="card-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div class="card-title-row"><h3 class="card-title">{title}</h3>{chip_html}</div>'
        f"{subtitle_html}",
        unsafe_allow_html=True,
    )


def analytics_grid() -> Tuple[DeltaGenerator, DeltaGenerator]:
    """Grid analytics chính: cột lớn (8) cho biểu đồ chủ đạo, cột nhỏ (4) cho biểu đồ phụ."""
    return st.columns([8, 4], gap="medium")


def two_column_grid() -> Tuple[DeltaGenerator, DeltaGenerator]:
    """Grid hai cột bằng nhau (dùng cho các panel phụ như xếp hạng)."""
    return st.columns(2, gap="medium")
