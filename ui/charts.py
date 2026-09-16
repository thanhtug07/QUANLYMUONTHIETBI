# -*- coding: utf-8 -*-
"""
ui/charts.py — CHART CARDS
==========================
Chịu trách nhiệm: dựng các biểu đồ của dashboard/report với style thống nhất
(nền trong suốt trên card trắng, grid nhạt, typography Source Sans 3,
bo góc nhẹ, không gradient/3D/dark background).

Dữ liệu truyền vào LUÔN là số liệu thật từ statistics.compute_all /
validators — module này không tạo, không nội suy, không bịa dữ liệu.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

import altair as alt
import pandas as pd
import streamlit as st

from styles import tokens
from ui.states import render_empty_state
from utils.helpers import esc, month_label

#: Chiều cao biểu đồ (gọn để vừa viewport, vẫn đủ đọc số liệu).
CHART_HEIGHT = 240

#: Font cho Vega-Lite (lấy từ design tokens).
CHART_FONT = tokens.FONT_NAME

#: Màu biểu đồ theo TÊN trạng thái — cùng `styles/tokens.STATUS` với badge nên
#: badge và chart luôn cùng một visual meaning (nhãn chữ vẫn là chính).
STATUS_CHART_COLORS = {
    "Sẵn sàng": tokens.STATUS["success"]["base"],
    "Đã trả": tokens.STATUS["success"]["base"],
    "Đang mượn": tokens.STATUS["info"]["base"],
    "Bảo trì": tokens.STATUS["warning"]["base"],
    "Quá hạn": tokens.STATUS["warning"]["base"],
    "Thất thoát": tokens.STATUS["danger"]["base"],
}

#: Fallback khi gặp nhãn ngoài 6 trạng thái chuẩn (giữ trong palette).
STATUS_COLOR_FALLBACK = tokens.COLOR_ACCENT


def _status_colors(labels: Sequence[str]) -> List[str]:
    """Màu từng nhãn trạng thái theo đúng thứ tự labels (khớp domain)."""
    return [STATUS_CHART_COLORS.get(str(label), STATUS_COLOR_FALLBACK) for label in labels]


def _status_color_encoding(field: str, labels: Sequence[str]) -> alt.Color:
    """Encoding màu Altair với domain/range tường minh — màu luôn khớp nhãn."""
    return alt.Color(
        f"{field}:N",
        scale=alt.Scale(domain=list(labels), range=_status_colors(labels)),
    )


def _axis_labels(**overrides: object) -> alt.Axis:
    base = {
        "labelColor": tokens.COLOR_TEXT,
        "labelFontSize": 12,
        "titleColor": tokens.COLOR_TEXT,
        "titleFontSize": 12,
        "domainColor": tokens.COLOR_BORDER,
        "tickColor": tokens.COLOR_BORDER,
    }
    base.update(overrides)
    return alt.Axis(**base)  # type: ignore[arg-type]


def _value_axis(**overrides: object) -> alt.Axis:
    base = {
        "gridColor": tokens.COLOR_BORDER,
        "gridOpacity": 0.8,
        "domain": False,
        "ticks": False,
    }
    base.update(overrides)
    return _axis_labels(**base)


def render_category_chart(rows: Sequence[Tuple[str, int]], footer_total: int) -> None:
    """
    Biểu đồ CỘT — "Lượt mượn theo loại thiết bị".

    `rows` đã được statistics sắp giảm dần nên trục X giữ nguyên thứ tự dữ
    liệu (sort=None), không đổi logic thống kê.
    """
    if not rows:
        render_empty_state(
            "Chưa có dữ liệu lượt mượn theo loại thiết bị.",
            "Số liệu sẽ xuất hiện khi có phiếu mượn phù hợp bộ lọc hiện tại.",
            "box",
            compact=True,
        )
        return

    frame = pd.DataFrame(list(rows), columns=["Loại thiết bị", "Số lượt"])
    chart = (
        alt.Chart(frame)
        .mark_bar(color=tokens.COLOR_PRIMARY, cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X(
                "Loại thiết bị:N",
                title=None,
                sort=None,
                axis=_axis_labels(labelLimit=170, labelAngle=0, grid=False),
            ),
            y=alt.Y("Số lượt:Q", title=None, axis=_value_axis()),
            tooltip=[
                alt.Tooltip("Loại thiết bị:N", title="Loại thiết bị"),
                alt.Tooltip("Số lượt:Q", title="Số lượt"),
            ],
        )
        .properties(height=CHART_HEIGHT, background="transparent")
        .configure_view(stroke=None, fill="transparent")
        .configure(font=CHART_FONT)
    )
    st.altair_chart(chart, width="stretch")
    st.markdown(
        f'<div class="chart-footer"><span>Tổng lượt mượn</span>'
        f"<strong>{footer_total}</strong></div>",
        unsafe_allow_html=True,
    )


def render_status_donut(counts: Dict[str, int], center_label: str) -> None:
    """
    Biểu đồ DONUT — "Phân bố trạng thái thiết bị" (trang Báo cáo).

    - Legend đặt ngang phía dưới, cỡ chữ nhỏ.
    - Nhãn trung tâm là TỔNG số thiết bị thật.
    - Màu chỉ lấy từ palette (thang sáng -> đậm).
    """
    if not counts or sum(counts.values()) == 0:
        render_empty_state(
            "Chưa có dữ liệu phân bố trạng thái.",
            "Số liệu sẽ xuất hiện khi danh mục thiết bị có dữ liệu.",
            "box",
            compact=True,
        )
        return

    frame = pd.DataFrame({"Trạng thái": list(counts.keys()), "Số lượng": list(counts.values())})
    total = int(sum(counts.values()))
    labels = list(counts.keys())

    donut = (
        alt.Chart(frame)
        .mark_arc(innerRadius=58, outerRadius=92, stroke=tokens.COLOR_SURFACE, strokeWidth=2)
        .encode(
            theta=alt.Theta("Số lượng:Q", stack=True),
            color=alt.Color(
                "Trạng thái:N",
                scale=alt.Scale(domain=labels, range=_status_colors(labels)),
                legend=alt.Legend(
                    orient="bottom",
                    title=None,
                    labelColor=tokens.COLOR_TEXT,
                    labelFontSize=12,
                    symbolSize=110,
                    direction="horizontal",
                    columns=2,
                ),
            ),
            tooltip=[
                alt.Tooltip("Trạng thái:N", title="Trạng thái"),
                alt.Tooltip("Số lượng:Q", title="Số lượng"),
            ],
        )
    )
    center = (
        alt.Chart(pd.DataFrame({"text": [center_label]}))
        .mark_text(fontSize=26, fontWeight="bold", color=tokens.COLOR_TEXT, dy=2)
        .encode(text="text:N")
    )
    caption = (
        alt.Chart(pd.DataFrame({"text": ["thiết bị"]}))
        .mark_text(fontSize=12, color=tokens.TEXT_MUTED, dy=22)
        .encode(text="text:N")
    )
    chart = (
        (donut + center + caption)
        .properties(height=252, background="transparent")
        .configure_view(stroke=None, fill="transparent")
        .configure(font=CHART_FONT)
    )
    st.altair_chart(chart, width="stretch")
    st.markdown(
        f'<div class="chart-footer"><span>Tổng thiết bị trong danh mục</span>'
        f"<strong>{total}</strong></div>",
        unsafe_allow_html=True,
    )


def render_trend_area(
    rows: Sequence[Tuple[str, int]],
    stats: Dict[str, Any],
) -> None:
    """
    Biểu đồ VÙNG — focal point "Hoạt động mượn thiết bị" (trang Tổng quan).

    Area vẽ TỔNG LƯỢT TÍCH LŨY theo tháng (chỉ gồm tháng có phiếu thật, sinh
    từ statistics.borrows_by_month — không nội suy tháng trống, không bịa số).
    Ba con số phía trên (Tổng / Đang mượn / Đã trả) là số liệu thật của stats.
    """
    if not rows:
        render_empty_state(
            "Chưa có dữ liệu hoạt động mượn.",
            "Xu hướng sẽ xuất hiện khi dữ liệu có ngày mượn hợp lệ.",
            "clock",
            compact=True,
        )
        return

    cumulative: List[int] = []
    running = 0
    for _, count in rows:
        running += int(count)
        cumulative.append(running)

    frame = pd.DataFrame(
        {
            "Tháng": [month_label(month) for month, _ in rows],
            "Tổng lượt (tích luỹ)": cumulative,
        }
    )
    chart = (
        alt.Chart(frame)
        .mark_area(color=tokens.COLOR_ACCENT, opacity=0.16, line={"color": tokens.COLOR_PRIMARY, "size": 2.5}, interpolate="monotone")
        .encode(
            x=alt.X("Tháng:N", title=None, sort=None, axis=_axis_labels(labelAngle=0, grid=False)),
            y=alt.Y("Tổng lượt (tích luỹ):Q", title=None, axis=_value_axis()),
            tooltip=[
                alt.Tooltip("Tháng:N", title="Tháng"),
                alt.Tooltip("Tổng lượt (tích luỹ):Q", title="Tổng lượt"),
            ],
        )
        .properties(height=CHART_HEIGHT, background="transparent")
        .configure_view(stroke=None, fill="transparent")
        .configure(font=CHART_FONT)
    )
    st.altair_chart(chart, width="stretch")

    total_borrows = int(stats.get("total_borrows", 0) or 0)
    currently = int(stats.get("currently_borrowed", 0) or 0)
    returned = max(total_borrows - currently, 0)
    st.markdown(
        f'<div class="trend-summary">'
        f'<div class="trend-cell"><span>Tổng lượt mượn</span><strong>{total_borrows}</strong></div>'
        f'<div class="trend-cell"><span>Đang mượn</span><strong>{currently}</strong></div>'
        f'<div class="trend-cell"><span>Đã trả</span><strong>{returned}</strong></div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def render_weekday_bars(rows: Sequence[Tuple[str, int]]) -> None:
    """
    Biểu đồ CỘT — "Ngày mượn nhiều nhất trong tuần" (Most Day Active).

    `rows` = statistics.borrows_by_weekday (đủ 7 nhãn Thứ 2 -> Chủ nhật, kể cả
    0 lượt để trục ổn định). Cột cao nhất tô đậm + nhãn số trên đỉnh; các cột
    còn lại nhạt. Không có lượt nào -> empty state (không bịa đỉnh giả).
    """
    counts = [int(count) for _, count in rows]
    if not rows or sum(counts) == 0:
        render_empty_state(
            "Chưa có dữ liệu theo ngày trong tuần.",
            "Số liệu sẽ xuất hiện khi có phiếu mượn với ngày hợp lệ.",
            "clock",
            compact=True,
        )
        return

    peak = max(counts)
    peak_label = next(label for label, count in rows if int(count) == peak)
    frame = pd.DataFrame(
        {"Ngày": [label for label, _ in rows], "Số lượt": counts}
    )
    base = alt.Chart(frame).encode(
        x=alt.X("Ngày:N", title=None, sort=None,
                axis=_axis_labels(labelLimit=80, grid=False)),
        y=alt.Y("Số lượt:Q", title=None, axis=_value_axis()),
        tooltip=[
            alt.Tooltip("Ngày:N", title="Ngày"),
            alt.Tooltip("Số lượt:Q", title="Số lượt"),
        ],
    )
    bars = base.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        color=alt.condition(
            alt.datum["Số lượt"] == peak,
            alt.value(tokens.STATUS["info"]["base"]),
            alt.value(tokens.COLOR_BORDER),
        )
    )
    labels = base.mark_text(dy=-8, fontSize=12, fontWeight="bold", color=tokens.COLOR_TEXT).encode(
        text="Số lượt:Q"
    )
    chart = (
        (bars + labels)
        .properties(height=232, background="transparent")
        .configure_view(stroke=None, fill="transparent")
        .configure(font=CHART_FONT)
    )
    st.altair_chart(chart, width="stretch")
    st.markdown(
        f'<div class="chart-footer"><span>Ngày cao điểm</span>'
        f"<strong>{esc(peak_label)} · {peak}</strong></div>",
        unsafe_allow_html=True,
    )


def render_rate_gauge(rate: float, caption: str) -> None:
    """
    Gauge BÁN NGUYỆT cho tỷ lệ 0–100 (VD: tỷ lệ trả đúng hạn).

    Vẽ bằng 2 cung Altair: track nhạt 180° + cung giá trị theo đúng tỷ lệ thật
    + số % ở giữa. `rate` ngoài khoảng sẽ bị kẹp về [0, 100], không crash.
    """
    try:
        value = max(0.0, min(100.0, float(rate)))
    except (TypeError, ValueError):
        value = 0.0
    track = (
        alt.Chart(pd.DataFrame({"frac": [1.0]}))
        .mark_arc(innerRadius=58, outerRadius=86, cornerRadius=4,
                  color=tokens.COLOR_BORDER, opacity=0.55)
        .encode(theta=alt.Theta("frac:Q", scale=alt.Scale(domain=[0, 1], range=[0, 3.14159])))
    )
    fill = (
        alt.Chart(pd.DataFrame({"frac": [value / 100.0]}))
        .mark_arc(innerRadius=58, outerRadius=86, cornerRadius=4,
                  color=tokens.STATUS["success"]["base"])
        .encode(theta=alt.Theta("frac:Q", scale=alt.Scale(domain=[0, 1], range=[0, 3.14159])))
    )
    number = (
        alt.Chart(pd.DataFrame({"text": [f"{value:.1f}%".replace(".", ",")]}))
        .mark_text(fontSize=30, fontWeight="bold", color=tokens.COLOR_TEXT, dy=6)
        .encode(text="text:N")
    )
    chart = (
        (track + fill + number)
        .properties(height=190, background="transparent")
        .configure_view(stroke=None, fill="transparent")
        .configure(font=CHART_FONT)
    )
    st.markdown('<div class="gauge-wrap">', unsafe_allow_html=True)
    st.altair_chart(chart, width="stretch")
    st.markdown(f'<div class="gauge-caption">{esc(caption)}</div></div>', unsafe_allow_html=True)


def render_activity_timeline(
    joined_records: Sequence[Dict[str, Any]],
    devices_by_id: Dict[str, Dict[str, Any]],
    borrowers_by_id: Dict[str, Dict[str, Any]],
    limit: int = 6,
) -> None:
    """
    "Hoạt động gần đây" — timeline đọc hiểu từ NGÀY THẬT của phiếu.

    KHÔNG có giờ-phút trong schema nên KHÔNG bịa "10 phút trước": dòng mới
    nhất được xếp lên trên theo ngày mượn (format_date giữ nguyên dữ liệu lỗi
    để không che dữ liệu sai). Người mượn/thiết bị tra qua Dictionary thật.
    """
    if not joined_records:
        render_empty_state(
            "Chưa có hoạt động nào.",
            "Các phiếu mượn gần nhất sẽ xuất hiện ở đây.",
            "clock",
            compact=True,
        )
        return

    def _sort_key(record: Dict[str, Any]) -> str:
        from cleaners import parse_date  # import cục bộ: tránh vòng phụ thuộc khi nạp module

        parsed = parse_date(record.get("borrow_date"))
        return parsed.isoformat() if parsed else ""

    recent = sorted(joined_records, key=_sort_key, reverse=True)[:limit]

    items: List[str] = []
    for record in recent:
        status = str(record.get("status", "")).strip().lower()
        returned = status == "returned"
        borrower_id = str(record.get("borrower_id", "")).strip()
        device_id = str(record.get("device_id", "")).strip()
        borrower = borrowers_by_id.get(borrower_id, {})
        device = devices_by_id.get(device_id, {})
        name = str(borrower.get("name", "")).strip() or borrower_id or "—"
        device_name = str(device.get("device_name", "")).strip() or device_id or "—"
        verb = "Trả" if returned else "Mượn"

        meta_bits: List[str] = []
        if record.get("borrow_date"):
            meta_bits.append(f"Mượn {month_label_day(record.get('borrow_date'))}")
        if record.get("due_date"):
            meta_bits.append(f"Hạn trả {month_label_day(record.get('due_date'))}")
        status_label_text = "Đã trả" if returned else "Đang mượn"

        item_class = "timeline-item returned" if returned else "timeline-item"
        items.append(
            f'<li class="{item_class}">'
            f'<span class="alert-marker"></span>'
            f'<div class="timeline-body">'
            f'<div class="timeline-title"><span class="timeline-id">{esc(record.get("borrow_id", ""))}</span> · {esc(name)}</div>'
            f'<div class="timeline-desc">{verb} {esc(device_name)}</div>'
            f'<div class="timeline-meta">{" · ".join(esc(bit) for bit in meta_bits)} · {esc(status_label_text)}</div>'
            f"</div></li>"
        )

    st.markdown(
        f'<ul class="timeline" role="list" aria-label="Hoạt động mượn gần đây">{"".join(items)}</ul>',
        unsafe_allow_html=True,
    )


def month_label_day(value: Any) -> str:
    """'2026-06-01' / '01/06/2026' -> 'dd/mm/yyyy' (giữ nguyên dữ liệu lỗi)."""
    from cleaners import parse_date  # import cục bộ

    parsed = parse_date(value)
    return parsed.strftime("%d/%m/%Y") if parsed else str(value or "")


def render_monthly_trend(rows: Sequence[Tuple[str, int]], footer_total: int) -> None:
    """
    Biểu đồ ĐƯỜNG — "Lượt mượn theo thời gian" (trang Báo cáo).

    `rows` = [(YYYY-MM, số lượt), ...] sinh từ statistics.borrows_by_month,
    tức chỉ gồm tháng THẬT SỰ có phiếu mượn (không nội suy tháng trống).
    """
    if not rows:
        render_empty_state(
            "Chưa có dữ liệu lượt mượn theo thời gian.",
            "Dữ liệu cần ngày mượn hợp lệ để tổng hợp theo tháng.",
            "clock",
            compact=True,
        )
        return

    frame = pd.DataFrame(
        {
            "Tháng": [month_label(month) for month, _ in rows],
            "Số lượt": [count for _, count in rows],
        }
    )
    chart = (
        alt.Chart(frame)
        .mark_line(
            color=tokens.COLOR_PRIMARY,
            strokeWidth=2.5,
            point=alt.OverlayMarkDef(color=tokens.COLOR_PRIMARY, size=55, filled=True),
        )
        .encode(
            x=alt.X("Tháng:N", title=None, sort=None, axis=_axis_labels(labelAngle=0, grid=False)),
            y=alt.Y("Số lượt:Q", title=None, axis=_value_axis()),
            tooltip=[
                alt.Tooltip("Tháng:N", title="Tháng"),
                alt.Tooltip("Số lượt:Q", title="Số lượt mượn"),
            ],
        )
        .properties(height=CHART_HEIGHT, background="transparent")
        .configure_view(stroke=None, fill="transparent")
        .configure(font=CHART_FONT)
    )
    st.altair_chart(chart, width="stretch")
    st.markdown(
        f'<div class="chart-footer"><span>Tổng lượt mượn theo tháng</span>'
        f"<strong>{footer_total}</strong></div>",
        unsafe_allow_html=True,
    )
