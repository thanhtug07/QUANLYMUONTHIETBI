# -*- coding: utf-8 -*-
"""
main.py — PIPELINE DÙNG CHUNG (CLI + app.py gọi lại)
====================================================
Luồng xử lý bắt buộc cho MỌI nguồn dữ liệu (file mặc định hoặc upload):

    CSV -> cleaners (làm sạch + thu lỗi) -> validators (Set, quá hạn,
    thất thoát) -> statistics (thống kê, lọc, sort) -> reports (báo cáo).

Không chứa UI; trả về dict kết quả để cả `main()` (CLI) và `app.py` sử dụng.
"""
from __future__ import annotations

import sys as _sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import cleaners
import reports
import statistics
import validators

# Console Windows mặc định có thể dùng cp1252 -> in tiếng Việt sẽ lỗi
# UnicodeEncodeError. Chuyển stdout/stderr sang UTF-8 cho CLI chạy được trên
# mọi máy (không ảnh hưởng pipeline hay dashboard).
for _stream in (_sys.stdout, _sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# ----------------------------------------------------------------------
# Đường dẫn mặc định
# ----------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
REPORT_TXT = OUTPUT_DIR / "report.txt"

DEVICES_CSV = DATA_DIR / "devices.csv"
BORROWERS_CSV = DATA_DIR / "borrowers.csv"
RECORDS_CSV = DATA_DIR / "borrow_records.csv"

# Thông báo lỗi thân thiện (app.py hiển thị trực tiếp các chuỗi này).
MSG_NO_DATA = "Không có dữ liệu để phân tích."
MSG_NO_VALID = "Không có bản ghi hợp lệ."


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _has_data(rows: List[Dict[str, Any]]) -> bool:
    """Kiểm tra danh sách dict đọc từ CSV có dòng dữ liệu thực sự hay không."""
    return bool(rows)


def _valid_devices(devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Chỉ giữ thiết bị có device_id (điều kiện tối thiểu để dùng được)."""
    return [d for d in devices if d.get("device_id")]


def _valid_borrowers(borrowers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Chỉ giữ người mượn có borrower_id."""
    return [b for b in borrowers if b.get("borrower_id")]


def _valid_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Chỉ giữ phiếu mượn có đủ 3 khoá ngoại bắt buộc
    (borrow_id + device_id + borrower_id) — phần còn lại đã được
    validators báo chi tiết bằng error records.
    """
    return [
        r for r in records
        if r.get("borrow_id") and r.get("device_id") and r.get("borrower_id")
    ]


# ----------------------------------------------------------------------
# Pipeline chính
# ----------------------------------------------------------------------

def run_pipeline(
    devices_csv: Optional[Path] = None,
    borrowers_csv: Optional[Path] = None,
    records_csv: Optional[Path] = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Chạy toàn bộ pipeline và trả về dict kết quả:

        error       : Optional[str] — thông báo thân thiện nếu dừng sớm
        devices     : List[Dict] thiết bị hợp lệ
        borrowers   : List[Dict] người mượn hợp lệ
        records     : List[Dict] phiếu mượn hợp lệ
        errors      : List[Dict] lỗi làm sạch + validation ({row, field, value, error})
        warnings    : List[str]  cảnh báo nghiệp vụ
        stats       : Dict       kết quả statistics.compute_all
        report_text : str        nội dung báo cáo (rỗng nếu dừng sớm)
        counts      : Dict       số liệu tổng hợp cho UI (hợp lệ / lỗi)
    """
    today = today or date.today()
    devices_csv = devices_csv or DEVICES_CSV
    borrowers_csv = borrowers_csv or BORROWERS_CSV
    records_csv = records_csv or RECORDS_CSV

    result: Dict[str, Any] = {
        "error": None, "devices": [], "borrowers": [], "records": [],
        "errors": [], "warnings": [], "stats": {}, "report_text": "",
        "counts": {},
    }

    # 1) Kiểm tra cấu trúc file (schema) trước khi đọc
    schema_checks = (
        ("devices.csv", devices_csv, cleaners.DEVICE_COLUMNS),
        ("borrowers.csv", borrowers_csv, cleaners.BORROWER_COLUMNS),
        ("borrow_records.csv", records_csv, cleaners.RECORD_COLUMNS),
    )
    for name, path, columns in schema_checks:
        missing = cleaners.missing_columns(str(path), columns)
        if missing:
            result["error"] = (
                f"File '{name}' không đúng cấu trúc. Thiếu các cột: {', '.join(missing)}."
            )
            return result

    # 2) Đọc + làm sạch (cleaners trả về (rows, errors))
    raw_devices = cleaners.load_csv(str(devices_csv), cleaners.DEVICE_COLUMNS)
    raw_borrowers = cleaners.load_csv(str(borrowers_csv), cleaners.BORROWER_COLUMNS)
    raw_records = cleaners.load_csv(str(records_csv), cleaners.RECORD_COLUMNS)

    devices, dev_errors = cleaners.clean_devices(raw_devices)
    borrowers, bor_errors = cleaners.clean_borrowers(raw_borrowers)
    records, rec_errors = cleaners.clean_borrow_records(raw_records)

    all_errors: List[Dict[str, Any]] = list(dev_errors) + list(bor_errors) + list(rec_errors)

    # 3) Trạng thái dừng sớm: rỗng hoặc không còn bản ghi hợp lệ
    if not (devices or borrowers or records):
        result["error"] = MSG_NO_DATA
        result["counts"] = {"valid": 0, "invalid": len(all_errors)}
        return result

    valid_d = _valid_devices(devices)
    valid_b = _valid_borrowers(borrowers)
    valid_r = _valid_records(records)
    if not valid_r:
        result["error"] = MSG_NO_VALID
        result["counts"] = {"valid": 0, "invalid": len(all_errors)}
        return result

    # 4) Validation bằng SET (tham chiếu, trùng, quá hạn, thất thoát...)
    validation_errors, overdue_records, lost_devices = validators.validate_all(
        valid_d, valid_b, valid_r, today
    )
    all_errors = all_errors + list(validation_errors)

    # 5) Thống kê (Dictionary lookup/join, Top-N, tỷ lệ...)
    stats = statistics.compute_all(
        valid_d, valid_b, valid_r,
        overdue_records=overdue_records, lost_devices=lost_devices, today=today,
    )

    # 6) Báo cáo (chỉ format từ stats — không tính lại số liệu)
    # Cảnh báo = thông điệp tóm tắt từ kết quả của validators (đã có logic Set).
    warnings = [str(e.get("error", "")) for e in validation_errors if e.get("error")]
    if overdue_records:
        warnings.append(
            f"[QUÁ HẠN] {len(overdue_records)} phiếu quá hạn chưa trả: "
            f"{sorted({r.get('borrow_id', '') for r in overdue_records if r.get('borrow_id')})}"
        )
    if lost_devices:
        warnings.append(
            f"[THẤT THOÁT] {len(lost_devices)} thiết bị nghi thất thoát: {sorted(lost_devices)}"
        )
    report_text = reports.build_report_text(stats, all_errors, validation_errors)

    result.update({
        "devices": valid_d,
        "borrowers": valid_b,
        "records": valid_r,
        "errors": all_errors,
        "warnings": warnings,
        "stats": stats,
        "report_text": report_text,
        "counts": {"valid": len(valid_r), "invalid": len(all_errors)},
    })
    return result


def write_report(result: Dict[str, Any]) -> Optional[Path]:
    """Ghi báo cáo ra output/report.txt; trả về đường dẫn nếu thành công."""
    if not result.get("report_text"):
        return None
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_TXT.write_text(result["report_text"], encoding="utf-8")
    return REPORT_TXT


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def _print_summary(result: Dict[str, Any]) -> None:
    """In tóm tắt kết quả pipeline ra console (CLI)."""
    print("=" * 60)
    print("QUẢN LÝ MƯỢN THIẾT BỊ — KẾT QUẢ PIPELINE")
    print("=" * 60)
    if result["error"]:
        print(f"LỖI: {result['error']}")
        return
    print(f"  Thiết bị hợp lệ   : {len(result['devices'])}")
    print(f"  Người mượn hợp lệ : {len(result['borrowers'])}")
    print(f"  Phiếu hợp lệ      : {len(result['records'])}")
    print(f"  Bản ghi lỗi       : {result['counts'].get('invalid', 0)}")
    print("-" * 60)
    stats = result["stats"]
    print(f"  Tổng lượt mượn    : {stats.get('total_borrows')}")
    print(f"  Đang mượn         : {stats.get('currently_borrowed')}")
    print(f"  Đã trả            : {stats.get('returned_count')}")
    print(f"  Quá hạn           : {stats.get('overdue_count')}")
    print(f"  Thất thoát        : {stats.get('lost_count')}")
    print(f"  Tỷ lệ đúng hạn    : {stats.get('on_time_rate')}%")
    print("-" * 60)
    for warning in result["warnings"][:10]:
        print(f"  {warning}")
    extra = len(result["warnings"]) - 10
    if extra > 0:
        print(f"  ... và {extra} cảnh báo khác")


def main() -> int:
    """Điểm vào CLI: chạy pipeline, ghi báo cáo, in tóm tắt."""
    result = run_pipeline()
    _print_summary(result)
    path = write_report(result)
    if path:
        print("-" * 60)
        print(f"Báo cáo đã ghi tại: {path}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())