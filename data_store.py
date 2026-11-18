# -*- coding: utf-8 -*-
"""
data_store.py — GHI DỮ LIỆU CSV (Create / Update / Delete)
==========================================================
Tầng truy cập dữ liệu duy nhất cho thao tác GHI. Project dùng CSV làm nguồn
dữ liệu (không database, không API) nên CRUD được persist trực tiếp vào
`data/*.csv` — đúng kiến trúc hiện có.

Nguyên tắc an toàn dữ liệu:
  - Đọc file ở dạng RAW (không làm sạch) để giữ nguyên MỌI giá trị gốc,
    kể cả các dòng dữ liệu lỗi đang dùng cho việc kiểm thử cleaners/validators.
  - Chỉ thay đổi đúng dòng liên quan (update/delete) hoặc thêm dòng mới (create).
  - Ghi qua file tạm rồi `os.replace` (atomic) để không làm hỏng file gốc nếu
    có sự cố giữa chừng.
  - Giữ nguyên thứ tự cột và thứ tự dòng.

Module này KHÔNG chứa quy tắc nghiệp vụ (quy tắc nằm ở validators.py).
"""
from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def _norm_key(value: Any) -> str:
    """Chuẩn hoá khoá định danh giống cleaners.normalize_id (IN HOA, bỏ khoảng trắng)."""
    if value is None:
        return ""
    return "".join(str(value).upper().split())


def read_raw_rows(path: str | Path, columns: Sequence[str]) -> List[Dict[str, str]]:
    """
    Đọc file CSV ở dạng RAW: trả về List[Dict] theo `columns`, giá trị giữ
    nguyên như trong file (không trim, không chuẩn hoá).

    File không tồn tại / rỗng / lỗi đọc (sai encoding...) -> rỗng (không crash).
    """
    file_path = Path(path)
    if not file_path.exists() or file_path.stat().st_size == 0:
        return []

    rows: List[Dict[str, str]] = []
    try:
        with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            try:
                header = next(reader)
            except StopIteration:
                return []
            header_map = {
                " ".join(str(cell).split()).lower(): idx for idx, cell in enumerate(header)
            }
            use_header = all(col.lower() in header_map for col in columns)
            col_indices = [
                header_map[col.lower()] if use_header else idx
                for idx, col in enumerate(columns)
            ]
            for raw in reader:
                if not any(cell.strip() for cell in raw):
                    continue
                rows.append(
                    {
                        column: (raw[col_idx] if col_idx < len(raw) else "")
                        for column, col_idx in zip(columns, col_indices)
                    }
                )
    except (OSError, UnicodeDecodeError, csv.Error):
        return []
    return rows


def write_rows(path: str | Path, columns: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    """Ghi lại toàn bộ file CSV theo `columns`, ghi atomic qua file tạm."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    handle_fd, temp_name = tempfile.mkstemp(
        prefix=file_path.name, suffix=".tmp", dir=str(file_path.parent)
    )
    os.close(handle_fd)
    temp_path = Path(temp_name)
    try:
        with temp_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({column: str(row.get(column, "")) for column in columns})
        os.replace(temp_path, file_path)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def next_sequential_id(rows: Sequence[Dict[str, Any]], id_field: str, prefix: str, width: int = 3) -> str:
    """
    Sinh mã kế tiếp dựa trên mã LỚN NHẤT đang có (ví dụ TB001 -> TB025).

    Không dùng số ngẫu nhiên: mã luôn suy ra từ dữ liệu thật đang có trong file.
    """
    highest = 0
    for row in rows:
        raw = _norm_key(row.get(id_field, ""))
        if not raw.startswith(prefix.upper()):
            continue
        suffix = raw[len(prefix):]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"{prefix}{highest + 1:0{width}d}"


def insert_row(path: str | Path, columns: Sequence[str], row: Dict[str, Any]) -> None:
    """
    Thêm một dòng mới vào cuối file CSV.

    Ném ValueError nếu `row[id_field]` đã tồn tại trong file (so khớp không
    phân biệt hoa/thường, bỏ khoảng trắng — cùng quy tắc với update/delete)
    để khoá định danh luôn duy nhất ở tầng dữ liệu.
    """
    id_field = columns[0]
    new_id = _norm_key(row.get(id_field, ""))
    rows = read_raw_rows(path, columns)
    if new_id and any(_norm_key(existing.get(id_field, "")) == new_id for existing in rows):
        raise ValueError(f"'{new_id}' đã tồn tại trong {Path(path).name} — không thể thêm bản ghi trùng mã.")
    rows.append({column: str(row.get(column, "")) for column in columns})
    write_rows(path, columns, rows)


def update_row(
    path: str | Path,
    columns: Sequence[str],
    key_field: str,
    key_value: str,
    new_values: Dict[str, Any],
) -> bool:
    """
    Cập nhật dòng có `key_field == key_value` (giữ nguyên vị trí dòng).

    Trả về True nếu tìm thấy và cập nhật, False nếu không có dòng nào khớp.
    """
    rows = read_raw_rows(path, columns)
    target = _norm_key(key_value)
    found = False
    for index, row in enumerate(rows):
        if _norm_key(row.get(key_field, "")) == target:
            rows[index] = {column: str(new_values.get(column, row.get(column, ""))) for column in columns}
            found = True
    if found:
        write_rows(path, columns, rows)
    return found


def delete_row(path: str | Path, columns: Sequence[str], key_field: str, key_value: str) -> int:
    """Xoá mọi dòng có `key_field == key_value`; trả về số dòng đã xoá."""
    rows = read_raw_rows(path, columns)
    target = _norm_key(key_value)
    kept = [row for row in rows if _norm_key(row.get(key_field, "")) != target]
    removed = len(rows) - len(kept)
    if removed:
        write_rows(path, columns, kept)
    return removed


def delete_rows(
    path: str | Path,
    columns: Sequence[str],
    key_field: str,
    key_values: Sequence[str],
) -> int:
    """
    Xoá nhiều dòng theo danh sách khoá; trả về số dòng đã xoá.

    Ghi file đúng một lần để bulk delete vẫn atomic và không làm xáo trộn các
    dòng không liên quan.
    """
    targets = {_norm_key(value) for value in key_values if _norm_key(value)}
    if not targets:
        return 0

    rows = read_raw_rows(path, columns)
    kept = [
        row for row in rows
        if _norm_key(row.get(key_field, "")) not in targets
    ]
    removed = len(rows) - len(kept)
    if removed:
        write_rows(path, columns, kept)
    return removed


def find_rows(path: str | Path, columns: Sequence[str], key_field: str, key_value: str) -> List[Dict[str, str]]:
    """Các dòng RAW khớp khoá (dùng để hiển thị/nhân bản dữ liệu khi edit)."""
    target = _norm_key(key_value)
    return [
        row
        for row in read_raw_rows(path, columns)
        if _norm_key(row.get(key_field, "")) == target
    ]


def count_rows(path: str | Path) -> int:
    """Số dòng dữ liệu (không tính header) — dùng cho trang CSV."""
    file_path = Path(path)
    if not file_path.exists() or file_path.stat().st_size == 0:
        return 0
    try:
        with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            try:
                next(reader)
            except StopIteration:
                return 0
            return sum(1 for raw in reader if any(cell.strip() for cell in raw))
    except (OSError, UnicodeDecodeError, csv.Error):
        return 0


def file_columns(path: str | Path) -> List[str]:
    """Header thực tế của file CSV (rỗng nếu không đọc được)."""
    file_path = Path(path)
    if not file_path.exists() or file_path.stat().st_size == 0:
        return []
    try:
        with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            try:
                return [cell.strip() for cell in next(reader)]
            except StopIteration:
                return []
    except (OSError, UnicodeDecodeError, csv.Error):
        return []


def last_modified(path: str | Path) -> Optional[float]:
    """Thời điểm sửa file gần nhất (epoch giây) — dùng để hiển thị trạng thái."""
    file_path = Path(path)
    if not file_path.exists():
        return None
    return file_path.stat().st_mtime


def sync_device_status(
    devices_csv: str | Path,
    records_csv: str | Path,
    device_Columns: Sequence[str],
    record_columns: Sequence[str],
    device_ids: Sequence[str],
) -> None:
    """
    Đồng bộ trạng thái thiết bị trong `devices.csv` khi tạo/sửa/xóa phiếu mượn.

    Quy tắc:
      - Nếu thiết bị có phiếu active status == 'lost' -> 'lost'
      - Nếu thiết bị có phiếu active status in {'borrowing', 'overdue'} -> 'borrowed'
      - Nếu không còn phiếu active nào và danh mục đang là 'borrowed' -> 'available'
        (giữ nguyên 'maintenance' nếu đang bảo trì).
    """
    targets = {_norm_key(did) for did in device_ids if _norm_key(did)}
    if not targets:
        return
    devices = read_raw_rows(devices_csv, device_Columns)
    records = read_raw_rows(records_csv, record_columns)
    active_by_device: Dict[str, set[str]] = {}
    for rec in records:
        did = _norm_key(rec.get("device_id", ""))
        st_code = str(rec.get("status", "")).strip().lower()
        if did in targets and st_code in ("borrowing", "overdue", "lost"):
            active_by_device.setdefault(did, set()).add(st_code)

    changed = False
    for dev in devices:
        did = _norm_key(dev.get("device_id", ""))
        if did not in targets:
            continue
        statuses = active_by_device.get(did, set())
        cur = str(dev.get("status", "")).strip().lower()
        if "lost" in statuses:
            new_st = "lost"
        elif statuses & {"borrowing", "overdue"}:
            new_st = "borrowed"
        elif cur == "borrowed":
            new_st = "available"
        else:
            new_st = cur
        if new_st and new_st != cur:
            dev["status"] = new_st
            changed = True
    if changed:
        write_rows(devices_csv, device_Columns, devices)
