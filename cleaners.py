

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

#: Các định dạng ngày được chấp nhận khi đọc CSV (ưu tiên từ trên xuống).
DATE_FORMATS: Tuple[str, ...] = (
    "%d/%m/%Y",   # 25/12/2024  (định dạng phổ biến ở Việt Nam)
    "%Y-%m-%d",   # 2024-12-25  (ISO)
    "%d-%m-%Y",   # 25-12-2024
)

#: Cột chuẩn của từng file CSV (đúng theo data model của đề bài).
DEVICE_COLUMNS: List[str] = ["device_id", "device_name", "category", "status"]
BORROWER_COLUMNS: List[str] = ["borrower_id", "name", "class_name"]
RECORD_COLUMNS: List[str] = [
    "borrow_id",
    "borrower_id",
    "device_id",
    "borrow_date",
    "due_date",
    "return_date",   # rỗng nếu chưa trả
    "status",        # borrowing | returned | overdue | lost
]

#: Bộ giá trị trạng thái HỢP LỆ (dùng Set để kiểm tra O(1)).
DEVICE_STATUSES: frozenset[str] = frozenset({"available", "borrowed", "lost", "maintenance"})
RECORD_STATUSES: frozenset[str] = frozenset({"borrowing", "returned", "overdue", "lost"})

#: Từ đồng nghĩa -> giá trị chuẩn. Dùng DICT để MAPPING dữ liệu bẩn về chuẩn.
DEVICE_STATUS_ALIASES: Dict[str, str] = {
    "san_sang": "available", "san sang": "available", "ready": "available", "ok": "available",
    "dang_muon": "borrowed", "dang muon": "borrowed", "borrowing": "borrowed",
    "mat": "lost", "that_thoat": "lost", "that thoat": "lost",
    "bao_tri": "maintenance", "bao tri": "maintenance", "repair": "maintenance",
}
RECORD_STATUS_ALIASES: Dict[str, str] = {
    "dang_muon": "borrowing", "dang muon": "borrowing", "borrowed": "borrowing",
    "da_tra": "returned", "da tra": "returned", "return": "returned",
    "qua_han": "overdue", "qua han": "overdue", "late": "overdue",
    "mat": "lost", "that_thoat": "lost", "that thoat": "lost",
}

# ----------------------------------------------------------------------
# TẠO BẢN GHI LỖI DỮ LIỆU (thống nhất 1 định dạng cho toàn hệ thống)
# ----------------------------------------------------------------------

def make_error(row: int, field: str, value: Any, message: str, table: str = "") -> Dict[str, Any]:
    """
    Tạo một bản ghi LỖI theo đúng định dạng đề bài yêu cầu:

        {"row": 18, "field": "due_date", "value": "abc", "error": "Invalid date"}

    `row` là số dòng thực tế trong file CSV (đã tính cả dòng header),
    giúp người dùng mở file CSV ra là tìm được ngay dòng bị lỗi.
    """
    error: Dict[str, Any] = {
        "row": row,
        "field": field,
        "value": "" if value is None else str(value),
        "error": message,
    }
    if table:
        error["table"] = table
    return error


# ----------------------------------------------------------------------
# CÁC HÀM CHUẨN HOÁ (dùng lại ở mọi nơi -> không duplicate logic)
# ----------------------------------------------------------------------

def normalize_text(value: Any) -> str:
    """
    Bỏ khoảng trắng đầu/cuối và gộp khoảng trắng ở giữa về đúng 1 dấu cách.

    Ví dụ: "  Laptop   Dell XPS 15  " -> "Laptop Dell XPS 15"
    """
    if value is None:
        return ""
    return " ".join(str(value).split())


def normalize_id(value: Any) -> str:
    """
    Chuẩn hoá mã định danh: IN HOA + bỏ toàn bộ khoảng trắng.

    Ví dụ: " tb 01 " -> "TB01"  (giúp ghép khoá giữa các bảng không bị lệch).
    """
    return "".join(normalize_text(value).upper().split())


def _alias_key(value: Any) -> str:
    """Chuẩn hoá trạng thái để tra trong bảng alias: thường + '_' thay khoảng trắng."""
    return normalize_text(value).lower().replace(" ", "_")


def normalize_status(value: Any, allowed: frozenset[str], aliases: Dict[str, str]) -> str:
    """
    Chuẩn hoá trạng thái về đúng bộ giá trị hợp lệ.

    - "Available"/"SAN_SANG"  -> "available"
    - "ĐANG MƯỢN"/"borrowed"  -> "borrowed" (nhờ DICT alias)
    - Giá trị lạ                -> giữ nguyên dạng thường để validators báo lỗi
      (KHÔNG tự bịa giá trị, tránh che mất lỗi dữ liệu thật).
    """
    text = normalize_text(value)
    if not text:
        return ""
    lowered = text.lower()
    if lowered in allowed:
        return lowered
    key = _alias_key(text)
    if key in aliases:
        return aliases[key]
    return lowered


def parse_date(value: Any) -> Optional[date]:
    """
    Parse chuỗi ngày theo nhiều định dạng trong DATE_FORMATS.

    Trả về `date` nếu hợp lệ, None nếu ô rỗng hoặc sai định dạng
    (None sẽ được validators báo lỗi thay vì làm chương trình crash).
    """
    text = normalize_text(value)
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def to_iso(value: Any) -> str:
    """Chuyển ngày về chuỗi ISO (YYYY-MM-DD); trả về '' nếu không parse được."""
    parsed = parse_date(value)
    return parsed.isoformat() if parsed else ""


# ----------------------------------------------------------------------
# ĐỌC CSV
# ----------------------------------------------------------------------

def load_csv(path: str | Path, columns: List[str]) -> List[Dict[str, str]]:
    """
    Đọc file CSV có header -> List[Dict], ánh xạ theo `columns` chuẩn.

    Xử lý được:
      - file không tồn tại / file rỗng  -> trả về [] (không crash);
      - header sai thứ tự / thiếu cột   -> vẫn đọc theo vị trí cột chuẩn;
      - dòng trống                      -> bỏ qua;
      - ô thiếu                          -> điền chuỗi rỗng "".

    Lỗi CẤU TRÚC (thiếu cột) do tầng UI kiểm tra trước bằng `missing_columns`,
    còn giá trị sai (ngày sai, thiếu mã...) do các hàm clean_* ghi nhận.
    """
    file_path = Path(path)
    if not file_path.exists() or file_path.stat().st_size == 0:
        return []

    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            next(reader)  # bỏ dòng header
        except StopIteration:
            return []

        rows: List[Dict[str, str]] = []
        for row_no, raw in enumerate(reader, start=2):   # dòng 1 là header
            if not any(cell.strip() for cell in raw):    # bỏ dòng trống
                continue
            row = {
                col: (raw[idx] if idx < len(raw) else "")
                for idx, col in enumerate(columns)
            }
            row["_row_no"] = row_no   # số dòng THỰC trong file -> báo lỗi đúng dòng
            rows.append(row)
    return rows


def missing_columns(path: str | Path, columns: List[str]) -> List[str]:
    """
    Kiểm tra CẤU TRÚC file: trả về danh sách cột còn thiếu trong header.

    Dùng Set để so sánh 2 tập cột (O(n)) thay vì duyệt lồng nhau.
    """
    file_path = Path(path)
    if not file_path.exists() or file_path.stat().st_size == 0:
        return []
    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = {normalize_text(cell).lower() for cell in next(reader)}
        except StopIteration:
            return []
    expected = {column.lower() for column in columns}
    return sorted(expected - header)   # hiệu tập hợp -> cột bị thiếu

# ----------------------------------------------------------------------
# HÀM DÙNG CHUNG CHO CÁC HÀM clean_*
# ----------------------------------------------------------------------

def _strip_meta(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Bỏ khoá nội bộ `_row_no` (số dòng trong file) để dữ liệu sạch không bị lẫn.

    Đây là lý do vì sao các hàm clean_* KHÔNG sửa trực tiếp dict đầu vào:
    chúng luôn làm việc trên bản sao -> hàm thuần (pure), dễ test.
    """
    return {key: value for key, value in row.items() if key != "_row_no"}


def drop_exact_duplicate_rows(
    rows: List[Dict[str, str]], columns: List[str], table: str
) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    """
    Loại các dòng bị TRÙNG HOÀN TOÀN (mọi cột giống nhau) — lỗi CSV rất hay gặp.

    [SET] Dùng `set` chứa tuple giá trị các cột để so trùng với chi phí O(1)
    cho mỗi dòng; nếu dùng List thì phải duyệt lại toàn bộ (O(n²)).

    Lưu ý phân biệt với validators: ở đây chỉ xử lý dòng trùng NGUYÊN BẢN,
    còn "trùng mã định danh nhưng dữ liệu khác nhau" là lỗi nghiệp vụ và
    do validators.py phát hiện (tránh làm trùng logic ở 2 nơi).
    """
    unique_rows: List[Dict[str, str]] = []
    errors: List[Dict[str, Any]] = []
    seen: set[Tuple[str, ...]] = set()

    for row in rows:
        signature = tuple(str(row.get(column, "")) for column in columns)
        if signature in seen:
            errors.append(
                make_error(
                    int(row.get("_row_no", 0)), "*",
                    " | ".join(signature),
                    "Dòng trùng hoàn toàn với dòng trước đó (đã tự động loại bỏ)",
                    table,
                )
            )
            continue
        seen.add(signature)
        unique_rows.append(row)
    return unique_rows, errors


# ----------------------------------------------------------------------
# LÀM SẠCH TỪNG BẢNG
# ----------------------------------------------------------------------

def clean_devices(raw_rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    """
    Làm sạch bảng THIẾT BỊ.

    Xử lý: trim khoảng trắng, chuẩn hoá mã (IN HOA), chuẩn hoá trạng thái
    theo bộ `available | borrowed | lost | maintenance`, phát hiện giá trị
    thiếu và trạng thái lạ. Trả về (rows, errors).
    """
    rows: List[Dict[str, str]] = []
    errors: List[Dict[str, Any]] = []

    for raw in raw_rows:
        row_no = int(raw.get("_row_no", 0))
        data = _strip_meta(raw)

        device_id = normalize_id(data.get("device_id"))
        if not device_id:
            errors.append(make_error(row_no, "device_id", data.get("device_id"),
                                     "Thiếu mã thiết bị (bắt buộc)", "devices"))

        device_name = normalize_text(data.get("device_name"))
        if not device_name:
            errors.append(make_error(row_no, "device_name", data.get("device_name"),
                                     "Thiếu tên thiết bị (bắt buộc)", "devices"))

        category = normalize_text(data.get("category"))
        if not category:
            errors.append(make_error(row_no, "category", data.get("category"),
                                     "Thiếu loại thiết bị (bắt buộc)", "devices"))

        raw_status = data.get("status")
        status = normalize_status(raw_status, DEVICE_STATUSES, DEVICE_STATUS_ALIASES)
        if not status:
            errors.append(make_error(row_no, "status", raw_status,
                                     "Thiếu trạng thái thiết bị", "devices"))
        elif status not in DEVICE_STATUSES:
            errors.append(make_error(
                row_no, "status", raw_status,
                f"Trạng thái thiết bị không hợp lệ: '{normalize_text(raw_status)}' "
                f"(chỉ nhận: {', '.join(sorted(DEVICE_STATUSES))})", "devices"))

        rows.append({
            "device_id": device_id,
            "device_name": device_name,
            "category": category,
            "status": status,
            "_row_no": row_no,   # giữ lại để validators/UI báo đúng dòng lỗi
        })

    rows, duplicate_errors = drop_exact_duplicate_rows(rows, DEVICE_COLUMNS, "devices")
    errors.extend(duplicate_errors)
    return rows, errors


def clean_borrowers(raw_rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    """
    Làm sạch bảng NGƯỜI MƯỢN: mã (IN HOA), tên, lớp.

    Trả về (rows, errors) — lỗi thiếu trường bắt buộc được ghi lại
    nhưng bản ghi vẫn được giữ ở dạng tối thiểu để validators có thể
    báo cáo tham chiếu (không âm thầm bỏ dữ liệu của người dùng).
    """
    rows: List[Dict[str, str]] = []
    errors: List[Dict[str, Any]] = []

    for raw in raw_rows:
        row_no = int(raw.get("_row_no", 0))
        data = _strip_meta(raw)

        borrower_id = normalize_id(data.get("borrower_id"))
        if not borrower_id:
            errors.append(make_error(row_no, "borrower_id", data.get("borrower_id"),
                                     "Thiếu mã người mượn (bắt buộc)", "borrowers"))

        name = normalize_text(data.get("name"))
        if not name:
            errors.append(make_error(row_no, "name", data.get("name"),
                                     "Thiếu tên người mượn (bắt buộc)", "borrowers"))

        class_name = normalize_text(data.get("class_name"))
        if not class_name:
            errors.append(make_error(row_no, "class_name", data.get("class_name"),
                                     "Thiếu lớp (bắt buộc)", "borrowers"))

        rows.append({
            "borrower_id": borrower_id,
            "name": name,
            "class_name": class_name,
            "_row_no": row_no,   # giữ lại để validators/UI báo đúng dòng lỗi
        })

    rows, duplicate_errors = drop_exact_duplicate_rows(rows, BORROWER_COLUMNS, "borrowers")
    errors.extend(duplicate_errors)
    return rows, errors


def clean_borrow_records(
    raw_rows: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    """
    Làm sạch bảng PHIẾU MƯỢN (bảng trung tâm của nghiệp vụ).

    Xử lý:
      - mã phiếu / mã người mượn / mã thiết bị: chuẩn hoá (IN HOA, bỏ khoảng trắng);
      - ngày mượn / hạn trả: BẮT BUỘC parse được -> ISO; sai thì ghi lỗi
        "Invalid date" (đúng định dạng error record của đề bài);
      - ngày trả: được phép rỗng (chưa trả), nhưng nếu có mà sai định dạng thì báo lỗi;
      - trạng thái: chuẩn hoá về borrowing | returned | overdue | lost;
        nếu bỏ trống thì SUY DIỄN theo nghiệp vụ:
        có ngày trả -> "returned", chưa có -> "borrowing";
      - dòng trùng hoàn toàn: tự loại bỏ và ghi lỗi.

    Trả về (rows, errors). Bản ghi lỗi vẫn được giữ lại (kèm `_row_no`)
    để tầng validation báo cáo đầy đủ — không âm thầm nuốt dữ liệu người dùng.
    """
    rows: List[Dict[str, str]] = []
    errors: List[Dict[str, Any]] = []

    for raw in raw_rows:
        row_no = int(raw.get("_row_no", 0))
        data = _strip_meta(raw)

        borrow_id = normalize_id(data.get("borrow_id"))
        if not borrow_id:
            errors.append(make_error(row_no, "borrow_id", data.get("borrow_id"),
                                     "Thiếu mã phiếu mượn (bắt buộc)", "borrow_records"))

        borrower_id = normalize_id(data.get("borrower_id"))
        if not borrower_id:
            errors.append(make_error(row_no, "borrower_id", data.get("borrower_id"),
                                     "Thiếu mã người mượn (bắt buộc)", "borrow_records"))

        device_id = normalize_id(data.get("device_id"))
        if not device_id:
            errors.append(make_error(row_no, "device_id", data.get("device_id"),
                                     "Thiếu mã thiết bị (bắt buộc)", "borrow_records"))

        # --- Ngày mượn / hạn trả: bắt buộc hợp lệ ---
        borrow_date = to_iso(data.get("borrow_date"))
        if not borrow_date:
            errors.append(make_error(row_no, "borrow_date", data.get("borrow_date"),
                                     "Invalid date (rỗng hoặc sai định dạng)",
                                     "borrow_records"))

        due_date = to_iso(data.get("due_date"))
        if not due_date:
            errors.append(make_error(row_no, "due_date", data.get("due_date"),
                                     "Invalid date (rỗng hoặc sai định dạng)",
                                     "borrow_records"))

        # --- Ngày trả: rỗng là hợp lệ (chưa trả); có giá trị thì phải đúng ---
        return_date = to_iso(data.get("return_date"))
        if normalize_text(data.get("return_date")) and not return_date:
            errors.append(make_error(row_no, "return_date", data.get("return_date"),
                                     "Invalid date (sai định dạng)", "borrow_records"))

        # --- Trạng thái: chuẩn hoá; lạ thì báo lỗi rồi suy diễn để không crash ---
        raw_status = normalize_text(data.get("status"))
        status = normalize_status(raw_status, RECORD_STATUSES, RECORD_STATUS_ALIASES)
        if status and status not in RECORD_STATUSES:
            errors.append(make_error(
                row_no, "status", data.get("status"),
                f"Trạng thái phiếu không hợp lệ: '{raw_status}' "
                f"(chỉ nhận: {', '.join(sorted(RECORD_STATUSES))})", "borrow_records"))
            status = ""
        if not status:
            status = "returned" if return_date else "borrowing"

        rows.append({
            "borrow_id": borrow_id,
            "borrower_id": borrower_id,
            "device_id": device_id,
            "borrow_date": borrow_date,
            "due_date": due_date,
            "return_date": return_date,
            "status": status,
            "_row_no": row_no,   # giữ lại để validators/UI báo đúng dòng lỗi
        })

    rows, duplicate_errors = drop_exact_duplicate_rows(rows, RECORD_COLUMNS, "borrow_records")
    errors.extend(duplicate_errors)
    return rows, errors