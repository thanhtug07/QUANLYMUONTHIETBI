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
