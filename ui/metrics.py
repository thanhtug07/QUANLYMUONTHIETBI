# -*- coding: utf-8 -*-
"""
ui/metrics.py — KPI CARDS
=========================
Chịu trách nhiệm: thẻ KPI (label + icon + số lớn + ngữ cảnh hỗ trợ + chỉ báo
ngữ cảnh) và grid KPI responsive (4 cột -> 2 -> 1).

Chỉ hiển thị số liệu THẬT truyền vào từ app.py (kết quả pipeline), không
hardcode, không tạo trend/percentage giả: nếu một card không có dữ liệu phụ
phù hợp thì phần chỉ báo đơn giản không được render (ẩn thay vì bịa).

`kind` chỉ chọn BIỂU TƯỢNG trình bày, không thêm màu mới:
  - "share"  : progress bar phần trăm (vd: 70.8% tổng số);
  - "alert"  : badge đậm khi số > 0, nhạt khi số = 0;
  - None     : như bản cũ (label phụ đơn giản).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

import streamlit as st

from utils.helpers import esc, icon


@dataclass(frozen=True)
class MetricCard:
    """Dữ liệu của một thẻ KPI."""

    label: str
    value: Any
    sub: str = ""
    icon_name: str = "box"
    #: Loại chỉ báo ngữ cảnh: "share" (progress bar) | "alert" (badge) | None.
    kind: Optional[str] = None
    #: Tỷ lệ 0..100 cho kind="share" (None -> không vẽ bar).
    percent: Optional[float] = None
    #: Nhãn đếm phụ bên phải (vd: "23 phiếu" cho nhóm Quá hạn).
    mini: str = ""
    #: Chữ trong badge (kind="alert"); mặc định suy từ sub.
    badge: str = ""
    #: Pill delta kỳ ("+12,5%" — chuỗi đã format từ statistics.format_delta,
    #: None/rỗng -> ẩn pill thay vì bịa số).
    delta: str = ""
    #: Tone của pill delta: "good" (success) | "bad" (danger) | "" (info).
    delta_tone: str = ""
    #: (mở rộng) danh sách field bổ sung — giữ tương thích ngược với bản cũ.
    extra: List[str] = field(default_factory=list)


def _foot_html(card: MetricCard) -> str:
    """Chỉ báo ngữ cảnh của card — chỉ render phần có dữ liệu thật."""
    parts: List[str] = []

    if card.kind == "share" and card.percent is not None:
        clamped = max(0.0, min(100.0, float(card.percent)))
        parts.append(f'<div class="kpi-bar"><div class="kpi-bar-fill" style="width:{clamped:.1f}%"></div></div>')
        if card.mini:
            parts.append(f'<div class="kpi-mini">{esc(card.mini)}</div>')
    elif card.kind == "alert":
        try:
            positive = float(card.value) > 0
        except (TypeError, ValueError):
            positive = False
        label = card.badge or ("Cần xử lý" if positive else "Ổn định")
        variant = "kpi-badge attention" if positive else "kpi-badge"
        parts.append(f'<div class="kpi-badge-row"><span class="{variant}">{esc(label)}</span>')
        if card.mini:
            parts.append(f'<span class="kpi-mini">{esc(card.mini)}</span>')
        parts.append("</div>")

    return f'<div class="kpi-foot">{"".join(parts)}</div>' if parts else ""


def _delta_html(card: MetricCard) -> str:
    """Pill delta kỳ cạnh số KPI — ẩn khi không có cơ sở so sánh."""
    text = str(card.delta or "").strip()
    if not text:
        return ""
    tone = str(card.delta_tone or "").strip().lower()
    variant = f" {tone}" if tone in ("good", "bad") else ""
    arrow = "▲" if text.startswith("+") else ("▼" if text.startswith(("−", "-")) else "•")
    return f'<span class="kpi-delta{variant}">{arrow} {esc(text.lstrip("+-−"))}</span>'


def render_metric_card(card: MetricCard) -> str:
    """Trả về markup của một thẻ KPI."""
    sub_html = (
        f'<div class="kpi-sub"><span class="dot"></span>{esc(card.sub)}</div>'
        if card.sub
        else '<div class="kpi-sub"></div>'
    )
    foot_html = _foot_html(card)
    return (
        f'<div class="kpi-card">'
        f'<div class="kpi-head">'
        f'<span class="kpi-label">{esc(card.label)}</span>'
        f'<span class="kpi-icon">{icon(card.icon_name, 18)}</span>'
        f"</div>"
        f'<div class="kpi-value-row"><div class="kpi-value">{esc(card.value)}</div>'
        f"{_delta_html(card)}</div>"
        f"{sub_html}{foot_html}</div>"
    )


def render_kpi_grid(cards: List[MetricCard]) -> None:
    """
    Render toàn bộ dải KPI trong MỘT grid HTML.

    Dùng CSS grid (thay vì st.columns) để giữ đúng 4 cột bằng nhau ở desktop
    và tự chuyển 2x2 / 1 cột ở tablet / mobile mà không lệch alignment.
    """
    cards_html = "".join(render_metric_card(card) for card in cards)
    st.markdown(f'<div class="kpi-grid">{cards_html}</div>', unsafe_allow_html=True)
