# -*- coding: utf-8 -*-
"""
ui/badges.py — STATUS BADGE & CHIP
==================================
Chịu trách nhiệm: pill trạng thái và dải chip thống kê trạng thái.

Quy ước màu: chỉ dùng palette của project (không thêm màu semantic mới), và
MỌI trạng thái luôn kèm nhãn chữ — màu không bao giờ là thông tin duy nhất
(accessibility).
"""
from __future__ import annotations

from typing import Dict, Iterable, List

import streamlit as st

from utils.helpers import esc

#: Trạng thái "cần chú ý" -> dùng biến thể pill đậm hơn (vẫn trong palette).
ATTENTION_STATUSES = frozenset({"Quá hạn", "Thất thoát", "Bảo trì", "Dữ liệu lỗi"})


def status_badge(status: str) -> str:
    """HTML của một pill trạng thái (nhãn chữ + biến thể màu theo token)."""
    label = esc(status or "—")
    variant = "status-badge attention" if status in ATTENTION_STATUSES else "status-badge"
    return f'<span class="{variant}">{label}</span>'


def status_badges(statuses: Iterable[str]) -> str:
    """Nhiều pill cạnh nhau (dùng trong ô bảng hoặc panel chi tiết)."""
    return "".join(status_badge(status) for status in statuses)


def render_status_chips(counts: Dict[str, int], total_label: str = "") -> None:
    """Dải chip: mỗi trạng thái kèm số lượng THẬT lấy từ dữ liệu."""
    chips: List[str] = []
    for status, count in counts.items():
        variant = "stat-chip attention" if status in ATTENTION_STATUSES else "stat-chip"
        chips.append(
            f'<span class="{variant}"><span class="stat-chip-label">{esc(status)}</span>'
            f"<strong>{int(count)}</strong></span>"
        )
    total_html = f'<span class="stat-chip total"><span class="stat-chip-label">Tổng</span><strong>{total_label}</strong></span>' if total_label else ""
    st.markdown(f'<div class="stat-chip-row">{"".join(chips)}{total_html}</div>', unsafe_allow_html=True)


def severity_label(status: str) -> str:
    """
    Mức độ hiển thị dạng chữ cho vùng cảnh báo (không dùng màu làm tín hiệu duy nhất).

    - Quá hạn nặng (>= 30 ngày) / Thất thoát / Dữ liệu lỗi -> "Cao"
    - Quá hạn thường -> "Trung bình"
    """
    return "Cao" if status in ATTENTION_STATUSES else "Trung bình"


def severity_badge(label: str) -> str:
    variant = "status-badge attention" if label == "Cao" else "status-badge"
    return f'<span class="{variant}">{esc(label)}</span>'
