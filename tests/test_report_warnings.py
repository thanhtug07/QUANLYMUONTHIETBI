# -*- coding: utf-8 -*-
"""
tests/test_report_warnings.py — MỨC ĐỘ CẢNH BÁO NGHIỆP VỤ (thuần)
==================================================================
warning_severity: danger cho mất mát/tham chiếu gãy/trùng mã,
warning cho các lỗi dữ liệu còn lại.
"""
from __future__ import annotations

from pages.reports import warning_severity


def test_danger_cases():
    assert warning_severity("[QUÁ HẠN] 11 phiếu quá hạn") == "danger"
    assert warning_severity("[THẤT THOÁT] 4 thiết bị") == "danger"
    assert warning_severity("Người mượn 'SV999' không tồn tại") == "danger"
    assert warning_severity("Trùng mã 'PM001'") == "danger"


def test_warning_cases():
    assert warning_severity("Thiếu giá trị bắt buộc 'borrow_date'") == "warning"
    assert warning_severity("Phiếu status='lost' nhưng thiếu ngày trả") == "warning"
    assert warning_severity("") == "warning"
    assert warning_severity(None) == "warning"
