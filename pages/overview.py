# -*- coding: utf-8 -*-
"""
pages/overview.py — TRANG TỔNG QUAN
===================================
Cho người quản lý nắm tình trạng hệ thống trong vài giây: KPI -> analytics ->
bảng vận hành -> cảnh báo -> xếp hạng.

Trang này KHÔNG có CRUD. Toàn bộ số liệu đến từ `main.run_pipeline` (đã được
`ui.app_shell` nạp và cache) và các hàm statistics/validators hiện có — phần
lọc dữ liệu giữ nguyên đúng thứ tự của bản gốc: thời gian -> loại thiết bị ->
trạng thái -> tìm kiếm.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import statistics as stat_mod
import streamlit as st
import validators

from pages.common import apply_listing_filters, render_first_run_guide
from ui.app_shell import goto_page
from ui.charts import (
    render_activity_timeline,
    render_category_chart,
    render_rate_gauge,
    render_trend_area,
    render_weekday_bars,
)
from ui.filters import render_filter_bar, reset_filters
from ui.layout import analytics_grid, card_header, page_header
from ui.metrics import MetricCard, render_kpi_grid
from ui.tables import (
    render_borrow_table,
    render_top_devices_table,
)
from utils.helpers import esc, previous_window, time_filter_records

#: Kết quả thống kê rỗng khi bộ lọc không trả về phiếu nào (giữ nguyên key
#: như bản gốc để phần render phía dưới không phải xử lý đặc biệt).
_EMPTY_STATS: Dict[str, Any] = {
    "total_borrows": 0,
    "currently_borrowed": 0,
    "overdue_count": 0,
    "lost_count": 0,
    "top_devices": [],
    "top_borrowers": [],
    "borrows_by_category": [],
    "joined_records": [],
    "devices_by_id": {},
    "borrowers_by_id": {},
    "overdue_days": [],
    "lost_ids": [],
}


def render(analysis: Dict[str, Any]) -> None:
    base_devices: List[Dict[str, Any]] = analysis.get("devices", [])
    base_borrowers: List[Dict[str, Any]] = analysis.get("borrowers", [])
    base_records: List[Dict[str, Any]] = analysis.get("records", [])
    today = date.today()

    page_header(
        "Dashboard",
        "Theo dõi tình trạng thiết bị và hoạt động mượn.",
        meta=(
            f"{len(base_devices)} thiết bị · {len(base_borrowers)} người mượn · "
            f"{len(base_records)} phiếu mượn hợp lệ"
        ),
    )

    if render_first_run_guide(analysis):
        return

    filter_state = render_filter_bar(base_devices)

    # ------------------------------------------------------------------
    # Lọc dữ liệu — giữ nguyên thuật toán của bản gốc
    # ------------------------------------------------------------------
    devices_by_id = stat_mod.build_devices_by_id(base_devices)
    borrowers_by_id = stat_mod.build_borrowers_by_id(base_borrowers)
    filtered_records = time_filter_records(
        base_records, filter_state.time_filter, filter_state.custom_start, filter_state.custom_end
    )
    filters_active = (
        filter_state.time_filter != "Tất cả"
        or filter_state.category_filter != "Tất cả"
        or filter_state.status_filter != "Tất cả"
        or bool(filter_state.search_query.strip())
    )

    filtered_records = apply_listing_filters(
        filtered_records,
        category=filter_state.category_filter,
        status=filter_state.status_filter,
        search=filter_state.search_query,
        devices_by_id=devices_by_id,
        borrowers_by_id=borrowers_by_id,
        today=today,
    )

    filtered_record_device_ids = {str(r.get("device_id", "")).strip() for r in filtered_records}
    filtered_record_borrower_ids = {str(r.get("borrower_id", "")).strip() for r in filtered_records}
    if filters_active:
        filtered_devices = [
            d for d in base_devices if str(d.get("device_id", "")).strip() in filtered_record_device_ids
        ]
        filtered_borrowers = [
            b for b in base_borrowers if str(b.get("borrower_id", "")).strip() in filtered_record_borrower_ids
        ]
    else:
        filtered_devices = list(base_devices)
        filtered_borrowers = list(base_borrowers)

    if filtered_records:
        overdue_records = validators.find_overdue_records(filtered_records, today)
        lost_ids = validators.find_lost_devices(filtered_records, today)
        stats = stat_mod.compute_all(
            filtered_devices,
            filtered_borrowers,
            filtered_records,
            overdue_records=overdue_records,
            lost_devices=lost_ids,
            today=today,
        )
    else:
        stats = dict(_EMPTY_STATS)

    # ------------------------------------------------------------------
    # Pill delta KPI: kỳ hiện tại so với kỳ trước liền kề cùng độ dài.
    # Mọi con số đều tính từ dữ liệu thật; không có cơ sở so sánh thì ẨN pill.
    # "Tổng thiết bị" là danh mục tại một thời điểm nên không có delta.
    # ------------------------------------------------------------------
    prev_bounds = previous_window(
        filter_state.time_filter, filter_state.custom_start, filter_state.custom_end, today
    )
    delta_active = delta_overdue = delta_lost = ""
    tone_overdue = tone_lost = ""
    if prev_bounds is not None and filtered_records:
        prev_start, prev_end = prev_bounds
        prev_records = apply_listing_filters(
            time_filter_records(base_records, "Tùy chỉnh", prev_start, prev_end),
            category=filter_state.category_filter,
            status=filter_state.status_filter,
            search=filter_state.search_query,
            devices_by_id=devices_by_id,
            borrowers_by_id=borrowers_by_id,
            today=today,
        )
        prev_active = stat_mod.count_currently_borrowed(prev_records)
        prev_overdue = validators.find_overdue_records(prev_records, prev_end)
        prev_lost = validators.find_lost_devices(prev_records, prev_end)

        currently_borrowed_now = stat_mod.count_currently_borrowed(filtered_records)
        overdue_now = validators.find_overdue_records(filtered_records, today)
        lost_now = validators.find_lost_devices(filtered_records, today)

        delta_active = stat_mod.format_delta(currently_borrowed_now, prev_active) or ""
        delta_overdue = stat_mod.format_delta(len(overdue_now), len(prev_overdue)) or ""
        if delta_overdue:
            tone_overdue = "good" if len(overdue_now) <= len(prev_overdue) else "bad"
        delta_lost = stat_mod.format_delta(len(lost_now), len(prev_lost)) or ""
        if delta_lost:
            tone_lost = "good" if len(lost_now) <= len(prev_lost) else "bad"

    # ------------------------------------------------------------------
    # KPI — số liệu thật từ statistics.compute_all (+ delta kỳ nếu có)
    # ------------------------------------------------------------------
    available_count = sum(
        1 for d in filtered_devices if str(d.get("status", "")).strip().lower() == "available"
    )
    device_total = len(filtered_devices)
    currently_borrowed = stats.get("currently_borrowed", 0)
    utilization = (currently_borrowed / device_total * 100) if device_total else 0
    availability = (available_count / device_total * 100) if device_total else 0
    overdue_count = int(stats.get("overdue_count", 0) or 0)
    lost_count = int(stats.get("lost_count", 0) or 0)
    on_time_rate = float(stats.get("on_time_rate", 0.0) or 0.0)

    render_kpi_grid(
        [
            MetricCard(
                "Tổng thiết bị",
                device_total,
                f"{available_count} sẵn sàng",
                "box",
                kind="share",
                percent=availability,
                mini=f"{availability:.0f}% sẵn sàng",
            ),
            MetricCard(
                "Đang mượn",
                currently_borrowed,
                f"{utilization:.1f}% tổng số",
                "swap",
                kind="share",
                percent=utilization,
                mini="Tỷ lệ sử dụng",
                delta=delta_active,
            ),
            MetricCard(
                "Sẵn sàng",
                available_count,
                "Có thể mượn ngay",
                "check",
                kind="share",
                percent=availability,
                mini=f"{availability:.0f}% danh mục",
            ),
            MetricCard(
                "Quá hạn",
                overdue_count,
                "Phiếu trả trễ hạn",
                "clock",
                kind="alert",
                mini=f"{overdue_count} phiếu",
                delta=delta_overdue,
                delta_tone=tone_overdue,
            ),
            MetricCard(
                "Thất thoát",
                lost_count,
                "Thiết bị chưa được trả",
                "alert",
                kind="alert",
                mini=f"{lost_count} thiết bị",
                delta=delta_lost,
                delta_tone=tone_lost,
            ),
        ]
    )

    # ------------------------------------------------------------------
    # Quick actions — điều hướng thật tới các trang thao tác (không nút chết)
    # ------------------------------------------------------------------
    quick_left, quick_mid_left, quick_mid_right, quick_right = st.columns(4, gap="medium")
    with quick_left:
        st.button(
            "+ Phiếu mượn",
            key="quick_borrowing",
            on_click=goto_page,
            args=("borrowing",),
            width="stretch",
            help="Mở trang Phiếu mượn để tạo phiếu mới.",
        )
    with quick_mid_left:
        st.button(
            "+ Thiết bị",
            key="quick_equipment",
            on_click=goto_page,
            args=("equipment",),
            width="stretch",
            help="Mở trang Thiết bị để thêm thiết bị.",
        )
    with quick_mid_right:
        st.button(
            "Xem cảnh báo",
            key="quick_alerts",
            on_click=goto_page,
            args=("alerts",),
            width="stretch",
            help="Mở trang Cảnh báo để xử lý phiếu quá hạn.",
        )
    with quick_right:
        st.button(
            "Xuất báo cáo",
            key="quick_reports",
            on_click=goto_page,
            args=("reports",),
            width="stretch",
            help="Mở trang Báo cáo để xem và xuất báo cáo.",
        )

    # Thứ tự block (trên -> dưới, quan trọng -> chi tiết): header, filter,
    # KPI, thao tác nhanh, xu hướng + cảnh báo, phân tích theo nhóm, xếp hạng,
    # bảng vận hành. Panel "Cần xử lý" cạnh chart chính thay cho dải strip
    # trùng lặp nên trang gọn mà cảnh báo vẫn above-the-fold.
    # ------------------------------------------------------------------
    # VISUAL FOCAL POINT — "Hoạt động mượn thiết bị" (area chart, 8/4)
    # ------------------------------------------------------------------
    focal_left, focal_right = analytics_grid()

    with focal_left:
        with st.container(border=True):
            card_header(
                "Hoạt động mượn thiết bị",
                "Tổng lượt mượn tích luỹ theo tháng từ ngày mượn của phiếu.",
            )
            monthly = stat_mod.borrows_by_month(filtered_records)
            render_trend_area(monthly, stats)

    with focal_right:
        with st.container(border=True):
            total_alerts = (
                int(stats.get("overdue_count", 0) or 0)
                + int(stats.get("lost_count", 0) or 0)
                + len(analysis.get("errors", []))
            )
            card_header(
                "Cần xử lý",
                "Cảnh báo nghiêm trọng nhất trong bộ lọc hiện tại.",
                chip=str(total_alerts),
            )
            top_overdue = list(stats.get("overdue_days", []))[:3]
            if top_overdue:
                devices_lookup = stats.get("devices_by_id", {})
                entries = []
                for row in top_overdue:
                    device_id = str(row.get("device_id", "")).strip()
                    name = str(devices_lookup.get(device_id, {}).get("device_name", "") or "").strip()
                    label = f"{row.get('borrow_id', '')} · {name or device_id}"
                    entries.append(
                        f'<li class="rank-item">'
                        f'<div class="rank-name"><span>{esc(label)}</span></div>'
                        f'<span class="rank-meta">{int(row.get("days_overdue", 0) or 0)} ngày</span></li>'
                    )
                st.markdown(f'<ul class="rank-list">{"".join(entries)}</ul>', unsafe_allow_html=True)
            else:
                st.markdown(
                    '<div class="table-footnote">Không có cảnh báo trong bộ lọc hiện tại.</div>',
                    unsafe_allow_html=True,
                )
            st.button(
                "Xử lý ngay",
                key="summary_to_alerts",
                on_click=goto_page,
                args=("alerts",),
                width="stretch",
                help="Mở trang Cảnh báo để xử lý.",
            )

    # ------------------------------------------------------------------
    # Secondary analytics: loại thiết bị (8) + ngày trong tuần (4)
    # ------------------------------------------------------------------
    analytics_left, analytics_right = analytics_grid()

    with analytics_left:
        with st.container(border=True):
            card_header(
                "Lượt mượn theo loại thiết bị",
                "So sánh nhu cầu mượn giữa các nhóm thiết bị.",
            )
            render_category_chart(
                stats.get("borrows_by_category", []), stats.get("total_borrows", 0)
            )

    with analytics_right:
        with st.container(border=True):
            card_header(
                "Ngày mượn nhiều nhất",
                "Số lượt mượn theo ngày trong tuần.",
            )
            render_weekday_bars(stats.get("borrows_by_weekday", []))

    # ------------------------------------------------------------------
    # Best table (8) + gauge/độ phủ (4): xếp hạng cạnh chỉ số tỷ lệ
    # ------------------------------------------------------------------
    mix_left, mix_right = analytics_grid()

    with mix_left:
        with st.container(border=True):
            card_header(
                "Thiết bị được mượn nhiều",
                "Xếp hạng theo số lượt mượn trong bộ lọc hiện tại.",
                chip=str(len(stats.get("top_devices", [])[:6])),
            )
            render_top_devices_table(
                stats.get("top_devices", []),
                stats.get("devices_by_id", {}),
                int(stats.get("total_borrows", 0) or 0),
            )

    with mix_right:
        with st.container(border=True):
            card_header(
                "Tỷ lệ trả đúng hạn",
                "Tính trên các phiếu đã trả trong bộ lọc hiện tại.",
            )
            returned_count = int(stats.get("returned_count", 0) or 0)
            render_rate_gauge(
                on_time_rate,
                f"{returned_count} phiếu đã trả",
            )
            st.button(
                "Xem báo cáo",
                key="gauge_to_reports",
                on_click=goto_page,
                args=("reports",),
                width="stretch",
                help="Mở trang Báo cáo để xem phân tích đầy đủ.",
            )

    with mix_right:
        with st.container(border=True):
            card_header(
                "Mức sử dụng thiết bị",
                "Thiết bị từng được mượn trên tổng danh mục.",
            )
            used_ids = {
                str(r.get("device_id", "")).strip() for r in filtered_records
            } & {
                str(d.get("device_id", "")).strip() for d in filtered_devices
            } - {""}
            use_rate = (len(used_ids) / device_total * 100) if device_total else 0.0
            st.markdown(
                f'<div class="kpi-value">{len(used_ids)}/{device_total}</div>'
                f'<div class="kpi-sub"><span class="dot"></span>{use_rate:.1f}% danh mục từng được mượn</div>'
                f'<div class="kpi-foot"><div class="kpi-bar">'
                f'<div class="kpi-bar-fill primary" style="width:{use_rate:.1f}%"></div>'
                f"</div></div>",
                unsafe_allow_html=True,
            )

    # ------------------------------------------------------------------
    # Dữ liệu vận hành + hoạt động gần đây
    # ------------------------------------------------------------------
    ops_left, ops_right = analytics_grid()

    with ops_left:
        with st.container(border=True):
            card_header(
                "Thiết bị cần theo dõi",
                "Danh sách phiếu mượn theo bộ lọc hiện tại.",
                chip=str(len(filtered_records)) if filtered_records else "",
            )
            render_borrow_table(
                stats.get("joined_records", []), on_empty_reset=reset_filters
            )

    with ops_right:
        with st.container(border=True):
            card_header(
                "Hoạt động gần đây",
                "Phiếu mượn mới nhất xếp theo ngày mượn.",
            )
            render_activity_timeline(
                stats.get("joined_records", []), stats.get("devices_by_id", {}), stats.get("borrowers_by_id", {})
            )

