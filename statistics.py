"""
statistics.py — PHÂN TÍCH & THỐNG KÊ
===============================================================
Nhận dữ liệu sạch từ cleaners + kết quả kiểm tra từ validators,
trả ra toàn bộ số liệu cho BÁO CÁO (reports.py) và DASHBOARD (app.py).

CẤU TRÚC DỮ LIỆU VÀ LÝ DO SỬ DỤNG (vấn đáp):
  - DICTIONARY devices_by_id / borrowers_by_id:
      tra cứu O(1) theo mã -> JOIN tên/loại thiết bị, tên/lớp người mượn
      vào từng phiếu (join_records) mà không cần duyệt lồng List.
  - LIST: danh sách phiếu, danh sách kết quả lọc/tìm kiếm (giữ thứ tự).
  - TUPLE: kết quả Top N dạng (mã, số_lượt) — cấu trúc cố định 2 phần tử.
  - SET: đếm thiết bị ĐANG được mưuợn (mã duy nhất), tính TỶ LỆ SỬ DỤNG
    (giao với danh mục), loại trùng khi quét Counter.

LƯU Ý: module trùng tên với thư viện chuẩn `statistics` nên TUYỆT ĐỐI
không import thư viện đó ở đây (tránh shadowing).
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import validators
from cleaners import parse_date

#: Trạng thái phiếu = đang mượn (chưa trả).
ACTIVE_RECORD_STATUSES: frozenset = frozenset({"borrowing", "overdue"})

#: Trạng thái phiếu = đã trả xong.
RETURNED_RECORD_STATUSES: frozenset = frozenset({"returned"})

#: Nhãn khi join không tìm thấy thiết bị/người mượn (dữ liệu tham chiếu lỗi).
UNKNOWN_LABEL = "(không rõ)"


# ----------------------------------------------------------------------
# DICTIONARY — TRA CỨU / JOIN (PHẦN 1 của yêu cầu)
# ----------------------------------------------------------------------

def build_devices_by_id(devices: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Dựng Dictionary tra cứu thiết bị: {device_id: {device_name, category, status}}.

    Dict cho phép JOIN phiếu -> thiết bị với chi phí O(1) mỗi phiếu
    thay vì quét toàn bộ List thiết bị (O(n)) cho từng phiếu.
    """
    return {
        str(d.get("device_id", "")).strip(): {
            "device_name": d.get("device_name", ""),
            "category": d.get("category", ""),
            "status": d.get("status", ""),
        }
        for d in devices if str(d.get("device_id", "")).strip()
    }


def build_borrowers_by_id(borrowers: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Dựng Dictionary tra cứu người mượn: {borrower_id: {name, class_name}}."""
    return {
        str(b.get("borrower_id", "")).strip(): {
            "name": b.get("name", ""),
            "class_name": b.get("class_name", ""),
            "phone": b.get("phone", ""),
        }
        for b in borrowers if str(b.get("borrower_id", "")).strip()
    }


def join_records(
    records: List[Dict[str, Any]],
    devices_by_id: Dict[str, Dict[str, Any]],
    borrowers_by_id: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    JOIN mỗi phiếu mượn với tên thiết bị / loại / người mượn qua 2 Dictionary.

    Đây là dữ liệu dùng cho: bảng Phiếu mượn, tìm kiếm theo tên,
    thống kê theo loại thiết bị và báo cáo.
    """
    joined: List[Dict[str, Any]] = []
    for record in records:
        device = devices_by_id.get(record.get("device_id", ""), {})
        borrower = borrowers_by_id.get(record.get("borrower_id", ""), {})
        row = dict(record)  # giữ nguyên dữ liệu gốc của phiếu
        row["device_name"] = device.get("device_name", UNKNOWN_LABEL)
        row["category"] = device.get("category", UNKNOWN_LABEL)
        row["name"] = borrower.get("name", UNKNOWN_LABEL)
        row["class_name"] = borrower.get("class_name", "")
        joined.append(row)
    return joined

# ----------------------------------------------------------------------
# CÁC HÀM THỐNG KÊ CƠ BẢN (mỗi hàm 1 số liệu — nhỏ, dễ test)
# ----------------------------------------------------------------------

def count_total_borrows(records: List[Dict[str, Any]]) -> int:
    """(1) Tổng số lượt mượn = số dòng phiếu mượn."""
    return len(records)


def count_total_devices(devices: List[Dict[str, Any]]) -> int:
    """(2) Tổng số thiết bị trong danh mục."""
    return len(devices)


def count_total_borrowers(borrowers: List[Dict[str, Any]]) -> int:
    """Tổng số người mượn trong danh mục."""
    return len(borrowers)


def count_currently_borrowed(records: List[Dict[str, Any]]) -> int:
    """
    (3) Số THIẾT BỊ đang được mượn (chưa quay lại kho).

    [SET] Dùng set để đếm MÃ DUY NHẤT: một thiết bị có thể xuất hiện trong
    nhiều phiếu (mượn - trả - mượn lại) nhưng chỉ được đếm 1 lần.
    """
    busy = {
        str(r.get("device_id", "")).strip()
        for r in records
        if str(r.get("status", "")) in ACTIVE_RECORD_STATUSES
    }
    busy.discard("")
    return len(busy)


def count_returned(records: List[Dict[str, Any]]) -> int:
    """(4) Số lượt ĐÃ TRẢ."""
    return sum(1 for r in records if str(r.get("status", "")) == "returned")


def count_lost(lost_ids: List[str]) -> int:
    """(5) Số thiết bị THẤT THOÁT (danh sách do validators hợp 3 nguồn)."""
    return len(lost_ids)


def on_time_return_rate(records: List[Dict[str, Any]]) -> float:
    """
    (6) Tỷ lệ trả ĐÚNG HẠN (%) — tính trên các phiếu đã trả:
        return_date <= due_date. Không có phiếu đã trả -> 0.0.
    """
    returned = [r for r in records if str(r.get("status", "")) == "returned"]
    if not returned:
        return 0.0
    on_time = 0
    for row in returned:
        ret = parse_date(row.get("return_date"))
        due = parse_date(row.get("due_date"))
        if ret and due and ret <= due:
            on_time += 1
    return round(100.0 * on_time / len(returned), 1)


def overdue_summary(overdue_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    (7) Tóm tắt quá hạn: số lượt + ngày quá hạn LỚN NHẤT / TRUNG BÌNH.

    Số ngày lấy từ kết quả validators.find_overdue_records — KHÔNG tự
    tính lại (tránh duplicate logic giữa 2 module).
    """
    days = [int(r.get("days_overdue", 0)) for r in overdue_records]
    return {
        "count": len(days),
        "max_days": max(days) if days else 0,
        "avg_days": round(sum(days) / len(days), 1) if days else 0.0,
    }


def device_utilization_rate(
    records: List[Dict[str, Any]],
    devices: List[Dict[str, Any]],
) -> float:
    """
    (8) Tỷ lệ sử dụng thiết bị (%): số thiết bị TỪNG được mượn / tổng thiết bị.

    [SET] INTERSECTION: thiết bị xuất hiện trong phiếu ∩ thiết bị trong danh
    mục -> chỉ đếm thiết bị hợp lệ (mã tham chiếu lỗi đã bị validators báo).
    """
    used_ids = {str(r.get("device_id", "")).strip() for r in records} - {""}
    catalog_ids = {str(d.get("device_id", "")).strip() for d in devices} - {""}
    if not catalog_ids:
        return 0.0
    return round(100.0 * len(used_ids & catalog_ids) / len(catalog_ids), 1)


def borrows_by_category(
    records: List[Dict[str, Any]],
    devices_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Tuple[str, int]]:
    """
    (9) Số lượt mượn theo LOẠI thiết bị.

    [DICTIONARY] JOIN phiếu -> thiết bị qua devices_by_id để lấy 'category'
    (O(1) mỗi phiếu). Trả về List[Tuple[category, số_lượt]] sắp giảm dần.
    """
    devices_by_id = devices_by_id or {}
    counter: Counter = Counter()
    for row in records:
        category = str(row.get("category", "")).strip()
        if not category:
            device = devices_by_id.get(str(row.get("device_id", "")).strip(), {})
            category = str(device.get("category", "")).strip()
        if category:
            counter[category] += 1
    return sorted(counter.items(), key=lambda item: item[1], reverse=True)


def borrows_by_month(records: List[Dict[str, Any]]) -> List[Tuple[str, int]]:
    """
    (13) Số lượt mượn theo THÁNG, tăng dần theo thời gian.

    Khoá là 'YYYY-MM' suy ra từ borrow_date (thiếu thì dùng due_date) — chỉ
    gồm tháng thực sự có dữ liệu, KHÔNG nội suy/dựng chuỗi thời gian giả.
    """
    counter: Counter = Counter()
    for row in records:
        parsed = parse_date(row.get("borrow_date")) or parse_date(row.get("due_date"))
        if parsed is not None:
            counter[f"{parsed.year:04d}-{parsed.month:02d}"] += 1
    return sorted(counter.items(), key=lambda item: item[0])


#: Thứ tự các ngày trong tuần cho biểu đồ (Thứ 2 -> Chủ nhật).
WEEKDAY_LABELS: Tuple[str, ...] = (
    "Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật",
)


def borrows_by_weekday(records: List[Dict[str, Any]]) -> List[Tuple[str, int]]:
    """
    Số lượt mượn theo NGÀY TRONG TUẦN (Thứ 2 -> Chủ nhật), đủ 7 nhãn kể cả
    ngày 0 lượt để biểu đồ cột luôn có trục ổn định.

    Mốc ngày giống `borrows_by_month` (borrow_date, thiếu thì due_date);
    phiếu không parse được ngày nào thì bỏ qua — không bịa số liệu.
    """
    counter: Counter = Counter()
    for row in records:
        parsed = parse_date(row.get("borrow_date")) or parse_date(row.get("due_date"))
        if parsed is not None:
            counter[parsed.weekday()] += 1
    return [(WEEKDAY_LABELS[day], counter.get(day, 0)) for day in range(7)]


def format_delta(current: float, previous: float) -> Optional[str]:
    """
    Chuỗi pill delta kỳ ("+12,5%" / "-8,0%") cho KPI Dashboard.

    Trả về None khi kỳ trước bằng 0 (không có cơ sở so sánh) — caller ẨN pill
    thay vì bịa số. Dấu trừ dùng U+2212 cho đẹp typography.
    """
    if previous == 0:
        return None
    pct = 100.0 * (current - previous) / abs(previous)
    text = f"{abs(pct):.1f}%".replace(".", ",")
    if abs(pct) < 0.05:
        return "0,0%"
    sign = "+" if pct > 0 else "−"
    return f"{sign}{text}"


# ----------------------------------------------------------------------
# TOP N — [SORTED + LAMBDA, reverse=True]
# ----------------------------------------------------------------------

def top_devices_by_borrows(
    records: List[Dict[str, Any]], top_n: int = 5
) -> List[Tuple[str, int]]:
    """
    (10) Top N thiết bị được mượn nhiều nhất -> List[Tuple[device_id, lượt]].

    [SORTED + LAMBDA] `key=lambda item: item[1], reverse=True` phục vụ nghiệp
    vụ XẾP HẠNG: thiết bị được mượn nhiều nhất đứng đầu để đề xuất mua thêm /
    bảo trì định kỳ. Counter đếm, sorted sắp — tách bạch 2 việc.
    """
    counter: Counter = Counter(
        str(r.get("device_id", "")).strip() for r in records
        if str(r.get("device_id", "")).strip()
    )
    return sorted(counter.items(), key=lambda item: item[1], reverse=True)[:top_n]


def top_borrowers_by_borrows(
    records: List[Dict[str, Any]], top_n: int = 5
) -> List[Tuple[str, int]]:
    """
    (11) Top N người mượn nhiều nhất -> List[Tuple[borrower_id, lượt]].

    [SORTED + LAMBDA] tương tự top_devices_by_borrows — phục vụ nghiệp vụ
    nhận diện người mượn tích cực / cần theo dõi.
    """
    counter: Counter = Counter(
        str(r.get("borrower_id", "")).strip() for r in records
        if str(r.get("borrower_id", "")).strip()
    )
    return sorted(counter.items(), key=lambda item: item[1], reverse=True)[:top_n]


def overdue_days_list(
    records: List[Dict[str, Any]], today: Optional[date] = None
) -> List[Dict[str, Any]]:
    """
    (12) Danh sách phiếu quá hạn sắp theo SỐ NGÀY GIẢM DẦN.

    [SORTED + LAMBDA] `key=lambda r: r["days_overdue"], reverse=True`
    phục vụ nghiệp vụ ƯU TIÊN XỬ LÝ: phiếu quá hạn lâu nhất cần nhắc trả trước.
    Tái sử dụng validators.find_overdue_records (không duplicate logic).
    """
    rows = validators.find_overdue_records(records, today)
    return sorted(rows, key=lambda r: int(r.get("days_overdue", 0)), reverse=True)

# ----------------------------------------------------------------------
# BỘ LỌC / TÌM KIẾM (dashboard gọi lại — không copy logic vào app.py)
# ----------------------------------------------------------------------

def filter_by_status(records: List[Dict[str, Any]], status: str) -> List[Dict[str, Any]]:
    """Lọc phiếu theo TRẠNG THÁI (borrowing/returned/overdue/lost)."""
    return [r for r in records if str(r.get("status", "")) == status]


def filter_by_device(records: List[Dict[str, Any]], device_id: str) -> List[Dict[str, Any]]:
    """Lọc phiếu theo MÃ THIẾT BỊ (xem lịch sử mượn của 1 thiết bị)."""
    return [r for r in records if str(r.get("device_id", "")) == device_id]


def filter_by_borrower(records: List[Dict[str, Any]], borrower_id: str) -> List[Dict[str, Any]]:
    """Lọc phiếu theo MÃ NGƯỜI MƯỢN (xem lịch sử mượn của 1 người)."""
    return [r for r in records if str(r.get("borrower_id", "")) == borrower_id]


def filter_by_category(
    records: List[Dict[str, Any]],
    category: str,
    devices_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Lọc phiếu theo LOẠI thiết bị (ví dụ chỉ xem 'Laptop').

    [DICTIONARY] Nếu phiếu chưa được join, tra devices_by_id (O(1)/phiếu)
    để lấy category — tái sử dụng kết quả JOIN thay vì quét List thiết bị.
    """
    devices_by_id = devices_by_id or {}
    out: List[Dict[str, Any]] = []
    for row in records:
        row_category = str(row.get("category", "")).strip()
        if not row_category:
            device = devices_by_id.get(str(row.get("device_id", "")).strip(), {})
            row_category = str(device.get("category", "")).strip()
        if row_category == category:
            out.append(row)
    return out


def filter_overdue(
    records: List[Dict[str, Any]], today: Optional[date] = None
) -> List[Dict[str, Any]]:
    """
    Lọc phiếu QUÁ HẠN — tái sử dụng validators.find_overdue_records
    (không duplicate logic). Kết quả kèm days_overdue để hiển thị/sắp xếp.
    """
    return validators.find_overdue_records(records, today)


def search_records(
    records: List[Dict[str, Any]],
    keyword: str,
    devices_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
    borrowers_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    TÌM KIẾM không phân biệt hoa/thường trên các trường người dùng nhìn thấy:
    mã phiếu, mã/tên/loại thiết bị, mã/tên/lớp người mượn, trạng thái.

    Keyword rỗng -> trả về toàn bộ. Dùng devices_by_id / borrowers_by_id
    (Dictionary) để tìm theo TÊN mà không cần quét danh mục cho từng phiếu.
    """
    needle = str(keyword).strip().lower()
    if not needle:
        return list(records)
    devices_by_id = devices_by_id or {}
    borrowers_by_id = borrowers_by_id or {}
    fields = ("borrow_id", "device_id", "borrower_id", "status",
              "device_name", "category", "name", "class_name")
    out: List[Dict[str, Any]] = []
    for row in records:
        device = devices_by_id.get(str(row.get("device_id", "")).strip(), {})
        borrower = borrowers_by_id.get(str(row.get("borrower_id", "")).strip(), {})
        haystack = " ".join(
            str(row.get(field, "")) for field in fields
        ) + " " + str(device.get("device_name", "")) + " " + str(borrower.get("name", ""))
        if needle in haystack.lower():
            out.append(row)
    return out


# ----------------------------------------------------------------------
# compute_all — GỌI MỘT LẦN, LẤY TOÀN BỘ SỐ LIỆU (reports + dashboard dùng)
# ----------------------------------------------------------------------

def compute_all(
    devices: List[Dict[str, Any]],
    borrowers: List[Dict[str, Any]],
    records: List[Dict[str, Any]],
    overdue_records: Optional[List[Dict[str, Any]]] = None,
    lost_devices: Optional[List[str]] = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Tổng hợp mọi thống kê vào MỘT Dictionary duy nhất cho reports.py / app.py.

    Nếu validators đã tính overdue/lost thì truyền vào để TÁI SỬ DỤNG kết quả
    (không tính lại); ngược lại hàm tự gọi validators. Toàn bộ số liệu đều
    suy ra từ dữ liệu đầu vào — KHÔNG có giá trị hard-code.
    """
    today = today or date.today()
    if overdue_records is None:
        overdue_records = validators.find_overdue_records(records, today)
    if lost_devices is None:
        lost_devices = validators.find_lost_devices(records, today)

    devices_by_id = build_devices_by_id(devices)
    borrowers_by_id = build_borrowers_by_id(borrowers)
    joined = join_records(records, devices_by_id, borrowers_by_id)
    summary = overdue_summary(overdue_records)

    return {
        # Dictionary tra cứu / JOIN (PHẦN 1 của yêu cầu)
        "devices_by_id": devices_by_id,
        "borrowers_by_id": borrowers_by_id,
        "joined_records": joined,
        # Các số liệu cơ bản
        "total_borrows": count_total_borrows(records),
        "total_devices": count_total_devices(devices),
        "total_borrowers": count_total_borrowers(borrowers),
        "currently_borrowed": count_currently_borrowed(records),
        "returned_count": count_returned(records),
        "overdue_count": summary["count"],
        "overdue_max_days": summary["max_days"],
        "overdue_avg_days": summary["avg_days"],
        "lost_count": count_lost(lost_devices),
        "lost_ids": list(lost_devices),
        # Tỷ lệ
        "on_time_rate": on_time_return_rate(records),
        "utilization_rate": device_utilization_rate(records, devices),
        # Xếp hạng / nhóm
        "borrows_by_category": borrows_by_category(records, devices_by_id),
        "borrows_by_month": borrows_by_month(records),
        "borrows_by_weekday": borrows_by_weekday(records),
        "top_devices": top_devices_by_borrows(records),
        "top_borrowers": top_borrowers_by_borrows(records),
        "overdue_days": overdue_days_list(records, today),
    }