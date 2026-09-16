"""
validators.py — KIỂM TRA DỮ LIỆU (Validation)
===============================================================
Nhận dữ liệu ĐÃ LÀM SẠCH từ cleaners.py và kiểm tra NGHIỆP VỤ:

  1. Trường bắt buộc không được rỗng (mã định danh, ngày...).
  2. Trùng mã định danh trong từng bảng (duplicate ID).
  3. Mã tham chiếu không tồn tại: borrower_id / device_id trong phiếu
     không có trong danh mục.
  4. Logic NGÀY sai:
       - borrow_date > due_date;
       - return_date < borrow_date.
  5. Logic TRẠNG THÁI không phù hợp:
       - returned / lost nhưng không có ngày trả;
       - borrowing / overdue nhưng lại có ngày trả.
  6. Phát hiện QUÁ HẠN (today > due_date và chưa trả) và THẤT THOÁT
     (quá hạn >= LOST_THRESHOLD_DAYS hoặc phiếu ghi rõ status='lost').

=================================================================
TẠI SAO DÙNG SET? (câu hỏi vấn đáp — giải thích ngay tại từng hàm)
=================================================================
Set cho phép kiểm tra thành viên O(1) và các phép toán tập hợp:
  - DIFFERENCE (hiệu):  mã_trong_phiếu - mã_hợp_lệ -> mã KHÔNG tồn tại.
  - INTERSECTION (giao): thiết bị_đang_bị_mượn ∩ thiết bị_'available'
    -> danh mục ghi "sẵn sàng" nhưng thực tế đang bị mượn (mâu thuẫn).
  - UNION (hợp): phiếu_ghi_lost_rõ ∪ phiếu_quá_hạn_nặng -> tập thất thoát.
  - set 'seen' khi quét dòng: phát hiện TRÙNG MÃ với chi phí O(1)/dòng
    thay vì O(n^2) nếu dùng List.

Mọi lỗi trả về theo định dạng thống nhất cleaners.make_error:
    {row, field, value, error, table}
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

from cleaners import is_valid_phone, make_error, parse_date

#: Ngưỡng quá hạn để coi thiết bị là THẤT THOÁT (ngày).
LOST_THRESHOLD_DAYS: int = 30

#: Trạng thái phiếu cho thấy thiết bị VẪN ĐANG Ở NGOÀI (chưa quay lại kho).
BUSY_RECORD_STATUSES: frozenset = frozenset({"borrowing", "overdue", "lost"})


def _row_no(row: Dict[str, Any]) -> int:
    """Số dòng thực trong file CSV (do cleaners gắn vào mỗi bản ghi)."""
    return int(row.get("_row_no", 0))


# ----------------------------------------------------------------------
# 1) TRƯỜNG BẮT BUỘC + 2) TRÙNG MÃ
# ----------------------------------------------------------------------

def find_missing_required(
    rows: List[Dict[str, Any]], required: List[str], table: str
) -> List[Dict[str, Any]]:
    """Kiểm tra lại trường BẮT BUỘC sau khi làm sạch (không được rỗng)."""
    errors: List[Dict[str, Any]] = []
    for row in rows:
        for field in required:
            if not str(row.get(field, "")).strip():
                errors.append(
                    make_error(_row_no(row), field, row.get(field),
                               f"Thiếu giá trị bắt buộc '{field}'", table)
                )
    return errors


def find_duplicate_ids(
    rows: List[Dict[str, Any]], id_field: str, table: str
) -> Tuple[List[Dict[str, Any]], Set[str]]:
    """
    Phát hiện TRÙNG MÃ định danh trong một bảng.

    [SET] Dùng set `seen` để tra cứu O(1) cho từng dòng — với List phải
    quét lại toàn bộ danh sách (O(n^2)) nên không phù hợp với file lớn.
    Trả về (danh_sách_lỗi, tập_mã_bị_trùng).
    """
    errors: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    duplicated: Set[str] = set()

    for row in rows:
        value = str(row.get(id_field, "")).strip()
        if not value:
            continue  # thiếu mã đã được báo ở find_missing_required
        if value in seen:
            duplicated.add(value)   # [SET] thêm 1 lần dù trùng nhiều lần
            errors.append(
                make_error(_row_no(row), id_field, value,
                           f"Trùng mã '{value}' (đã xuất hiện trước đó)", table)
            )
        seen.add(value)
    return errors, duplicated


# ----------------------------------------------------------------------
# 3) THAM CHIẾU KHÔNG TỒN TẠI — [SET] DIFFERENCE
# ----------------------------------------------------------------------

def find_unknown_references(
    records: List[Dict[str, Any]],
    valid_device_ids: Set[str],
    valid_borrower_ids: Set[str],
) -> Tuple[List[Dict[str, Any]], Set[str], Set[str]]:
    """
    Đối chiếu mã trong PHIẾU với DANH MỤC bằng phép HIỆU tập hợp.

    [SET] TẠI SAO DÙNG SET?
      device_ids_in_records  - valid_device_ids   -> mã thiết bị KHÔNG tồn tại
      borrower_ids_in_records - valid_borrower_ids -> mã người mượn KHÔNG tồn tại
    difference là phép toán O(n) của set; nếu dùng List ta phải duyệt lồng
    O(n*m). Đây là nghiệp vụ đối chiếu dữ liệu giữa 2 bảng CSV.

    Trả về (errors, unknown_device_ids, unknown_borrower_ids).
    """
    device_ids_in_records = {str(r.get("device_id", "")).strip() for r in records} - {""}
    borrower_ids_in_records = {str(r.get("borrower_id", "")).strip() for r in records} - {""}

    # [SET] difference: phần tử có trong phiếu nhưng KHÔNG có trong danh mục.
    unknown_devices = device_ids_in_records - valid_device_ids
    unknown_borrowers = borrower_ids_in_records - valid_borrower_ids

    errors: List[Dict[str, Any]] = []
    for row in records:
        device_id = str(row.get("device_id", "")).strip()
        borrower_id = str(row.get("borrower_id", "")).strip()
        if device_id in unknown_devices:
            errors.append(
                make_error(_row_no(row), "device_id", device_id,
                           f"Thiết bị '{device_id}' không tồn tại trong devices.csv",
                           "borrow_records")
            )
        if borrower_id in unknown_borrowers:
            errors.append(
                make_error(_row_no(row), "borrower_id", borrower_id,
                           f"Người mượn '{borrower_id}' không tồn tại trong borrowers.csv",
                           "borrow_records")
            )
    return errors, unknown_devices, unknown_borrowers


def _to_date(value: Any) -> Optional[date]:
    """Chuyển ngày (ISO 'YYYY-MM-DD' hoặc DD/MM/YYYY) sang date; lỗi -> None."""
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return parse_date(text)


def find_date_logic_errors(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Phát hiện NGÀY phiếu mượn sai logic nghiệp vụ:

      - borrow_date > due_date   (ngày mượn sau ngày hạn trả);
      - return_date < borrow_date (trả trước cả ngày mượn).

    Ngày đã được cleaners chuẩn hoá về ISO; hàm chỉ so sánh và báo lỗi,
    KHÔNG tự sửa dữ liệu (tách bạch làm sạch và kiểm tra).
    """
    errors: List[Dict[str, Any]] = []
    for row in records:
        borrow_date = _to_date(row.get("borrow_date"))
        due_date = _to_date(row.get("due_date"))
        return_date = _to_date(row.get("return_date"))

        if borrow_date and due_date and borrow_date > due_date:
            errors.append(make_error(
                _row_no(row), "due_date", row.get("due_date"),
                f"Ngày mượn {row.get('borrow_date')} sau ngày hạn trả "
                f"{row.get('due_date')}", "borrow_records"))
        if return_date and borrow_date and return_date < borrow_date:
            errors.append(make_error(
                _row_no(row), "return_date", row.get("return_date"),
                f"Ngày trả {row.get('return_date')} trước ngày mượn "
                f"{row.get('borrow_date')}", "borrow_records"))
    return errors


def find_status_logic_errors(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Kiểm tra TRẠNG THÁI phiếu khớp với dữ liệu ngày trả:

      - 'returned' / 'lost'     -> BẮT BUỘC có return_date;
      - 'borrowing' / 'overdue' -> KHÔNG được có return_date
        (vẫn đang ở ngoài thì chưa thể có ngày trả thực tế).
    """
    errors: List[Dict[str, Any]] = []
    for row in records:
        status = str(row.get("status", "")).strip()
        return_date = str(row.get("return_date", "") or "").strip()

        if status in {"returned", "lost"} and not return_date:
            errors.append(make_error(
                _row_no(row), "return_date", return_date,
                f"Phiếu status='{status}' nhưng thiếu ngày trả thực tế",
                "borrow_records"))
        if status in {"borrowing", "overdue"} and return_date:
            errors.append(make_error(
                _row_no(row), "return_date", return_date,
                f"Phiếu status='{status}' vẫn đang mượn nhưng lại có ngày trả "
                f"'{return_date}'", "borrow_records"))
    return errors


# ----------------------------------------------------------------------
# 7) QUÁ HẠN — đầu vào cho thống kê, cảnh báo và bộ lọc "chỉ quá hạn"
# ----------------------------------------------------------------------

def find_overdue_records(
    records: List[Dict[str, Any]], today: Optional[date] = None
) -> List[Dict[str, Any]]:
    """
    Phát hiện PHIẾU QUÁ HẠN: today > due_date và phiếu CHƯA kết thúc
    (chưa có return_date và status != 'lost').

    Mỗi kết quả là BẢN SAO của phiếu + trường `days_overdue` (số ngày quá hạn)
    — dùng cho sorted(..., key=lambda r: r["days_overdue"], reverse=True)
    để xếp phiếu cần nhắc trả lên đầu.
    """
    today = today or date.today()
    overdue: List[Dict[str, Any]] = []
    for row in records:
        status = str(row.get("status", "")).strip()
        if status == "lost" or str(row.get("return_date", "") or "").strip():
            continue  # đã trả / đã khai báo mất -> không nằm trong "quá hạn"
        due = _to_date(row.get("due_date"))
        if due is None or today <= due:
            continue
        flag = dict(row)
        flag["days_overdue"] = (today - due).days
        overdue.append(flag)
    return overdue


def find_lost_devices(
    records: List[Dict[str, Any]], today: Optional[date] = None
) -> List[str]:
    """
    Danh sách mã THIẾT BỊ THẤT THOÁT (sắp tăng dần để báo cáo ổn định).

    [SET] UNION (hợp) 2 nguồn nghiệp vụ:
      (a) phiếu khai báo rõ status = 'lost'         -> mất theo khai báo;
      (b) quá hạn >= LOST_THRESHOLD_DAYS (30 ngày)  -> mất tiềm ẩn.
    difference/union của set chạy O(n); nếu dùng List phải duyệt lồng O(n^2).
    """
    today = today or date.today()
    declared: Set[str] = set()
    suspected: Set[str] = set()
    for row in records:
        device_id = str(row.get("device_id", "")).strip()
        if not device_id:
            continue
        if str(row.get("status", "")).strip() == "lost":
            declared.add(device_id)
            continue
        if str(row.get("return_date", "") or "").strip():
            continue
        due = _to_date(row.get("due_date"))
        if due is not None and (today - due).days >= LOST_THRESHOLD_DAYS:
            suspected.add(device_id)
    return sorted(declared | suspected)  # [SET] UNION


# ----------------------------------------------------------------------
# 8) MÂU THUẪN DANH MỤC — [SET] INTERSECTION
# ----------------------------------------------------------------------

def find_category_conflicts(
    devices: List[Dict[str, Any]], records: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Đối chiếu TRẠNG THÁI thiết bị giữa danh mục và phiếu mượn.

    [SET] INTERSECTION (giao):
      thiết bị_đang_bị_mượn_theo_phiếu ∩ thiết bị_danh_mục_ghi_'available'
      -> thiết bị đang ở ngoài nhưng danh mục lại ghi "sẵn sàng" (mâu thuẫn
      dữ liệu giữa 2 bảng CSV). Phép giao O(min(n,m)); với List phải duyệt
      lồng O(n*m).
    """
    busy = {
        str(r.get("device_id", "")).strip()
        for r in records
        if str(r.get("status", "")).strip() in BUSY_RECORD_STATUSES
    } - {""}
    available = {
        str(d.get("device_id", "")).strip()
        for d in devices
        if str(d.get("status", "")).strip() == "available"
    } - {""}
    conflicts = busy & available  # [SET] INTERSECTION

    errors: List[Dict[str, Any]] = []
    for row in devices:
        device_id = str(row.get("device_id", "")).strip()
        if device_id in conflicts:
            errors.append(make_error(
                _row_no(row), "status", row.get("status"),
                f"Thiết bị '{device_id}' đang bị mượn theo phiếu nhưng danh "
                f"mục lại ghi 'available'", "devices"))
    return errors


# ----------------------------------------------------------------------
# 9) KIỂM TRA MỘT BẢN GHI ỨNG VIÊN (dùng cho CRUD: Create / Update)
#    Chỉ TỔ HỢP các quy tắc đã có ở trên — không thêm luật nghiệp vụ mới,
#    để form nhập liệu không bao giờ tự định nghĩa lại validation.
# ----------------------------------------------------------------------

def find_busy_device_conflicts(
    candidates: List[Dict[str, Any]], existing_records: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Chặn mượn thiết bị ĐANG BỊ MƯỢN: ứng viên có trạng thái active
    (borrowing / overdue / lost) mà thiết bị đã có phiếu active khác
    (khác borrow_id) thì không được tạo/sửa.

    Chỉ dùng cho đường CREATE/UPDATE (`validate_candidate_record`); KHÔNG dùng
    trong `validate_all` để dữ liệu lịch sử có sẵn không bị gắn cờ hàng loạt.
    """
    busy_by_device: Dict[str, str] = {}
    for row in existing_records:
        if str(row.get("status", "")).strip() in BUSY_RECORD_STATUSES:
            device_id = str(row.get("device_id", "")).strip()
            if device_id:
                busy_by_device.setdefault(
                    device_id, str(row.get("borrow_id", "")).strip() or "?"
                )

    errors: List[Dict[str, Any]] = []
    for candidate in candidates:
        if str(candidate.get("status", "")).strip() not in BUSY_RECORD_STATUSES:
            continue
        device_id = str(candidate.get("device_id", "")).strip()
        if not device_id or device_id not in busy_by_device:
            continue
        errors.append(
            make_error(
                _row_no(candidate), "device_id", device_id,
                f"Thiết bị '{device_id}' đang được mượn ở phiếu "
                f"'{busy_by_device[device_id]}' — trả thiết bị trước khi mượn tiếp",
                "borrow_records",
            )
        )
    return errors


def _without_key(rows: List[Dict[str, Any]], key_field: str, key_value: Any) -> List[Dict[str, Any]]:
    """Bỏ các dòng có cùng khoá (khi EDIT, bản ghi cũ không tính là trùng chính nó)."""
    target = str(key_value or "").strip().upper()
    return [r for r in rows if str(r.get(key_field, "")).strip().upper() != target]


def validate_candidate_device(
    candidate: Dict[str, Any],
    devices: List[Dict[str, Any]],
    existing_records: Optional[List[Dict[str, Any]]] = None,
    editing: bool = False,
) -> List[Dict[str, Any]]:
    """Kiểm tra một thiết bị ứng viên (thêm mới hoặc sửa) bằng quy tắc hiện có."""
    others = _without_key(devices, "device_id", candidate.get("device_id")) if editing else list(devices)
    errors = find_missing_required(
        [candidate], ["device_id", "device_name", "category", "status"], "devices")
    errors += find_duplicate_ids(others + [candidate], "device_id", "devices")[0]
    if existing_records is not None:
        errors += find_category_conflicts([candidate], existing_records)
    return errors


def validate_candidate_borrower(
    candidate: Dict[str, Any],
    borrowers: List[Dict[str, Any]],
    editing: bool = False,
) -> List[Dict[str, Any]]:
    """Kiểm tra một người mượn ứng viên bằng quy tắc hiện có."""
    others = _without_key(borrowers, "borrower_id", candidate.get("borrower_id")) if editing else list(borrowers)
    errors = find_missing_required(
        [candidate], ["borrower_id", "name", "class_name"], "borrowers")
    errors += find_duplicate_ids(others + [candidate], "borrower_id", "borrowers")[0]
    phone = str(candidate.get("phone", "") or "").strip()
    if phone and not is_valid_phone(phone):
        errors.append(
            make_error(int(candidate.get("_row_no", 0)), "phone", candidate.get("phone"),
                       "Số điện thoại không hợp lệ (cần 10 số, bắt đầu bằng 0)",
                       "borrowers")
        )
    return errors


def validate_candidate_record(
    candidate: Dict[str, Any],
    devices: List[Dict[str, Any]],
    borrowers: List[Dict[str, Any]],
    existing_records: List[Dict[str, Any]],
    editing: bool = False,
) -> List[Dict[str, Any]]:
    """
    Kiểm tra một phiếu mượn ứng viên (thêm mới hoặc sửa).

    Gồm: trường bắt buộc, trùng mã phiếu, tham chiếu thiết bị/người mượn
    không tồn tại, logic ngày, logic trạng thái và thiết bị đang bị mượn —
    tất cả tái sử dụng nguyên các hàm kiểm tra phía trên.
    """
    others = _without_key(existing_records, "borrow_id", candidate.get("borrow_id")) if editing else list(existing_records)
    valid_device_ids = {str(d.get("device_id", "")).strip() for d in devices} - {""}
    valid_borrower_ids = {str(b.get("borrower_id", "")).strip() for b in borrowers} - {""}

    errors = find_missing_required(
        [candidate], ["borrow_id", "borrower_id", "device_id", "borrow_date", "due_date"],
        "borrow_records")
    errors += find_duplicate_ids(others + [candidate], "borrow_id", "borrow_records")[0]
    errors += find_unknown_references([candidate], valid_device_ids, valid_borrower_ids)[0]
    errors += find_date_logic_errors([candidate])
    errors += find_status_logic_errors([candidate])
    errors += find_busy_device_conflicts([candidate], others)
    return errors


# ----------------------------------------------------------------------
# validate_all — CHẠY TOÀN BỘ KIỂM TRA (main.py và app.py dùng chung)
# ----------------------------------------------------------------------

def validate_all(
    devices: List[Dict[str, Any]],
    borrowers: List[Dict[str, Any]],
    records: List[Dict[str, Any]],
    today: Optional[date] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """
    Chạy toàn bộ pipeline KIỂM TRA, trả về:

        (errors, overdue_records, lost_devices)

      - errors: mọi vi phạm theo định dạng cleaners.make_error
        {row, field, value, error, table} — đầu vào cho mục "CẢNH BÁO DỮ
        LIỆU" của báo cáo và trang Cảnh báo của dashboard;
      - overdue_records: phiếu quá hạn (kèm days_overdue) — đầu vào thống kê;
      - lost_devices: mã thiết bị thất thoát — đầu vào thống kê / báo cáo.

    Hàm KHÔNG sửa dữ liệu và KHÔNG raise — mọi vấn đề đều nằm trong errors
    nên hệ thống không bao giờ crash vì dữ liệu xấu (TEST 2-8 dựa trên đây).
    """
    today = today or date.today()
    errors: List[Dict[str, Any]] = []

    # 1) Trường bắt buộc (sau khi cleaners đã chuẩn hoá)
    errors += find_missing_required(
        devices, ["device_id", "device_name", "category"], "devices")
    errors += find_missing_required(
        borrowers, ["borrower_id", "name"], "borrowers")
    errors += find_missing_required(
        records, ["borrow_id", "borrower_id", "device_id", "borrow_date",
                  "due_date"], "borrow_records")

    # 2) Trùng mã định danh trong từng bảng ([SET] seen — O(1)/dòng)
    errors += find_duplicate_ids(devices, "device_id", "devices")[0]
    errors += find_duplicate_ids(borrowers, "borrower_id", "borrowers")[0]
    errors += find_duplicate_ids(records, "borrow_id", "borrow_records")[0]

    # 3) Tham chiếu không tồn tại ([SET] difference giữa 2 bảng CSV)
    valid_device_ids = {str(d.get("device_id", "")).strip() for d in devices} - {""}
    valid_borrower_ids = {str(b.get("borrower_id", "")).strip() for b in borrowers} - {""}
    errors += find_unknown_references(records, valid_device_ids, valid_borrower_ids)[0]

    # 4-5) Logic ngày + logic trạng thái phiếu
    errors += find_date_logic_errors(records)
    errors += find_status_logic_errors(records)

    # 6) Mâu thuẫn trạng thái giữa danh mục và phiếu ([SET] intersection)
    errors += find_category_conflicts(devices, records)

    # 7) Quá hạn + thất thoát ([SET] union) — đầu vào cho tầng thống kê
    overdue_records = find_overdue_records(records, today)
    lost_devices = find_lost_devices(records, today)
    return errors, overdue_records, lost_devices