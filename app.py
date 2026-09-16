# -*- coding: utf-8 -*-
"""
app.py — ENTRYPOINT CỦA ỨNG DỤNG STREAMLIT
==========================================
File này chỉ làm 3 việc:

1. Khởi tạo trang + design system (`ui.app_shell`);
2. Nạp kết quả pipeline (`main.run_pipeline`, cache theo mtime của 3 file CSV)
   và dựng SaaS shell: sidebar điều hướng + topbar;
3. Gọi `render(analysis)` của page đang mở trong `pages/`.

Toàn bộ logic nghiệp vụ vẫn nằm nguyên trong cleaners / validators /
statistics / reports và được gọi lại y như bản gốc:

    CSV -> cleaners -> validators -> statistics -> reports  (main.run_pipeline)

Sidebar gồm 2 nhóm: QUẢN LÝ (Tổng quan, Phiếu mượn, Thiết bị, Người mượn,
Cảnh báo, Báo cáo) và DỮ LIỆU (CSV). Mỗi mục là một module riêng trong `pages/`.
"""
from __future__ import annotations

from typing import Any, Callable, Dict

import streamlit as st

from pages import DEFAULT_PAGE, alerts, borrowers, borrowing, csv_data, equipment, overview, reports
from ui.app_shell import (
    PAGE_KEY,
    current_page,
    has_error,
    init_app,
    load_analysis,
    render_data_error,
)
from ui.header import render_topbar
from ui.sidebar import page_label, render_sidebar
from ui.states import render_loading

#: Bảng điều phối: slug page -> hàm render của module tương ứng.
RENDERERS: Dict[str, Callable[[Dict[str, Any]], None]] = {
    "overview": overview.render,
    "borrowing": borrowing.render,
    "equipment": equipment.render,
    "borrowers": borrowers.render,
    "alerts": alerts.render,
    "reports": reports.render,
    "csv": csv_data.render,
}


def render_app() -> None:
    """Dựng toàn bộ ứng dụng cho một lần rerun của Streamlit."""
    init_app()

    with render_loading():
        analysis = load_analysis()

    counts = {
        "devices": len(analysis.get("devices", [])),
        "borrowers": len(analysis.get("borrowers", [])),
        "records": len(analysis.get("records", [])),
    }

    page = current_page()
    if page not in RENDERERS:
        page = DEFAULT_PAGE
        st.session_state[PAGE_KEY] = page

    render_sidebar(active=page, counts=counts, data_ok=not has_error(analysis))
    render_topbar(context=page_label(page))

    if has_error(analysis):
        render_data_error(analysis)
        st.stop()

    RENDERERS[page](analysis)


render_app()
