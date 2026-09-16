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

from pages.common import device_status_counts, render_first_run_guide
from ui.app_shell import goto_page
from ui.charts import (
    render_activity_timeline,
    render_category_chart,
    render_status_bars,
    render_top_category_chart,
    render_trend_area,
)
from ui.filters import render_filter_bar, reset_filters
from ui.layout import analytics_grid, card_header, page_header, two_column_grid
from ui.metrics import MetricCard, render_kpi_grid
from ui.tables import (
    build_alert_rows,
    render_alert_card,
    render_borrow_table,
    render_rank_panel,
)
from utils.helpers import time_filter_records

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

    page_header(
        "Quản lý mượn thiết bị",
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

    if filter_state.category_filter != "Tất cả":
        filtered_records = stat_mod.filter_by_category(
            filtered_records, filter_state.category_filter, devices_by_id
        )

    if filter_state.status_filter == "Đang mượn":
        filtered_records = stat_mod.filter_by_status(filtered_records, "borrowing")
    elif filter_state.status_filter == "Đã trả":
        filtered_records = stat_mod.filter_by_status(filtered_records, "returned")
    elif filter_state.status_filter == "Quá hạn":
        filtered_records = stat_mod.filter_overdue(filtered_records, date.today())
    elif filter_state.status_filter == "Thất thoát":
        lost_record_ids = set(validators.find_lost_devices(filtered_records, date.today()))
        filtered_records = [
            r for r in filtered_records if str(r.get("device_id", "")).strip() in lost_record_ids
        ]

    filtered_records = stat_mod.search_records(
        filtered_records,
        filter_state.search_query,
        devices_by_id=devices_by_id,
        borrowers_by_id=borrowers_by_id,
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
        overdue_records = validators.find_overdue_records(filtered_records, date.today())
        lost_ids = validators.find_lost_devices(filtered_records, date.today())
        stats = stat_mod.compute_all(
            filtered_devices,
            filtered_borrowers,
            filtered_records,
            overdue_records=overdue_records,
            lost_devices=lost_ids,
            today=date.today(),
        )
    else:
        stats = dict(_EMPTY_STATS)

    # ------------------------------------------------------------------
    # KPI — số liệu thật từ statistics.compute_all
    # Hai card đầu có chiều sâu (progress bar phần trăm), hai card cảnh báo
    # dùng badge nhấn khi số > 0. Không thêm màu mới, không fake trend.
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
            ),
            MetricCard(
                "Quá hạn",
                overdue_count,
                "Phiếu trả trễ hạn",
                "clock",
                kind="alert",
                mini=f"{overdue_count} phiếu",
            ),
            MetricCard(
                "Thất thoát",
                lost_count,
                "Thiết bị chưa được trả",
                "alert",
                kind="alert",
                mini=f"{lost_count} thiết bị",
            ),
        ]
    )

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
            card_header(
                "Trạng thái thiết bị",
                "Phân bố hiện tại của danh mục thiết bị.",
            )
            render_status_bars(device_status_counts(filtered_devices), device_total)

    # ------------------------------------------------------------------
    # Secondary analytics: loại thiết bị (8) + top loại thiết bị (4)
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
            card_header("Top loại thiết bị", "Các nhóm được mượn nhiều nhất.")
            render_top_category_chart(stats.get("borrows_by_category", []))

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

    # ------------------------------------------------------------------
    # Cảnh báo cần xử lý — 3 card có CTA dẫn thẳng tới trang tương ứng
    # ------------------------------------------------------------------
    alert_rows = build_alert_rows(stats, analysis.get("errors", []))
    card_left, card_mid, card_right = st.columns(3, gap="medium")

    with card_left:
        render_alert_card(
            "Quá hạn",
            int(stats.get("overdue_count", 0) or 0),
            "Phiếu mượn đã vượt hạn trả nhưng chưa được trả.",
            "clock",
            "Xem phiếu",
            "alert_card_overdue",
            lambda: goto_page("alerts"),
        )

    with card_mid:
        render_alert_card(
            "Thất thoát",
            int(stats.get("lost_count", 0) or 0),
            "Thiết bị đang mượn nhưng không còn trong danh mục.",
            "alert",
            "Xem thiết bị",
            "alert_card_lost",
            lambda: goto_page("alerts"),
        )

    with card_right:
        render_alert_card(
            "Dữ liệu lỗi",
            len(analysis.get("errors", [])),
            "Bản ghi lỗi khi làm sạch hoặc kiểm tra dữ liệu.",
            "database",
            "Kiểm tra dữ liệu",
            "alert_card_errors",
            lambda: goto_page("alerts"),
        )

    # ------------------------------------------------------------------
    # Xếp hạng (sorted + reverse=True từ statistics)
    # ------------------------------------------------------------------
    rank_left, rank_right = two_column_grid()

    with rank_left:
        with st.container(border=True):
            card_header("Top thiết bị được mượn", "Xếp hạng giảm dần theo số lượt mượn.")
            render_rank_panel(
                stats.get("top_devices", [])[:5], stats.get("devices_by_id", {}), "device_name"
            )

    with rank_right:
        with st.container(border=True):
            card_header("Top người mượn", "Xếp hạng giảm dần theo số lượt mượn.")
            render_rank_panel(
                stats.get("top_borrowers", [])[:5], stats.get("borrowers_by_id", {}), "name"
            )

