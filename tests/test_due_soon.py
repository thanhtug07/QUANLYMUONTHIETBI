# -*- coding: utf-8 -*-
"""Kiểm thử validators.find_due_soon_records (nhắc phiếu sắp đến hạn)."""
from datetime import date

import validators

TODAY = date(2026, 9, 16)


def _rec(borrow_id, due, return_date="", status="borrowed"):
    return {"borrow_id": borrow_id, "due_date": due, "return_date": return_date, "status": status}


def test_due_soon_window_and_order():
    records = [
        _rec("PM1", "2026-09-19"),  # còn 3 ngày -> lấy
        _rec("PM2", "2026-09-16"),  # hạn hôm nay -> lấy, đứng đầu
        _rec("PM3", "2026-09-20"),  # còn 4 ngày -> ngoài cửa sổ
        _rec("PM4", "2026-09-15"),  # đã quá hạn -> thuộc nhóm quá hạn
        _rec("PM5", "2026-09-17", return_date="2026-09-10"),  # đã trả
        _rec("PM6", "2026-09-17", status="lost"),  # đã khai báo mất
        _rec("PM7", ""),  # thiếu ngày hạn
    ]
    result = validators.find_due_soon_records(records, TODAY)
    assert [r["borrow_id"] for r in result] == ["PM2", "PM1"]
    assert [r["days_left"] for r in result] == [0, 3]


def test_due_soon_does_not_mutate_input():
    records = [_rec("PM1", "2026-09-17")]
    validators.find_due_soon_records(records, TODAY)
    assert "days_left" not in records[0]


def test_borrow_behavior_counts_and_late_flag():
    from pages.common import behavior_summary_html, borrow_behavior

    records = [
        {"borrow_id": "A", "borrower_id": "SV1", "due_date": "2026-09-01", "return_date": "2026-08-30", "status": "returned"},
        {"borrow_id": "B", "borrower_id": "SV1", "due_date": "2026-09-01", "return_date": "2026-09-05", "status": "returned"},
        {"borrow_id": "C", "borrower_id": "SV1", "due_date": "2026-09-10", "return_date": "", "status": "borrowed"},
        {"borrow_id": "D", "borrower_id": "SV2", "due_date": "2026-09-30", "return_date": "", "status": "borrowed"},
    ]
    b = borrow_behavior(records, "borrower_id", "sv1", TODAY)
    assert (b["total"], b["returned"], b["on_time"], b["late"]) == (3, 2, 1, 1)
    assert (b["active"], b["overdue"]) == (1, 1)
    assert b["on_time_rate"] == 50.0
    # 1 lần trễ + 1 phiếu đang quá hạn = 2 nhưng tỷ lệ 50% chưa dưới ngưỡng
    assert b["late_flag"] is False

    records.append(
        {"borrow_id": "E", "borrower_id": "SV1", "due_date": "2026-08-01", "return_date": "2026-08-09", "status": "returned"}
    )
    b2 = borrow_behavior(records, "borrower_id", "SV1", TODAY)
    assert b2["late_flag"] is True
    assert "thường trả trễ" in behavior_summary_html(b2, "người mượn")

    empty = borrow_behavior(records, "borrower_id", "SV9", TODAY)
    assert empty["total"] == 0 and empty["on_time_rate"] is None and not empty["late_flag"]
