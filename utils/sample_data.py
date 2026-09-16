# -*- coding: utf-8 -*-
"""
utils/sample_data.py — SINH DỮ LIỆU MẪU CHO DEMO / TEST
=======================================================
Module thuần (không import streamlit): chỉ TẠO dữ liệu mẫu hợp lệ.

Kiến trúc::

    pages/csv_data.py  ->  utils/sample_data.py  ->  validators.py
                                                 ->  data_store.py  ->  data/*.csv

- Sinh mã NỐI TIẾP từ mã lớn nhất đang có (qua `data_store.next_sequential_id`,
  không hardcode TB001/SV001/PM001) nên không bao giờ trùng ID.
- Mọi bản ghi sinh ra đều đi qua `validators.validate_candidate_*` trước khi
  ghi — dữ liệu không hợp lệ thì raise, không ghi gì cả.
- Ghi file qua `data_store.write_rows` (atomic: file tạm + `os.replace`),
  giữ nguyên thứ tự và nội dung các dòng cũ.
- Trước mỗi lần ghi, 3 file hiện tại được sao lưu vào
  `data/.sample_backup/` để chức năng "Khôi phục" có thể hoàn tác.
"""
from __future__ import annotations

import random
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import data_store
import validators
from cleaners import BORROWER_COLUMNS, DEVICE_COLUMNS, RECORD_COLUMNS

#: Các mức số lượng cho phép chọn trên UI.
SAMPLE_QUANTITIES: Tuple[int, ...] = (5, 10, 20, 50)

#: Thư mục sao lưu trước khi thêm mẫu (để "Khôi phục" hoàn tác).
BACKUP_DIRNAME = ".sample_backup"

#: Pool (tên, loại) — đúng chính tả loại đang có trong CSV để filter nhóm được.
DEVICE_POOL: Tuple[Tuple[str, str], ...] = (
    ("Laptop Dell Latitude 5440", "Laptop"),
    ("Laptop HP ProBook 440", "Laptop"),
    ("Laptop Lenovo ThinkPad E14", "Laptop"),
    ("Laptop Asus Vivobook 15", "Laptop"),
    ("Máy chiếu Epson EB-X05", "Máy chiếu"),
    ("Máy chiếu Panasonic PT-LB305", "Máy chiếu"),
    ("Máy chiếu Sony VPL-EX455", "Máy chiếu"),
    ("Tablet iPad Gen 10", "Tablet"),
    ("Tablet Samsung Galaxy Tab A8", "Tablet"),
    ("Màn hình Dell P2422H 24", "Màn hình"),
    ("Màn hình LG 27MP400 27", "Màn hình"),
    ("Camera Sony HDR-CX405", "Camera"),
    ("Camera Canon XA11", "Camera"),
    ("Webcam Logitech C920", "Camera"),
    ("Loa Bluetooth JBL PartyBox", "Loa"),
    ("Loa kéo Acnos CS3600", "Loa"),
    ("Loa trợ giảng Shidu S615", "Loa"),
    ("Micro không dây Shure SVX", "Micro"),
    ("Micro trợ giảng Takstar", "Micro"),
    ("Micro có dây Shure SM58", "Micro"),
    ("Chuột Logitech M331", "Chuột"),
    ("Chuột không dây Rapoo M100", "Chuột"),
    ("Chuột gaming Logitech G304", "Chuột"),
    ("Bàn phím Keychron K3", "Bàn phím"),
    ("Bàn phím Logitech K120", "Bàn phím"),
    ("Ổ điện Lioa 6 lỗ 3m", "Ổ điện"),
    ("Ổ điện Điện Quang 4 lỗ 5m", "Ổ điện"),
    ("Cuộn dây điện 20m phòng học", "Ổ điện"),
    ("Hộp phấn trắng Thái Bình", "Phấn - Bảng"),
    ("Bảng phụ di động 1.2m", "Phấn - Bảng"),
    ("Bút trình chiếu Logitech R400", "Cáp - Điều khiển"),
    ("Cáp HDMI 10m phòng học", "Cáp - Điều khiển"),
    ("Quạt đứng Senko DR1608", "Đèn - Quạt"),
    ("Đèn LED để bàn học", "Đèn - Quạt"),
)

_HO = ("Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Đỗ", "Vũ", "Bùi", "Đặng",
       "Ngô", "Dương", "Lý", "Võ", "Huỳnh", "Phan", "Trương", "Đinh", "Mai")
_DEM_NAM = ("Văn", "Hữu", "Đức", "Minh", "Quốc", "Thanh", "Công", "Xuân")
_DEM_NU = ("Thị", "Ngọc", "Thu", "Thanh", "Kim", "Mỹ", "Bảo", "Hồng")
_TEN_NAM = ("An", "Cường", "Em", "Giang", "Khoa", "Minh", "Nam", "Phong",
            "Quang", "Sơn", "Tài", "Tuấn", "Việt", "Huy", "Đạt", "Long", "Phúc")
_TEN_NU = ("Bình", "Dung", "Phương", "Hạnh", "Lan", "Nga", "Anh", "Hà",
           "Hương", "Linh", "Mai", "Thảo", "Trang", "Yến", "Quỳnh", "Châu")
CLASSES = ("CNTT-K45", "CNTT-K46", "CNTT-K47", "CNTT-K48", "KHMT-K45",
           "KHMT-K46", "HTTT-K46", "HTTT-K47", "KTPM-K47", "KTPM-K48",
           "MMT-K46", "KHDL-K47")


def _seq_ids(rows: Sequence[Dict[str, Any]], id_field: str,
             prefix: str, count: int) -> List[str]:
    """`count` mã nối tiếp từ mã lớn nhất đang có (TB025 sau TB024...)."""
    ids: List[str] = []
    probe = list(rows)
    for _ in range(count):
        new_id = data_store.next_sequential_id(probe, id_field, prefix)
        ids.append(new_id)
        probe.append({id_field: new_id})
    return ids


def _fmt(day: date) -> str:
    """Ngày theo đúng văn phong CSV hiện tại (dd/mm/yyyy)."""
    return day.strftime("%d/%m/%Y")


def generate_sample_devices(count: int, existing: Sequence[Dict[str, Any]],
                            rng: Optional[random.Random] = None) -> List[Dict[str, str]]:
    """Sinh `count` thiết bị: tên/loại từ pool phòng học, mặc định sẵn sàng."""
    rng = rng or random.Random()
    ids = _seq_ids(list(existing), "device_id", "TB", count)
    rows: List[Dict[str, str]] = []
    for device_id in ids:
        name, category = rng.choice(DEVICE_POOL)
        rows.append({"device_id": device_id, "device_name": name,
                     "category": category, "status": "available"})
    return rows


def generate_sample_borrowers(count: int, existing: Sequence[Dict[str, Any]],
                              rng: Optional[random.Random] = None) -> List[Dict[str, str]]:
    """Sinh `count` người mượn: tên Việt Nam + lớp, mã SV nối tiếp."""
    rng = rng or random.Random()
    ids = _seq_ids(list(existing), "borrower_id", "SV", count)
    taken = {str(r.get("name", "")).strip() for r in existing} - {""}
    prefixes = ("090", "091", "093", "097", "098", "032", "033", "070", "079", "084")
    rows: List[Dict[str, str]] = []
    for borrower_id in ids:
        female = rng.random() < 0.45
        for _ in range(100):  # tránh trùng tên hiển thị trong batch
            name = (f"{rng.choice(_HO)} {rng.choice(_DEM_NU if female else _DEM_NAM)} "
                    f"{rng.choice(_TEN_NU if female else _TEN_NAM)}")
            if name not in taken:
                taken.add(name)
                break
        phone = (
            "" if rng.random() < 0.1  # ~10% để trống (trường tuỳ chọn)
            else rng.choice(prefixes) + "".join(rng.choice("0123456789") for _ in range(7))
        )
        rows.append({"borrower_id": borrower_id, "name": name,
                     "class_name": rng.choice(CLASSES), "phone": phone})
    return rows


def generate_sample_records(count: int, device_ids: Sequence[str],
                            borrower_ids: Sequence[str],
                            existing: Sequence[Dict[str, Any]],
                            today: Optional[date] = None,
                            rng: Optional[random.Random] = None) -> List[Dict[str, str]]:
    """
    Sinh `count` phiếu mượn đủ variation cho demo: đã trả / đang mượn /
    quá hạn / thất thoát. FK luôn lấy từ danh mục (không orphan), ngày thỏa
    borrow <= due, `returned`/`lost` có return_date, `borrowing`/`overdue`
    để trống return_date — đúng `validators`.
    """
    if not device_ids or not borrower_ids:
        raise ValueError("Cần ít nhất một thiết bị và một người mượn để sinh phiếu.")
    rng = rng or random.Random()
    today = today or date.today()
    ids = _seq_ids(list(existing), "borrow_id", "PM", count)
    rows: List[Dict[str, str]] = []
    for index, borrow_id in enumerate(ids):
        kind = index % 10  # 0-5 trả, 6-7 mượn, 8 quá hạn, 9 thất thoát
        device_id = rng.choice(list(device_ids))
        borrower_id = rng.choice(list(borrower_ids))
        if kind <= 5:
            borrow = today - timedelta(days=rng.randint(20, 110))
            due = borrow + timedelta(days=rng.randint(7, 14))
            late = rng.random() < 0.25
            ret = (due + timedelta(days=rng.randint(1, 8)) if late
                   else borrow + timedelta(days=rng.randint(1, 9)))
            ret = min(ret, today - timedelta(days=1))
            ret = max(ret, borrow)
            rows.append({"borrow_id": borrow_id, "borrower_id": borrower_id,
                         "device_id": device_id, "borrow_date": _fmt(borrow),
                         "due_date": _fmt(due), "return_date": _fmt(ret),
                         "status": "returned"})
        elif kind <= 7:
            borrow = today - timedelta(days=rng.randint(0, 6))
            due = borrow + timedelta(days=rng.randint(7, 14))
            rows.append({"borrow_id": borrow_id, "borrower_id": borrower_id,
                         "device_id": device_id, "borrow_date": _fmt(borrow),
                         "due_date": _fmt(due), "return_date": "",
                         "status": "borrowing"})
        elif kind == 8:
            borrow = today - timedelta(days=rng.randint(15, 40))
            due = borrow + timedelta(days=rng.randint(7, 10))
            if due >= today:
                due = today - timedelta(days=rng.randint(1, 10))
            rows.append({"borrow_id": borrow_id, "borrower_id": borrower_id,
                         "device_id": device_id, "borrow_date": _fmt(borrow),
                         "due_date": _fmt(due), "return_date": "",
                         "status": "overdue"})
        else:
            borrow = today - timedelta(days=rng.randint(40, 90))
            due = borrow + timedelta(days=10)
            reported = due + timedelta(days=rng.randint(30, 60))
            if reported > today:
                reported = today
            rows.append({"borrow_id": borrow_id, "borrower_id": borrower_id,
                         "device_id": device_id, "borrow_date": _fmt(borrow),
                         "due_date": _fmt(due), "return_date": _fmt(reported),
                         "status": "lost"})
    return rows


def plan_sample_data(devices_n: int, borrowers_n: int, records_n: int,
                     devices: Sequence[Dict[str, Any]],
                     borrowers: Sequence[Dict[str, Any]],
                     records: Sequence[Dict[str, Any]],
                     seed: Optional[int] = None,
                     today: Optional[date] = None) -> Dict[str, List[Dict[str, str]]]:
    """
    Lập kế hoạch dữ liệu mẫu (chưa ghi): sinh borrowers -> devices ->
    records, rồi khớp trạng thái thiết bị mới với phiếu active
    (đang mượn/quá hạn -> borrowed, thất thoát -> lost) để không gây mâu
    thuẫn danh mục ở `validators.find_category_conflicts`.
    """
    rng = random.Random(seed)
    new_borrowers = generate_sample_borrowers(borrowers_n, borrowers, rng)
    new_devices = generate_sample_devices(devices_n, devices, rng)
    pool_devices = [str(d.get("device_id", "")).strip() for d in list(devices) + new_devices]
    pool_devices = [d for d in pool_devices if d]
    pool_borrowers = [str(b.get("borrower_id", "")).strip()
                      for b in list(borrowers) + new_borrowers]
    pool_borrowers = [b for b in pool_borrowers if b]
    new_records = (generate_sample_records(records_n, pool_devices, pool_borrowers,
                                           records, today, rng) if records_n else [])
    # Phiếu active (borrowing/overdue/lost) phải nằm trên thiết bị RẢNH (mỗi
    # thiết bị tối đa 1 phiếu active) — vừa tránh mâu thuẫn danh mục
    # (find_category_conflicts) vừa qua luật thiết-bị-bận của
    # validate_candidate_record. Ưu tiên thiết bị MỚI (trạng thái do khối
    # busy/lost dưới quyết định nên luôn nhất quán), thiếu mới dùng thiết bị
    # cũ đang rảnh. Hết thiết bị rảnh thì giữ nguyên để tầng kiểm tra ở
    # append_sample_data từ chối thay vì ghi dữ liệu xấu.
    new_ids = [str(d.get("device_id", "")).strip() for d in new_devices]
    new_ids = [i for i in new_ids if i]
    busy_existing = {
        str(r.get("device_id", "")).strip() for r in records
        if str(r.get("status", "")).strip() in ("borrowing", "overdue", "lost")
    } - {""}
    # Thiết bị cũ chỉ dùng được khi đang RẢNH và trạng thái danh mục đã khác
    # "available" (borrowed/lost/maintenance) — gán phiếu active cho thiết bị
    # cũ "available" sẽ tạo mâu thuẫn danh mục MỚI và bị từ chối ở dưới.
    idle_existing = [
        str(d.get("device_id", "")).strip() for d in devices
        if str(d.get("device_id", "")).strip()
        and str(d.get("device_id", "")).strip() not in busy_existing
        and str(d.get("status", "")).strip().lower() != "available"
    ]
    idle_pool = new_ids + idle_existing
    rng.shuffle(idle_pool)
    active_records = [r for r in new_records if r["status"] in ("borrowing", "overdue", "lost")]
    for record, device_id in zip(active_records, idle_pool):
        record["device_id"] = device_id
    busy = {r["device_id"] for r in new_records if r["status"] in ("borrowing", "overdue")}
    lost = {r["device_id"] for r in new_records if r["status"] == "lost"}
    for device in new_devices:
        if device["device_id"] in lost:
            device["status"] = "lost"
        elif device["device_id"] in busy:
            device["status"] = "borrowed"
    # ~10% thiết bị mới không dính phiếu active -> bảo trì cho đủ variation.
    idle = [d for d in new_devices if d["device_id"] not in busy | lost]
    for device in idle[: max(0, devices_n // 10)]:
        device["status"] = "maintenance"
    return {"devices": new_devices, "borrowers": new_borrowers, "records": new_records}


def backup_paths(data_dir: Path) -> Dict[str, Path]:
    """Đường dẫn 3 file sao lưu trong thư mục backup."""
    backup_dir = Path(data_dir) / BACKUP_DIRNAME
    return {"devices": backup_dir / "devices.csv",
            "borrowers": backup_dir / "borrowers.csv",
            "records": backup_dir / "borrow_records.csv"}


def has_backup(data_dir: Path) -> bool:
    """Có bản sao lưu hoàn chỉnh để khôi phục hay không."""
    return all(p.exists() for p in backup_paths(Path(data_dir)).values())


def append_sample_data(devices_n: int, borrowers_n: int, records_n: int,
                       devices_csv: Path, borrowers_csv: Path, records_csv: Path,
                       seed: Optional[int] = None,
                       today: Optional[date] = None) -> Dict[str, int]:
    """
    Sinh + kiểm tra + ghi nối dữ liệu mẫu vào 3 CSV. Trả về số dòng đã thêm.
    Raise ValueError nếu dữ liệu không qua validation — không ghi gì cả.
    """
    if devices_n < 0 or borrowers_n < 0 or records_n < 0:
        raise ValueError("Số lượng dữ liệu mẫu không được âm.")
    if devices_n + borrowers_n + records_n == 0:
        raise ValueError("Chưa chọn loại dữ liệu mẫu nào để thêm.")

    devices = data_store.read_raw_rows(devices_csv, DEVICE_COLUMNS)
    borrowers = data_store.read_raw_rows(borrowers_csv, BORROWER_COLUMNS)
    records = data_store.read_raw_rows(records_csv, RECORD_COLUMNS)

    plan = plan_sample_data(devices_n, borrowers_n, records_n,
                            devices, borrowers, records, seed, today)

    errors: List[Dict[str, Any]] = []
    all_devices = list(devices) + plan["devices"]
    for device in plan["devices"]:
        # Loại chính ứng viên khỏi danh sách so trùng (tránh "trùng chính nó").
        rest = [d for d in all_devices if d is not device]
        errors += validators.validate_candidate_device(
            device, rest, existing_records=None, editing=False)
    all_borrowers = list(borrowers) + plan["borrowers"]
    for borrower in plan["borrowers"]:
        rest = [b for b in all_borrowers if b is not borrower]
        errors += validators.validate_candidate_borrower(
            borrower, rest, editing=False)
    all_records = list(records) + plan["records"]
    for record in plan["records"]:
        rest = [r for r in all_records if r is not record]
        errors += validators.validate_candidate_record(
            record, all_devices, all_borrowers, rest, editing=False)
    # Kiểm tra mâu thuẫn danh mục trên TOÀN BỘ dữ liệu sau khi thêm (so với
    # trước khi thêm): chỉ các mâu thuẫn MỚI do batch mẫu gây ra mới bị từ
    # chối — dữ liệu gốc đã xấu thì không đổ lỗi cho batch mới. Kiểm tra cũ
    # chỉ soi thiết bị mới nên lọt lưới phiếu active trỏ vào thiết bị cũ.
    base_conflicts = validators.find_category_conflicts(devices, records)
    full_conflicts = validators.find_category_conflicts(all_devices, all_records)
    base_msgs = {e.get("error", "") for e in base_conflicts}
    errors += [e for e in full_conflicts if e.get("error", "") not in base_msgs]
    if errors:
        raise ValueError(f"Dữ liệu mẫu không hợp lệ ({len(errors)} lỗi).")

    # Sao lưu trước khi ghi để "Khôi phục" có thể hoàn tác.
    backups = backup_paths(devices_csv.parent)
    backups["devices"].parent.mkdir(parents=True, exist_ok=True)
    for key, src in (("devices", devices_csv), ("borrowers", borrowers_csv),
                     ("records", records_csv)):
        if Path(src).exists():
            shutil.copy2(src, backups[key])

    if plan["devices"]:
        data_store.write_rows(devices_csv, DEVICE_COLUMNS,
                              devices + plan["devices"])
    if plan["borrowers"]:
        data_store.write_rows(borrowers_csv, BORROWER_COLUMNS,
                              borrowers + plan["borrowers"])
    if plan["records"]:
        data_store.write_rows(records_csv, RECORD_COLUMNS, records + plan["records"])
    return {"devices": len(plan["devices"]), "borrowers": len(plan["borrowers"]),
            "records": len(plan["records"])}


def restore_sample_backup(devices_csv: Path, borrowers_csv: Path,
                          records_csv: Path) -> Dict[str, int]:
    """Khôi phục 3 CSV từ bản sao lưu gần nhất. Raise nếu chưa có sao lưu."""
    backups = backup_paths(devices_csv.parent)
    if not has_backup(devices_csv.parent):
        raise ValueError("Chưa có bản sao lưu nào để khôi phục.")
    counts: Dict[str, int] = {}
    for key, dest, columns in (
            ("devices", devices_csv, DEVICE_COLUMNS),
            ("borrowers", borrowers_csv, BORROWER_COLUMNS),
            ("records", records_csv, RECORD_COLUMNS)):
        rows = data_store.read_raw_rows(backups[key], columns)
        data_store.write_rows(dest, columns, rows)
        counts[key] = len(rows)
    return counts
