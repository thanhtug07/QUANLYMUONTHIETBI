# -*- coding: utf-8 -*-
"""
ui/sidebar.py — SIDEBAR NAVIGATION (SaaS)
=========================================
Chịu trách nhiệm: branding, điều hướng 2 nhóm (QUẢN LÝ / DỮ LIỆU), active
state, trạng thái hệ thống và số bản ghi đang có.

Nav là các `st.button` THẬT (bàn phím/aria chuẩn) chứ không phải HTML tĩnh:
mỗi mục chuyển trang qua `st.session_state["page"]`. Icon dùng chính bộ SVG
của app, nhúng vào CSS dưới dạng data-URI (một phong cách icon duy nhất,
không phụ thuộc font icon ngoài).
"""
from __future__ import annotations

import functools
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import streamlit as st

from styles import tokens
from ui.app_shell import goto_page
from ui.layout import inject_shortcuts
from ui.theme import is_dark
from utils.helpers import esc, icon, icon_data_uri

#: Khoá session_state của widget nav (dùng để style theo từng mục).
NAV_KEY_PREFIX = "nav_"


@dataclass(frozen=True)
class NavItem:
    """Một mục điều hướng: slug (khoá trang) + nhãn + tên icon nội bộ."""

    slug: str
    label: str
    icon_name: str


#: Cấu trúc điều hướng: (tiêu đề nhóm, các mục).
NAV_SECTIONS: Tuple[Tuple[str, Tuple[NavItem, ...]], ...] = (
    (
        "Quản lý",
        (
            NavItem("overview", "Tổng quan", "dashboard"),
            NavItem("borrowing", "Phiếu mượn", "receipt"),
            NavItem("equipment", "Thiết bị", "monitor"),
            NavItem("borrowers", "Người mượn", "users"),
            NavItem("alerts", "Cảnh báo", "alert"),
            NavItem("reports", "Báo cáo", "report"),
        ),
    ),
    ("Dữ liệu", (NavItem("csv", "CSV", "database"),)),
)

#: Trang mặc định.
DEFAULT_PAGE = NAV_SECTIONS[0][1][0].slug

#: Nhãn hiển thị của các số liệu nguồn dữ liệu trong sidebar.
COUNT_LABELS = (
    ("devices", "Thiết bị"),
    ("borrowers", "Người mượn"),
    ("records", "Phiếu mượn"),
)


def all_items() -> List[NavItem]:
    return [item for _, items in NAV_SECTIONS for item in items]


def page_label(slug: str) -> str:
    """Nhãn hiển thị của một trang (dùng cho topbar/breadcrumb)."""
    for item in all_items():
        if item.slug == slug:
            return item.label
    return DEFAULT_PAGE


def page_section(slug: str) -> str:
    """Tên nhóm điều hướng chứa trang (dùng cho breadcrumb topbar)."""
    for section_title, items in NAV_SECTIONS:
        if any(item.slug == slug for item in items):
            return section_title
    return ""


@functools.lru_cache(maxsize=32)
def _nav_icon_css(active: str, dark: bool = False) -> str:
    """
    CSS động cho icon của từng mục nav.

    Màu icon lấy từ token: mục đang mở dùng primary, mục còn lại dùng màu chữ
    phụ; nhờ vậy chỉ có một phong cách icon và không hardcode màu trong CSS.
    """
    rules: List[str] = []
    for item in all_items():
        # Sidebar nền xanh: mục đang mở là ô trắng -> icon xanh primary; các
        # mục còn lại icon trắng mờ trên nền xanh.
        colors = tokens.palette(dark)
        color = colors["primary"] if item.slug == active else tokens.SIDEBAR_TEXT_SOFT
        uri = icon_data_uri(item.icon_name, color)
        # Tiền tố stSidebar + !important: rule nền chung của button
        # (`[data-testid="stButton"] button { background: ... }`, kể cả :hover)
        # dùng shorthand `background` nên sẽ xoá mất icon nếu chỉ ngang hàng
        # độ ưu tiên.
        rules.append(
            f'[data-testid="stSidebar"] .st-key-{NAV_KEY_PREFIX}{item.slug} button, '
            f'[data-testid="stSidebar"] .st-key-{NAV_KEY_PREFIX}{item.slug} button:hover '
            f'{{ background-image: url("{uri}") !important; '
            f'background-repeat: no-repeat !important; '
            f'background-position: 15px center !important; '
            f'background-size: 17px 17px !important; }}'
        )
    return "\n".join(rules)


@functools.lru_cache(maxsize=1)
def _build_tag() -> str:
    """
    Mã commit ngắn của bản code đang chạy (để đối chiếu bản cũ/mới khi
    trình duyệt còn cache: nhìn tem là biết có cần hard-refresh không).
    Lấy lỗi (không có git / cloud chặn subprocess) thì ẩn, không crash app.
    """
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=str(Path(__file__).resolve().parent),
        )
        tag = completed.stdout.strip()
        if completed.returncode == 0 and len(tag) >= 4 and all(
            char in "0123456789abcdef" for char in tag
        ):
            return tag
    except Exception:
        pass
    return ""


def _data_meta_html(counts: Dict[str, int]) -> str:
    rows: List[str] = []
    for key, label in COUNT_LABELS:
        if key in counts:
            rows.append(
                f'<div class="side-meta-row"><span>{esc(label)}</span>'
                f"<strong>{int(counts[key])}</strong></div>"
            )
    return f'<div class="side-meta">{"".join(rows)}</div>' if rows else ""


def render_sidebar(
    active: str,
    counts: Optional[Dict[str, int]] = None,
    data_ok: bool = True,
) -> None:
    """
    Render sidebar: brand + nhóm điều hướng + nguồn dữ liệu + trạng thái.

    `active` là slug trang đang mở; `counts` là số bản ghi THẬT đang load.
    """
    counts = counts or {}

    with st.sidebar:
        st.markdown(
            f"<style>{_nav_icon_css(active, is_dark())}</style>"
            f'<div class="side-brand">'
            f'<span class="brand-mark">{icon("box", 19)}</span>'
            f'<span class="side-brand-text">'
            f'<span class="side-brand-name">Quản lý thiết bị</span>'
            f'<span class="side-brand-sub">Mượn / trả · CSV</span>'
            f"</span></div>",
            unsafe_allow_html=True,
        )

        for section_title, items in NAV_SECTIONS:
            st.markdown(
                f'<div class="side-section">{esc(section_title)}</div>', unsafe_allow_html=True
            )
            for item in items:
                is_active = item.slug == active
                st.button(
                    item.label,
                    key=f"{NAV_KEY_PREFIX}{item.slug}",
                    on_click=goto_page,
                    args=(item.slug,),
                    type="primary" if is_active else "secondary",
                    width="stretch",
                    help=f"Chuyển đến {item.label}" if not is_active else None,
                )

        status_text = "Hệ thống sẵn sàng" if data_ok else "Dữ liệu có lỗi"
        meta_html = _data_meta_html(counts)
        build_tag = _build_tag()
        version_html = (
            f'<div class="side-version">bản {esc(build_tag)}</div>'
            if build_tag
            else ""
        )
        st.markdown(
            f'<div class="side-pill-row"><span class="pill" role="status">'
            f'<span class="dot"></span>{esc(status_text)}</span></div>'
            f"{meta_html}"
            f"{version_html}"
            '<div class="side-user">'
            '<span class="user-avatar">QL</span>'
            '<span class="side-user-text">'
            '<span class="side-user-name">Người quản lý</span>'
            '<span class="side-user-sub">Quản trị hệ thống</span>'
            "</span></div>",
            unsafe_allow_html=True,
        )
        # Phím tắt gắn ở sidebar để thẻ script không tạo khoảng trống ở main.
        inject_shortcuts()
