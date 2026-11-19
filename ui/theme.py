# -*- coding: utf-8 -*-
"""
ui/theme.py — CHẾ ĐỘ SÁNG / TỐI
================================
Đọc chế độ hiển thị hiện tại của Streamlit (người dùng chọn trong menu ⋮ →
Settings, mặc định theo hệ điều hành) để code Python (biểu đồ Altair, icon
sidebar, màu ô bảng) dùng đúng bảng màu với CSS.
"""
from __future__ import annotations

from typing import Dict

import streamlit as st

from styles import tokens


#: App cố định giao diện SÁNG (nền trắng, xanh dương chủ đạo). Đặt True để
#: cho phép theo chế độ tối của trình duyệt / Streamlit như trước.
ALLOW_DARK_MODE = False


def is_dark() -> bool:
    """True khi được phép dark mode VÀ Streamlit đang ở chế độ tối."""
    if not ALLOW_DARK_MODE:
        return False
    try:
        theme = getattr(st.context, "theme", None)
        return str(getattr(theme, "type", "") or "").lower() == "dark"
    except Exception:
        return False


def color(name: str) -> str:
    """Màu token theo chế độ hiện tại (bg, surface, text, primary, border, text-muted...)."""
    return tokens.palette(is_dark())[name]


def status_colors() -> Dict[str, Dict[str, str]]:
    """Bảng màu trạng thái theo chế độ hiện tại."""
    return tokens.status_palette(is_dark())
