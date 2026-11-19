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


def render_topbar(context: str = "", alert_count: int = 0, section: str = "") -> None:
    """
    Topbar trắng, gọn một dòng: breadcrumb `section › context` bên trái,
    chuông cảnh báo bên phải.

    Brand + khối người dùng đã có ở sidebar nên KHÔNG lặp lại ở đây (topbar
    trước đây hiển thị trùng cả hai) — dành chỗ cho ngữ cảnh trang đang xem.
    """
    crumbs = []
    if section:
        crumbs.append(f'<span class="crumb">{esc(section)}</span>')
    if context:
        crumbs.append(f'<span class="crumb current" aria-current="page">{esc(context)}</span>')
    sep = f'<span class="crumb-sep" aria-hidden="true">›</span>'
    context_html = (
        f'<nav class="breadcrumb" aria-label="Breadcrumb">{sep.join(crumbs)}</nav>' if crumbs else ""
    )
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
        f"{context_html}"
        f"</div>"
        f'<div class="topbar-right">'
        f'<span class="shortcut-hint" title="Nhấn / để tìm kiếm trên trang này">'
        f'Nhấn <kbd>/</kbd> để tìm kiếm</span>'
        f'<span class="{bell_cls}" role="img" aria-label="Thông báo: {esc(bell_title)}" title="{esc(bell_title)}">'
        f'{icon("bell", 17)}{badge_html}</span>'
        f"</div></div>",
        unsafe_allow_html=True,
    )
