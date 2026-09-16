# -*- coding: utf-8 -*-
"""
ui/header.py — TOPBAR (global header)
=====================================
Chịu trách nhiệm: thanh header trên cùng — brand, ngữ cảnh trang đang xem
(breadcrumb nhẹ) và khu vực người dùng (giữ nguyên thành phần bản gốc,
KHÔNG thêm authentication). Icon dùng SVG inline nên không phụ thuộc font icon.
"""
from __future__ import annotations

import streamlit as st

from utils.helpers import esc, icon


def render_topbar(context: str = "") -> None:
    """Topbar trắng, gọn một dòng; `context` là tên trang đang mở."""
    context_html = f'<span class="page-chip">{esc(context)}</span>' if context else ""
    st.markdown(
        f'<div class="app-topbar">'
        f'<div class="brand">'
        f'<span class="brand-mark">{icon("box", 19)}</span>'
        f'<span class="brand-text">'
        f'<span class="brand-name">Quản lý thiết bị</span>'
        f'<span class="brand-sub">Theo dõi mượn / trả thiết bị</span>'
        f"</span>"
        f"{context_html}"
        f"</div>"
        f'<div class="topbar-right">'
        f'<span class="icon-btn" role="img" aria-label="Thông báo">{icon("bell", 17)}</span>'
        f'<span class="user-chip">'
        f'<span class="user-avatar">QL</span>'
        f'<span class="user-name">Người quản lý</span>'
        f"</span></div></div>",
        unsafe_allow_html=True,
    )
