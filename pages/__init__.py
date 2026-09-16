# -*- coding: utf-8 -*-
"""
pages/ — CÁC MODULE NGHIỆP VỤ CỦA ỨNG DỤNG
==========================================
Mỗi mục trên sidebar là một module riêng, có đúng một hàm `render(analysis)`:

    overview.py   Tổng quan (dashboard, không CRUD)
    borrowing.py  Phiếu mượn (CRUD)
    equipment.py  Thiết bị (CRUD)
    borrowers.py  Người mượn (CRUD)
    alerts.py     Cảnh báo (operational monitoring)
    reports.py    Báo cáo (analytics + báo cáo văn bản)
    csv_data.py   Dữ liệu CSV (upload / kiểm tra)

`app.py` là dispatcher duy nhất: nạp dữ liệu qua `ui.app_shell`, dựng shell
(sidebar + topbar) rồi gọi `render(analysis)` của page đang mở.
"""
from __future__ import annotations

from typing import Tuple

#: Thứ tự slug page (không import module ở đây để tránh vòng import).
PAGE_SLUGS: Tuple[str, ...] = (
    "overview",
    "borrowing",
    "equipment",
    "borrowers",
    "alerts",
    "reports",
    "csv",
)

DEFAULT_PAGE = "overview"
