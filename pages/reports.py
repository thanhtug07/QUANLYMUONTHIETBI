# -*- coding: utf-8 -*-
"""
pages/reports.py — TRANG BÁO CÁO
================================
Phân tích tổng hợp toàn bộ dữ liệu (không theo bộ lọc của trang Tổng quan):

    KPI  ->  lượt mượn theo loại  ->  phân bố trạng thái (donut)
         ->  lượt mượn theo thời gian  ->  xếp hạng  ->  báo cáo văn bản.

Mọi số liệu lấy từ `analysis["stats"]` (statistics.compute_all) và
`reports.build_report_text` — trang này KHÔNG tự tính lại hay tạo dữ liệu mới.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

import statistics as stat_mod
import streamlit as st

from pages.common import device_status_counts
from ui.app_shell import data_signature
from utils.excel_export import build_workbook
from ui.charts import render_category_chart, render_monthly_trend, render_status_donut
from ui.layout import card_header, page_header, two_column_grid
from ui.metrics import MetricCard, render_kpi_grid
from ui.states import render_empty_state
from ui.tables import render_rank_panel
from utils.helpers import esc

#: Số cảnh báo nghiệp vụ tối đa hiển thị trong panel.
WARNING_LIMIT = 10


def warning_severity(text: str) -> str:
    """
    Mức độ của một cảnh báo nghiệp vụ (thuần để test được): "danger" cho mất
    mát/tham chiếu gãy/trùng mã, "warning" cho các lỗi dữ liệu còn lại.
    """
    lowered = str(text or "").lower()
    if ("quá hạn" in lowered or "thất thoát" in lowered
            or "không tồn tại" in lowered or "trùng mã" in lowered):
        return "danger"
    return "warning"


def _render_warnings(warnings: Sequence[str]) -> None:
    if not warnings:
        render_empty_state(
            "Không có cảnh báo nghiệp vụ.",
            "Dữ liệu hiện tại không phát sinh cảnh báo từ tầng kiểm tra.",
            "report",
            compact=True,
        )
        return

    rows = "".join(
        f'<div class="warning-row sev-{warning_severity(warning)}" role="listitem">'
        f'<span class="alert-marker"></span><span>{esc(warning)}</span></div>'
        for warning in list(warnings)[:WARNING_LIMIT]
    )
    st.markdown(f'<div class="warning-list" role="list">{rows}</div>', unsafe_allow_html=True)
    remaining = len(warnings) - WARNING_LIMIT
    if remaining > 0:
        st.markdown(
            f'<div class="table-footnote">Còn {remaining} cảnh báo khác.</div>',
            unsafe_allow_html=True,
        )


@st.cache_data(show_spinner=False, max_entries=4)
def _excel_cached(signature: Any, _analysis: Dict[str, Any]) -> bytes:
    """Cache workbook theo chữ ký dữ liệu CSV (không dựng lại ở mỗi lần rerun)."""
    return build_workbook(_analysis)


def _excel_bytes(analysis: Dict[str, Any]) -> bytes:
    """Workbook Excel của báo cáo (lỗi dựng file -> bytes rỗng, không crash trang)."""
    try:
        return _excel_cached(data_signature(), analysis)
    except Exception:  # pragma: no cover - phòng thiếu openpyxl khi triển khai
        return b""


def render(analysis: Dict[str, Any]) -> None:
    stats: Dict[str, Any] = analysis.get("stats") or {}
    devices: List[Dict[str, Any]] = analysis.get("devices", [])
    borrowers: List[Dict[str, Any]] = analysis.get("borrowers", [])
    records: List[Dict[str, Any]] = analysis.get("records", [])

    page_header(
        "Báo cáo",
        "Phân tích và tổng hợp dữ liệu mượn thiết bị.",
        meta=(
            f"Toàn bộ dữ liệu: {len(records)} phiếu mượn · {len(devices)} thiết bị · "
            f"{len(borrowers)} người mượn."
        ),
    )

    render_kpi_grid(
        [
            MetricCard("Tổng lượt mượn", stats.get("total_borrows", 0), "Toàn bộ phiếu mượn", "receipt"),
            MetricCard("Đang mượn", stats.get("currently_borrowed", 0), "Chưa trả thiết bị", "swap"),
            MetricCard("Quá hạn", stats.get("overdue_count", 0), "Cần xử lý", "clock"),
            MetricCard("Thất thoát", stats.get("lost_count", 0), "Cần kiểm tra", "alert"),
        ]
    )

    # ------------------------------------------------------------------
    # Biểu đồ A (lớn) + biểu đồ B (phụ)
    # ------------------------------------------------------------------
    left, right = st.columns([8, 4], gap="medium")

    with left:
        with st.container(border=True):
            card_header(
                "Lượt mượn theo loại thiết bị",
                "Số lượt mượn theo từng nhóm thiết bị, giảm dần.",
            )
            render_category_chart(
                stats.get("borrows_by_category", []), stats.get("total_borrows", 0)
            )

    with right:
        with st.container(border=True):
            card_header("Phân bố trạng thái", "Tỷ lệ thiết bị theo trạng thái danh mục.")
            render_status_donut(device_status_counts(devices), str(len(devices)))

    # ------------------------------------------------------------------
    # Biểu đồ C — chỉ dựng khi dữ liệu thật sự có mốc thời gian
    # ------------------------------------------------------------------
    monthly = stats.get("borrows_by_month") or stat_mod.borrows_by_month(records)
    with st.container(border=True):
        card_header(
            "Lượt mượn theo thời gian",
            "Tổng hợp theo tháng từ ngày mượn của phiếu (chỉ gồm tháng có dữ liệu).",
        )
        render_monthly_trend(monthly, sum(count for _, count in monthly))

    # ------------------------------------------------------------------
    # Xếp hạng + cảnh báo nghiệp vụ (cảnh báo trước: ưu tiên xử lý)
    # ------------------------------------------------------------------
    with st.container(border=True):
        card_header(
            "Cảnh báo nghiệp vụ",
            "Tổng hợp từ kiểm tra dữ liệu tự động.",
            chip=str(len(analysis.get("warnings", []))),
        )
        _render_warnings(analysis.get("warnings", []))

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

    # ------------------------------------------------------------------
    # Báo cáo văn bản (reports.build_report_text — không tính lại số liệu).
    # Gọn trong expander vì nội dung dài mà số liệu đã có ở các chart phía trên.
    # ------------------------------------------------------------------
    report_text = str(analysis.get("report_text", "")).strip()
    with st.container(horizontal=True, gap="small", key="report_downloads"):
        st.download_button(
            "Tải báo cáo Excel (.xlsx)",
            data=_excel_bytes(analysis),
            file_name="bao_cao_muon_thiet_bi.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="report_download_xlsx",
            type="primary",
            icon=":material/table_view:",
            width="content",
            help="8 sheet: Tổng hợp, Phiếu mượn, Thiết bị, Người mượn, Quá hạn, Theo loại, Top thiết bị, Top người mượn.",
        )
        if report_text:
            st.download_button(
                "Tải báo cáo tổng hợp (.txt)",
                data=("\ufeff" + report_text).encode("utf-8"),
                file_name="report.txt",
                mime="text/plain",
                key="report_download_txt",
                width="content",
                help="Tải nội dung báo cáo 8 phần dạng văn bản (.txt).",
            )
    with st.expander("Báo cáo tổng hợp (văn bản)", expanded=False):
        if report_text:
            st.code(report_text, language=None)
        else:
            render_empty_state(
                "Chưa có nội dung báo cáo.",
                "Báo cáo được tạo khi có dữ liệu hợp lệ.",
                "report",
                compact=True,
            )
