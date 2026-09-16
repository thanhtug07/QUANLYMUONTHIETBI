
from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

REPORT_WIDTH: int = 60
MAX_OVERDUE_ROWS: int = 12
MAX_ERROR_EXAMPLES: int = 10

LEVEL_DATA = "DATA ERROR"
LEVEL_USER = "USER ERROR"
LEVEL_SYSTEM = "SYSTEM ERROR"


def _line(char: str = "=") -> str:
    """Đường kẻ ngang cố định độ dài của báo cáo."""
    return char * REPORT_WIDTH


def _kv(label: str, value: Any) -> str:
    """Dòng 'nhãn : giá trị' căn đều cho dễ đọc."""
    return f"  {label:<28}: {value}"


def _pct(value: float) -> str:
    """Định dạng phần trăm an toàn với giá trị None."""
    return f"{float(value):.1f}%" if value is not None else "n/a"


def _section(title: str) -> List[str]:
    """Tiêu đề một phần trong báo cáo."""
    return ["", f"{_line('-')}", f"{title}", f"{_line('-')}"]


def _device_name(stats: Dict[str, Any], device_id: str) -> str:
    """Tra tên thiết bị qua Dictionary devices_by_id (JOIN, không hard-code)."""
    device = stats.get("devices_by_id", {}).get(device_id, {})
    name = device.get("device_name", "")
    return f"{device_id} ({name})" if name else device_id


def _borrower_name(stats: Dict[str, Any], borrower_id: str) -> str:
    """Tra tên người mượn qua Dictionary borrowers_by_id."""
    borrower = stats.get("borrowers_by_id", {}).get(borrower_id, {})
    name = borrower.get("name", "")
    return f"{borrower_id} ({name})" if name else borrower_id


def _overview_section(stats: Dict[str, Any]) -> List[str]:
    """Phần 1 — Tổng quan: các con số KPI chính."""
    lines = _section("1. TỔNG QUAN")
    lines += [
        _kv("Tổng lượt mượn", stats.get("total_borrows", 0)),
        _kv("Tổng thiết bị", stats.get("total_devices", 0)),
        _kv("Tổng người mượn", stats.get("total_borrowers", 0)),
        _kv("Đang mượn", stats.get("currently_borrowed", 0)),
        _kv("Đã trả", stats.get("returned_count", 0)),
        _kv("Quá hạn", stats.get("overdue_count", 0)),
        _kv("Thất thoát", stats.get("lost_count", 0)),
    ]
    return lines


def _devices_section(stats: Dict[str, Any]) -> List[str]:
    """Phần 2 — Thiết bị: phân bố theo loại / trạng thái + tỷ lệ sử dụng."""
    lines = _section("2. THIẾT BỊ")
    devices = list(stats.get("devices_by_id", {}).values())

    by_category = Counter(str(d.get("category", "khác")) for d in devices)
    by_status = Counter(str(d.get("status", "khác")) for d in devices)

    lines.append(_kv("Tổng số thiết bị", len(devices)))
    lines.append("  - Theo loại thiết bị:")
    for category, count in sorted(by_category.items()):
        lines.append(f"      {category:<24}: {count}")
    lines.append("  - Theo trạng thái danh mục:")
    for status, count in sorted(by_status.items()):
        lines.append(f"      {status:<24}: {count}")
    lines.append(_kv("Tỷ lệ sử dụng thiết bị", _pct(stats.get("utilization_rate"))))
    return lines


def _borrowers_section(stats: Dict[str, Any]) -> List[str]:
    """Phần 3 — Người mượn: tổng số + top người mượn."""
    lines = _section("3. NGƯỜI MƯỢN")
    lines.append(_kv("Tổng số người mượn", stats.get("total_borrowers", 0)))
    for borrower_id, count in stats.get("top_borrowers", []):
        lines.append(f"      {_borrower_name(stats, borrower_id):<40}: {count} lượt")
    return lines


def _borrow_flow_section(stats: Dict[str, Any]) -> List[str]:
    """Phần 4 — Mượn/trả: dòng chảy mượn-trả + tỷ lệ trả đúng hạn."""
    lines = _section("4. MƯỢN/TRẢ")
    lines += [
        _kv("Tổng lượt mượn", stats.get("total_borrows", 0)),
        _kv("Đang mượn (borrowing)", stats.get("currently_borrowed", 0)),
        _kv("Đã trả (returned)", stats.get("returned_count", 0)),
        _kv("Tỷ lệ trả đúng hạn", _pct(stats.get("on_time_rate"))),
    ]
    return lines


def _overdue_section(stats: Dict[str, Any]) -> List[str]:
    """Phần 5 — Quá hạn: tổng hợp + danh sách phiếu (số ngày giảm dần)."""
    lines = _section("5. QUÁ HẠN")
    lines += [
        _kv("Số lượt quá hạn", stats.get("overdue_count", 0)),
        _kv("Số ngày quá hạn lớn nhất", stats.get("overdue_max_days", 0)),
        _kv("Số ngày quá hạn trung bình", stats.get("overdue_avg_days", 0.0)),
    ]
    rows = stats.get("overdue_days", [])[:MAX_OVERDUE_ROWS]
    if rows:
        lines.append(f"  Danh sách (tối đa {MAX_OVERDUE_ROWS} phiếu, số ngày giảm dần):")
        for row in rows:
            lines.append(
                f"      {row.get('borrow_id', '')} | "
                f"{_device_name(stats, row.get('device_id', ''))} | "
                f"{_borrower_name(stats, row.get('borrower_id', ''))} | "
                f"hạn {row.get('due_date', '')} | "
                f"quá hạn {row.get('days_overdue', 0)} ngày"
            )
    else:
        lines.append("  Không có phiếu quá hạn.")
    return lines


def _lost_section(stats: Dict[str, Any]) -> List[str]:
    """Phần 6 — Thất thoát: danh sách thiết bị mất (ngưỡng validators)."""
    lines = _section("6. THẤT THOÁT")
    lost_ids: List[str] = stats.get("lost_ids", [])
    lines.append(_kv("Số thiết bị thất thoát", len(lost_ids)))
    if lost_ids:
        for device_id in lost_ids:
            lines.append(f"      {_device_name(stats, device_id)}")
    else:
        lines.append("  Không có thiết bị thất thoát.")
    return lines


def _top_section(stats: Dict[str, Any]) -> List[str]:
    """Phần 7 — Top thiết bị + lượt mượn theo loại."""
    lines = _section("7. TOP THIẾT BỊ")
    top = stats.get("top_devices", [])
    if top:
        for device_id, count in top:
            lines.append(f"      {_device_name(stats, device_id):<40}: {count} lượt")
    else:
        lines.append("  Không có dữ liệu.")
    lines.append("  Lượt mượn theo loại thiết bị:")
    for category, count in stats.get("borrows_by_category", []):
        lines.append(f"      {category:<24}: {count} lượt")
    return lines


def _warnings_section(
    clean_errors: List[Dict[str, Any]],
    validation_errors: List[Dict[str, Any]],
) -> List[str]:
    """Phần 8 — Cảnh báo dữ liệu: lỗi làm sạch + lỗi kiểm tra (mẫu)."""
    lines = _section("8. CẢNH BÁO DỮ LIỆU")
    lines.append(_kv("Lỗi khi làm sạch (cleaning)", len(clean_errors)))
    lines.append(_kv("Lỗi khi kiểm tra (validation)", len(validation_errors)))
    examples = (clean_errors + validation_errors)[:MAX_ERROR_EXAMPLES]
    if examples:
        lines.append(f"  Ví dụ (tối đa {MAX_ERROR_EXAMPLES} lỗi đầu tiên):")
        for err in examples:
            value = str(err.get("value", ""))
            value = f"{value[:24]}..." if len(value) > 27 else value
            lines.append(
                f"      [{err.get('table', '')}] dòng {err.get('row', '?')} "
                f"trường '{err.get('field', '?')}' = {value!r} -> {err.get('error', '')}"
            )
        total = len(clean_errors) + len(validation_errors)
        if total > len(examples):
            lines.append(f"      ... và {total - len(examples)} lỗi khác")
    else:
        lines.append("  Dữ liệu hợp lệ — không có cảnh báo.")
    return lines


def build_report_text(
    stats: Dict[str, Any],
    clean_errors: Optional[List[Dict[str, Any]]] = None,
    validation_errors: Optional[List[Dict[str, Any]]] = None,
    generated_at: Optional[datetime] = None,
) -> str:
    """
    Dựng NỘI DUNG báo cáo text 8 phần từ kết quả tầng phân tích.

    Tham số:
        stats: Dictionary trả về từ statistics.compute_all().
        clean_errors: lỗi từ cleaners (dạng cleaners.make_error).
        validation_errors: lỗi từ validators.validate_all().
        generated_at: mốc thời gian tạo báo cáo (mặc định là bây giờ).

    Trả về:
        Chuỗi báo cáo hoàn chỉnh (đã kết thúc bằng '\\n').
    """
    clean_errors = clean_errors or []
    validation_errors = validation_errors or []
    generated_at = generated_at or datetime.now()

    sections: List[str] = [
        _line(),
        "BÁO CÁO QUẢN LÝ MƯỢN THIẾT BỊ",
        _line(),
        f"Thời điểm tạo: {generated_at:%Y-%m-%d %H:%M:%S}",
        _overview_section(stats),
        _devices_section(stats),
        _borrowers_section(stats),
        _borrow_flow_section(stats),
        _overdue_section(stats),
        _lost_section(stats),
        _top_section(stats),
        _warnings_section(clean_errors, validation_errors),
        "",
    ]
    # Các section builder trả về List[str] -> trải phẳng trước khi join.
    lines: List[str] = []
    for section in sections:
        if isinstance(section, list):
            lines.extend(section)
        else:
            lines.append(section)
    return "\n".join(lines)


def write_report(path: str | Path, text: str) -> None:
    """Ghi nội dung báo cáo ra file (UTF-8), tự tạo thư mục nếu thiếu."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")