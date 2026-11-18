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


def render_topbar(context: str = "", alert_count: int = 0) -> None:
    """Topbar trắng, gọn một dòng; `context` là tên trang đang mở, `alert_count` là số cảnh báo active."""
    context_html = f'<span class="page-chip">{esc(context)}</span>' if context else ""
    badge_html = (
        f'<span class="bell-badge" aria-label="{int(alert_count)} cảnh báo">{int(alert_count)}</span>'
        if alert_count > 0
        else ""
    )
    bell_title = (
        f"{int(alert_count)} cảnh báo cần xử lý"
        if alert_count > 0
        else "Không có cảnh báo mới"
    )
    bell_cls = "icon-btn has-alerts" if alert_count > 0 else "icon-btn"
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
        f'<span class="{bell_cls}" role="img" aria-label="Thông báo: {esc(bell_title)}" title="{esc(bell_title)}">'
        f'{icon("bell", 17)}{badge_html}</span>'
        f'<span class="user-chip">'
        f'<span class="user-avatar">QL</span>'
        f'<span class="user-name">Người quản lý</span>'
        f"</span></div></div>",
        unsafe_allow_html=True,
    )
