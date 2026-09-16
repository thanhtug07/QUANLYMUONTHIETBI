# -*- coding: utf-8 -*-
"""
ui/tables.py — DATA TABLE & PANEL PHỤ
=====================================
Chịu trách nhiệm:
- bảng dữ liệu CRUD (chọn 1 dòng để thao tác);
- bảng vận hành của trang Tổng quan;
- panel cảnh báo và panel xếp hạng.

Chỉ hiển thị field có thật trong CSV/ kết quả thống kê — không tạo field mới.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import pandas as pd
import streamlit as st

from ui.badges import status_badge
from ui.states import render_empty_state, render_no_results
from utils.helpers import esc, format_date, icon, status_label

#: Cột hiển thị của bảng phiếu mượn ở trang Tổng quan.
TABLE_COLUMNS: List[str] = ["Mã thiết bị", "Tên thiết bị", "Người mượn", "Hạn trả", "Trạng thái"]

#: Số cảnh báo tối đa hiển thị trong panel (giống bản gốc).
ALERT_LIMIT = 6

#: Số dòng tối đa của các bảng xếp hạng.
RANK_LIMIT = 5

ROW_HEIGHT = 37
MIN_TABLE_HEIGHT = 200
MAX_TABLE_HEIGHT = 520

#: Số dòng mỗi trang của bảng CRUD (pagination client-side).
PAGE_SIZE = 10


def paginate(
    rows: Sequence[Dict[str, Any]],
    page_key: str,
    page_size: int = PAGE_SIZE,
) -> tuple[List[Dict[str, Any]], int]:
    """
    Chia trang cho bảng CRUD (pagination client-side, giữ nguyên bản ghi).

    Trả về (dòng của trang hiện tại, tổng số trang). Trang lưu trong
    `st.session_state[page_key]`; đổi bộ lọc nên đưa trang về 1 (caller tự set).
    """
    total_rows = len(rows)
    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    current = int(st.session_state.get(page_key, 1) or 1)
    current = min(max(1, current), total_pages)
    start = (current - 1) * page_size
    return list(rows[start : start + page_size]), total_pages


def render_pagination(
    page_key: str,
    total_pages: int,
    shown_count: int,
    filtered_count: int,
    noun: str,
    page_size: int = PAGE_SIZE,
) -> None:
    """
    Thanh phân trang: '1–10 / 62 phiếu mượn' + Prev/Next (disabled đúng trạng thái).

    Nút là st.button thật (bàn phím/aria chuẩn); khi chỉ có 1 trang, thanh
    vẫn hiện để người dùng biết tổng số bản ghi đang hiển thị.

    `page_size` PHẢI khớp số truyền cho `paginate` — trước đây cứng PAGE_SIZE
    nên trang dùng cỡ khác (cảnh báo: 5/trang) hiện sai phạm vi dù dòng đúng.

    Trang lưu trong session_state có thể đã cũ (đổi filter/search làm tổng số
    trang co lại) nên phải kẹp về [1, total_pages] giống `paginate` — nếu không
    dòng "41–41 / 1 phiếu mượn" sẽ hiện sai dù bảng đã tự kẹp đúng trang.
    """
    stored = int(st.session_state.get(page_key, 1) or 1)
    current = min(max(1, stored), total_pages)
    if stored != current:
        st.session_state[page_key] = current  # tự lành, không cần rerun thêm
    start = (current - 1) * page_size + 1
    end = start + shown_count - 1
    range_text = f"{start}–{end} / {filtered_count} {noun}" if filtered_count else f"0 {noun}"

    # Bọc key riêng để CSS cho phép xuống dòng trên card hẹp (không chồng nút)
    # và đẩy thanh xuống đáy card (cân 2 card cạnh nhau).
    with st.container(key=f"pagination_{page_key}"):
        left, center, right = st.columns([1, 2, 1], gap="small", vertical_alignment="center")
        with left:
            st.button(
                "← Trước",
                key=f"{page_key}_prev",
                on_click=_goto_page,
                args=(page_key, current - 1),
                disabled=current <= 1,
                help="Trang trước" if current > 1 else None,
            )
        with center:
            st.markdown(
                f'<div class="pagination-info">{esc(range_text)}</div>',
                unsafe_allow_html=True,
            )
        with right:
            st.button(
                "Sau →",
                key=f"{page_key}_next",
                on_click=_goto_page,
                args=(page_key, current + 1),
                disabled=current >= total_pages,
                help="Trang sau" if current < total_pages else None,
            )


def _goto_page(page_key: str, page: int) -> None:
    """Callback nút Prev/Next — kẹp trang trong [1, tổng số trang]."""
    st.session_state[page_key] = max(1, int(page))


def table_height(row_count: int, maximum: int = MAX_TABLE_HEIGHT) -> int:
    """Chiều cao bảng theo số dòng (không để bảng rỗng quá cao hoặc quá ngắn)."""
    return int(min(maximum, max(MIN_TABLE_HEIGHT, 48 + row_count * ROW_HEIGHT)))


def render_records_table(
    rows: Sequence[Dict[str, Any]],
    columns: Sequence[str],
    key: str,
    selection: bool = False,
    height: Optional[int] = None,
    column_config: Optional[Dict[str, Any]] = None,
    on_empty_reset: Optional[Callable[[], None]] = None,
) -> List[int]:
    """
    Bảng dữ liệu SaaS.

    - `selection=True`: cho phép chọn nhiều dòng, trả về danh sách chỉ số dòng
      đang chọn. Trang CRUD dùng 1 dòng cho action đơn và nhiều dòng cho bulk.
    - Bảng rỗng -> no-results state kèm CTA đặt lại bộ lọc (`on_empty_reset`)
      thay vì một bảng trống vô nghĩa.
    """
    if not rows:
        render_no_results(on_reset=on_empty_reset)
        return []

    frame = pd.DataFrame(list(rows), columns=list(columns))
    state = st.dataframe(
        frame,
        width="stretch",
        height=height or table_height(len(rows)),
        hide_index=True,
        column_config=column_config or {},
        key=key,
        on_select="rerun" if selection else "ignore",
        selection_mode="multi-row",
    )
    if not selection:
        return []
    selected_rows = getattr(getattr(state, "selection", None), "rows", None) or []
    return [int(index) for index in selected_rows]


def render_table_footnote(text: str) -> None:
    st.markdown(f'<div class="table-footnote">{esc(text)}</div>', unsafe_allow_html=True)


def render_row_action_bar(
    label_html: str,
    actions: Sequence[Tuple[str, str, Callable[[], None], str]],
) -> None:
    """
    Action bar của dòng đang chọn: mô tả bản ghi + các nút thao tác.

    `actions` = ((nhãn, key, callback, loại button), ...) — chỉ truyền những
    thao tác hợp lệ với bản ghi đó.
    """
    with st.container(key="row_action_bar"):
        columns = st.columns([4] + [1] * len(actions), gap="small", vertical_alignment="center")
        with columns[0]:
            st.markdown(f'<div class="row-action-label">{label_html}</div>', unsafe_allow_html=True)
        for column, (action_label, action_key, callback, action_type) in zip(columns[1:], actions):
            column.button(
                action_label,
                key=action_key,
                on_click=callback,
                type="primary" if action_type == "primary" else "secondary",
                width="stretch",
            )


def csv_bytes(rows: Sequence[Dict[str, Any]], columns: Sequence[str]) -> bytes:
    """Chuyển các dòng đang hiển thị thành CSV UTF-8 có BOM để Excel mở đúng tiếng Việt."""
    if not rows:
        return "\ufeff".encode("utf-8")
    frame = pd.DataFrame(list(rows), columns=list(columns))
    return ("\ufeff" + frame.to_csv(index=False)).encode("utf-8")


def render_bulk_action_bar(
    selected_count: int,
    total_count: int,
    export_rows: Sequence[Dict[str, Any]],
    columns: Sequence[str],
    filename: str,
    delete_key: str,
    on_delete: Callable[[], None],
    export_key: str,
    extra_action: Optional[Tuple[str, str, Callable[[], None]]] = None,
) -> None:
    """
    Toolbar hiện khi đã chọn ít nhất một dòng: số lượng chọn, export selected,
    hành động bổ sung (`extra_action` = (nhãn, key, callback), vd "Đặt trạng thái")
    và bulk delete có xác nhận ở page. Trượt vào bằng animation `bar-in`.
    """
    if selected_count <= 0:
        return

    with st.container(key="bulk_action_bar"):
        n_extra = 1 if extra_action else 0
        columns_layout = st.columns(
            [3] + [1.25] * (2 + n_extra), gap="small", vertical_alignment="center"
        )
        with columns_layout[0]:
            st.markdown(
                f'<div class="row-action-label"><strong>Đã chọn {selected_count} mục</strong> '
                f'trong {total_count} mục đang hiển thị.</div>',
                unsafe_allow_html=True,
            )
        next_col = 1
        if extra_action:
            action_label, action_key, action_callback = extra_action
            with columns_layout[next_col]:
                st.button(
                    action_label,
                    key=action_key,
                    on_click=action_callback,
                    width="stretch",
                    help="Đổi trạng thái các bản ghi đang chọn.",
                )
            next_col += 1
        with columns_layout[next_col]:
            st.download_button(
                "Xuất dữ liệu",
                data=csv_bytes(export_rows, columns),
                file_name=filename,
                mime="text/csv",
                key=export_key,
                width="stretch",
                help="Xuất các bản ghi đang chọn ra CSV.",
            )
        with columns_layout[next_col + 1]:
            st.button(
                "Xóa",
                key=delete_key,
                on_click=on_delete,
                type="primary",
                width="stretch",
                help="Mở xác nhận xóa các bản ghi đang chọn.",
            )


def render_table_export(
    rows: Sequence[Dict[str, Any]],
    columns: Sequence[str],
    filename: str,
    key: str,
    label: str = "Xuất dữ liệu đang hiển thị",
) -> None:
    """Nút export toàn bộ dữ liệu sau search/filter hiện tại."""
    st.download_button(
        label,
        data=csv_bytes(rows, columns),
        file_name=filename,
        mime="text/csv",
        key=key,
        width="content",
        disabled=not rows,
        help="Xuất các bản ghi đang hiển thị sau khi áp dụng search/filter/sort.",
    )


# ----------------------------------------------------------------------
# Bảng vận hành của trang Tổng quan
# ----------------------------------------------------------------------

def _table_rows(joined_records: Sequence[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Chuyển joined_records (đã JOIN tên thiết bị / người mượn) sang dòng hiển thị."""
    return [
        {
            "Mã thiết bị": str(row.get("device_id", "") or "—"),
            "Tên thiết bị": str(row.get("device_name", "") or "—"),
            "Người mượn": str(row.get("name", "") or row.get("borrower_id", "") or "—"),
            "Hạn trả": format_date(row.get("due_date")),
            "Trạng thái": status_label(row.get("status", "")),
        }
        for row in joined_records
    ]


def render_borrow_table(
    joined_records: Sequence[Dict[str, Any]],
    key: str = "overview_table",
    on_empty_reset: Optional[Callable[[], None]] = None,
) -> None:
    """Bảng phiếu mượn theo bộ lọc (trang Tổng quan) — không có thao tác CRUD."""
    rows = _table_rows(joined_records)
    if not rows:
        render_no_results(on_reset=on_empty_reset)
        return

    frame = pd.DataFrame(rows, columns=TABLE_COLUMNS)
    st.dataframe(
        frame,
        width="stretch",
        height=table_height(len(rows), maximum=420),
        hide_index=True,
        key=key,
        column_config={
            "Mã thiết bị": st.column_config.TextColumn("Mã thiết bị", width="small"),
            "Tên thiết bị": st.column_config.TextColumn("Tên thiết bị", width="medium"),
            "Người mượn": st.column_config.TextColumn("Người mượn", width="medium"),
            "Hạn trả": st.column_config.TextColumn("Hạn trả", width="small"),
            "Trạng thái": st.column_config.TextColumn("Trạng thái", width="small"),
        },
    )
    render_table_footnote(f"Hiển thị {len(rows)} phiếu mượn theo bộ lọc hiện tại.")


# ----------------------------------------------------------------------
# Panel cảnh báo
# ----------------------------------------------------------------------

def build_alert_rows(
    stats: Dict[str, Any], errors: Optional[Sequence[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """
    Gom cảnh báo từ 3 nguồn (giữ nguyên logic bản gốc):
    phiếu quá hạn, thiết bị thất thoát, bản ghi dữ liệu lỗi.
    """
    rows: List[Dict[str, Any]] = []

    for row in stats.get("overdue_days", []):
        rows.append(
            {
                "type": "Quá hạn",
                "id": row.get("borrow_id", ""),
                "borrower": row.get("name", "") or row.get("borrower_id", ""),
                "device": row.get("device_id", "") or row.get("device_name", ""),
                "message": f"{row.get('days_overdue', 0)} ngày quá hạn",
                "record": row,
            }
        )

    for device_id in stats.get("lost_ids", []):
        rows.append(
            {
                "type": "Thất thoát",
                "id": device_id,
                "borrower": "Chưa xác định",
                "device": device_id,
                "message": "Cần kiểm tra",
                "record": {},
            }
        )

    for warning in errors or []:
        rows.append(
            {
                "type": "Dữ liệu lỗi",
                "id": str(warning.get("field", "")).strip() or "Dữ liệu",
                "borrower": "",
                "device": str(warning.get("value", "")).strip() or "",
                "message": str(warning.get("error", "")),
                "record": warning,
            }
        )

    return rows


def render_alert_card(
    title: str,
    count: int,
    description: str,
    icon_name: str,
    cta_label: str,
    cta_key: str,
    on_cta: Callable[[], None],
) -> None:
    """
    Card cảnh báo trên trang Tổng quan: icon + tiêu đề + SỐ THẬT + mô tả + CTA.

    Vỏ card là `st.container(border=True)` — đúng hệ card chung của app nên nút
    CTA (button thật, bàn phím/aria) nằm TRONG card, không phải HTML chia block.
    Số đếm luôn là số liệu thật truyền vào; màu chỉ nằm ở icon chip — không dùng
    màu làm tín hiệu duy nhất.
    """
    with st.container(border=True):
        st.markdown(
            f'<div class="alert-card-top">'
            f'<span class="alert-card-icon">{icon(icon_name, 18)}</span>'
            f'<span class="alert-card-title">{esc(title)}</span>'
            f'<span class="alert-card-count">{int(count)}</span>'
            f"</div>"
            f'<div class="alert-card-desc">{esc(description)}</div>',
            unsafe_allow_html=True,
        )
        with st.container(key=f"alert_card_cta_{cta_key}"):
            st.button(cta_label, key=cta_key, on_click=on_cta, width="stretch")


def render_alerts_panel(alert_rows: Sequence[Dict[str, Any]]) -> None:
    """Panel cảnh báo cần xử lý (tối đa ALERT_LIMIT dòng + số còn lại)."""
    if not alert_rows:
        render_empty_state(
            "Không có cảnh báo cần xử lý.",
            "Không phát hiện phiếu quá hạn, thiết bị thất thoát hay bản ghi lỗi trong bộ lọc hiện tại.",
            "report",
            compact=True,
        )
        return

    items: List[str] = []
    for row in list(alert_rows)[:ALERT_LIMIT]:
        borrower = esc(row.get("borrower", ""))
        device = esc(row.get("device", ""))
        detail = f"<span>{borrower}</span>" if borrower else ""
        if device:
            detail += f'<span class="alert-sep">•</span><span>{device}</span>'
        items.append(
            f'<div class="alert-item" role="listitem">'
            f'<div class="alert-top">'
            f'<div class="alert-type"><span class="alert-marker"></span>{esc(row.get("type", ""))}</div>'
            f'<div class="alert-meta">{esc(row.get("message", ""))}</div>'
            f"</div>"
            f'<div class="alert-body"><span class="alert-id">{esc(row.get("id", ""))}</span>{detail}</div>'
            f"</div>"
        )
    st.markdown(f'<div role="list">{"".join(items)}</div>', unsafe_allow_html=True)

    remaining = len(alert_rows) - ALERT_LIMIT
    if remaining > 0:
        st.markdown(
            f'<div class="table-footnote">Còn {remaining} cảnh báo khác chưa hiển thị.</div>',
            unsafe_allow_html=True,
        )


#: Số dòng tối đa của bảng thiết bị nổi bật (trang Tổng quan).
BEST_TABLE_LIMIT = 6


def render_top_devices_table(
    top_devices: Sequence[Tuple[str, int]],
    devices_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
    total_borrows: int = 0,
) -> None:
    """
    Bảng "Thiết bị được mượn nhiều" — ID / Tên / Lượt / Tỷ lệ / Trạng thái.

    Mọi ô đều từ dữ liệu thật (top từ statistics, tên/loại/trạng thái JOIN qua
    devices_by_id); tỷ lệ = lượt / tổng lượt. Trạng thái dùng cùng status_badge
    toàn app. Rỗng -> empty state.
    """
    items = list(top_devices)[:BEST_TABLE_LIMIT]
    if not items or not total_borrows:
        render_empty_state(
            "Chưa đủ dữ liệu để xếp hạng thiết bị.",
            "Số liệu sẽ xuất hiện khi có phiếu mượn phù hợp bộ lọc hiện tại.",
            "box",
            compact=True,
        )
        return

    devices_by_id = devices_by_id or {}
    body: List[str] = []
    for index, (device_id, count) in enumerate(items, start=1):
        device = devices_by_id.get(str(device_id), {})
        name = str(device.get("device_name", "")).strip() or "—"
        category = str(device.get("category", "")).strip()
        share = 100.0 * int(count) / total_borrows
        body.append(
            f"<tr>"
            f'<td><span class="best-rank">{index}</span></td>'
            f'<td class="best-id">{esc(device_id)}</td>'
            f'<td><div class="best-name">{esc(name)}</div>'
            f'<div class="best-cat">{esc(category)}</div></td>'
            f'<td class="num best-count">{int(count)}</td>'
            f'<td class="num best-share">{share:.1f}%</td>'
            f"<td>{status_badge(status_label(device.get('status', '')))}</td>"
            f"</tr>"
        )
    st.markdown(
        f'<table class="best-table"><thead><tr>'
        f"<th>#</th><th>Mã</th><th>Tên thiết bị</th>"
        f'<th class="num">Lượt</th><th class="num">Tỷ lệ</th><th>Trạng thái</th>'
        f"</tr></thead><tbody>{''.join(body)}</tbody></table>",
        unsafe_allow_html=True,
    )


def render_rank_panel(
    items: Sequence[Tuple[str, int]],
    lookup: Optional[Dict[str, Dict[str, Any]]] = None,
    label_key: str = "device_name",
    unit: str = "lượt",
) -> None:
    """
    Panel xếp hạng (giữ thứ tự giảm dần từ statistics: sorted + reverse=True).

    Nếu tra được tên qua Dictionary (devices_by_id / borrowers_by_id) thì
    hiển thị "mã · tên" — vẫn là dữ liệu thật, không sinh thêm nội dung.
    """
    if not items:
        render_empty_state("Chưa đủ dữ liệu để xếp hạng.", "", "report", compact=True)
        return

    lookup = lookup or {}
    entries: List[str] = []
    for index, (item_id, count) in enumerate(list(items)[:RANK_LIMIT], start=1):
        name = str(lookup.get(item_id, {}).get(label_key, "") or "").strip()
        label = f"{esc(item_id)} · {esc(name)}" if name else esc(item_id)
        entries.append(
            f'<li class="rank-item">'
            f'<div class="rank-name"><span class="rank-num">{index:02d}</span><span>{label}</span></div>'
            f'<span class="rank-meta">{int(count)} {esc(unit)}</span></li>'
        )
    st.markdown(f'<ul class="rank-list">{"".join(entries)}</ul>', unsafe_allow_html=True)
