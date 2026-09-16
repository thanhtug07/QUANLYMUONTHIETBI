# -*- coding: utf-8 -*-
"""
ui/badges.py — STATUS BADGE & CHIP
==================================
Chịu trách nhiệm: pill trạng thái và dải chip thống kê trạng thái.

Màu lấy từ `styles/tokens.STATUS` (single source of truth) qua các class
`.status-badge.st-<variant>` trong dashboard.css. MỌI trạng thái luôn kèm
nhãn chữ + chấm dot — màu không bao giờ là thông tin duy nhất
(accessibility).
"""
from __future__ import annotations

from typing import Dict, Iterable, List

import streamlit as st

from utils.helpers import esc

#: Nhãn hiển thị -> variant semantic. Một status = một visual meaning trên
#: toàn app (mọi page đều dùng `status_badge` nên tự nhất quán).
STATUS_VARIANTS: Dict[str, str] = {
    # success: hoàn tất / đã trả / sẵn sàng
    "Đã trả": "success",
    "Sẵn sàng": "success",
    "Hợp lệ": "success",
    "Ổn định": "success",
    # info: đang xử lý / đang mượn
    "Đang mượn": "info",
    # warning: cần chú ý / bảo trì / quá hạn (cam — phân biệt với thất thoát đỏ)
    "Bảo trì": "warning",
    "Trung bình": "warning",
    "Quá hạn": "warning",
    # danger: lỗi / thất thoát (đỏ — mức nghiêm trọng nhất)
    "Thất thoát": "danger",
    "Dữ liệu lỗi": "danger",
    "Cao": "danger",
    "Cần xử lý": "danger",
}

#: Giữ để tương thích ngược (severity chữ vẫn dùng tập này).
ATTENTION_STATUSES = frozenset({"Quá hạn", "Thất thoát", "Bảo trì", "Dữ liệu lỗi"})


def status_variant(status: str) -> str:
    """Variant semantic của một nhãn trạng thái (mặc định `neutral`)."""
    return STATUS_VARIANTS.get(str(status or "").strip(), "neutral")


def status_badge(status: str) -> str:
    """HTML pill trạng thái dạng [ ● Nhãn ] (dot + chữ, không chỉ dùng màu)."""
    label = esc(status or "—")
    variant = status_variant(status)
    return (
        f'<span class="status-badge st-{variant}">'
        f'<span class="status-dot" aria-hidden="true"></span>{label}</span>'
    )


def status_badges(statuses: Iterable[str]) -> str:
    """Nhiều pill cạnh nhau (dùng trong ô bảng hoặc panel chi tiết)."""
    return "".join(status_badge(status) for status in statuses)


def render_status_chips(counts: Dict[str, int], total_label: str = "") -> None:
    """Dải chip: mỗi trạng thái kèm số lượng THẬT lấy từ dữ liệu."""
    chips: List[str] = []
    for status, count in counts.items():
        chips.append(
            f'<span class="stat-chip st-{status_variant(status)}">'
            f'<span class="status-dot" aria-hidden="true"></span>'
            f'<span class="stat-chip-label">{esc(status)}</span>'
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
    variant = status_variant(label)
    return (
        f'<span class="status-badge st-{variant}">'
        f'<span class="status-dot" aria-hidden="true"></span>{esc(label)}</span>'
    )
