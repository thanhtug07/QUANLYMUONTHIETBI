# 🎓 Quản lý mượn thiết bị (Python + CSV + Streamlit)

Bài tập môn Python: ứng dụng **quản lý phiếu mượn / trả thiết bị**, tự động phát hiện
**mượn quá hạn** và **thiết bị thất thoát**.

Công nghệ: Python thuần + file CSV + giao diện **Streamlit**.
Không dùng database, không dùng FastAPI / Flask / Django.

---

## ✅ Tính năng

- Theo dõi mượn / trả thiết bị qua phiếu mượn (`borrow_records.csv`).
- Làm sạch dữ liệu: chuẩn hoá chuỗi, mã thiết bị, ngày tháng (`cleaners.py`).
- Kiểm tra & đối chiếu dữ liệu bằng **Set** (`validators.py`):
  - phát hiện trùng mã;
  - kiểm tra tham chiếu (thiết bị / người mượn trong phiếu so với danh sách hợp lệ);
  - kiểm tra logic ngày (ngày mượn ≤ ngày hạn trả).
- Phát hiện phiếu **QUÁ HẠN** và thiết bị **THẤT THOÁT**
  (quá hạn ≥ `validators.LOST_THRESHOLD_DAYS` = 30 ngày).
- Cấu trúc dữ liệu: **List, Tuple, Dictionary, Set**.
- **Dictionary có ý nghĩa thực tế** (`statistics.py`):
  - `devices_by_id = {"TB001": {...}, ...}` — tra cứu thiết bị O(1);
  - `borrowers_by_id = {"SV001": {...}, ...}` — tra cứu người mượn O(1);
  - `join_records_with_names()` dùng 2 Dictionary trên để ghép
    `ten_thiet_bi`, `loai_thiet_bi`, `ten_nguoi_muon` vào từng phiếu.
- Thống kê / lọc / sắp xếp **sorted + lambda (reverse=True)** (`statistics.py`).
- Báo cáo text `output/report.txt` (`reports.py`).
- Dashboard **Streamlit** gồm **7 module**: Tổng quan · Phiếu mượn · Thiết bị ·
  Người mượn · Cảnh báo · Báo cáo · Dữ liệu CSV.
- **CRUD đầy đủ** cho Phiếu mượn / Thiết bị / Người mượn (thêm — sửa — xóa với
  dialog + bước xác nhận), ghi trực tiếp vào `data/*.csv` qua `data_store.py`.
  Mọi dữ liệu nhập đều được kiểm tra bằng chính `validators.py` trước khi ghi.

---

## 📈 Thống kê & lọc có sẵn

**10 thống kê** (`statistics.compute_all`):

| # | Thống kê | Hàm |
|---|---|---|
| 1 | Tổng số lượt mượn | `count_total_borrows` |
| 2 | Số thiết bị đang được mượn | `count_currently_borrowed` |
| 3 | Số lượt đã trả | `count_returned` |
| 4 | Số lượt quá hạn | `overdue_summary` |
| 5 | Số thiết bị thất thoát | `count_lost` |
| 6 | Tỷ lệ trả đúng hạn (%) | `on_time_return_rate` |
| 7 | Top thiết bị được mượn nhiều nhất | `top_devices_by_borrows` |
| 8 | Top người mượn nhiều nhất | `top_borrowers_by_borrows` |
| 9 | Số lượt mượn theo loại thiết bị (join qua Dictionary) | `borrows_by_device_type` |
| 10 | Số ngày quá hạn lớn nhất / trung bình | `overdue_summary` |

**Bộ lọc** (PHẦN 3):

| Lọc | Hàm |
|---|---|
| Theo trạng thái | `statistics.filter_by_status` |
| Theo thiết bị | `statistics.filter_by_device` |
| Theo người mượn | `statistics.filter_by_borrower` |
| Dữ liệu quá hạn | `statistics.filter_overdue` |
| Tìm kiếm theo keyword | `statistics.search_records` |

**Sắp xếp `sorted(..., key=lambda ..., reverse=True)`** (PHẦN 4):
`top_devices_by_borrows`, `top_borrowers_by_borrows`, `overdue_days_list`.

---

## 🗂 Cấu trúc project

```
D:\Python QUan ly muon\
│
├── app.py              # Entrypoint Streamlit: shell + điều phối page
├── main.py             # Pipeline CLI (python main.py)
├── cleaners.py         # Đọc CSV + làm sạch dữ liệu
├── validators.py       # Kiểm tra / đối chiếu (Set), quá hạn, thất thoát
├── statistics.py       # Thống kê, lọc, sắp xếp (Dictionary + sorted + lambda)
├── reports.py          # Tạo và ghi báo cáo text
├── data_store.py       # Đọc/ghi CSV an toàn (nguồn duy nhất cho thao tác CRUD)
│
├── pages\              # Mỗi module nghiệp vụ là một page: render(analysis)
│   ├── common.py       #   helper dùng chung (lọc phiếu, dòng bảng, lựa chọn trạng thái)
│   ├── overview.py     #   Tổng quan (KPI + chart + bảng + cảnh báo + xếp hạng)
│   ├── borrowing.py    #   Phiếu mượn (CRUD)
│   ├── equipment.py    #   Thiết bị (CRUD)
│   ├── borrowers.py    #   Người mượn (CRUD)
│   ├── alerts.py       #   Cảnh báo (quá hạn / thất thoát / cần kiểm tra)
│   ├── reports.py      #   Báo cáo (analytics + báo cáo văn bản)
│   └── csv_data.py     #   Dữ liệu CSV (trạng thái, preview, thay thế file)
│
├── ui\                 # Component UI dùng chung cho mọi page:
│                        #   app_shell, sidebar, header, layout, filters, metrics,
│                        #   charts, tables, badges, forms, dialogs, states
├── styles\             # Design system: tokens.py (nguồn duy nhất) + dashboard.css
├── utils\              # Helper thuần cho UI (nhãn trạng thái, format ngày, icon SVG)
├── tests\              # pytest: helper + data_store + smoke test từng page (AppTest)
│
├── data\
│   ├── devices.csv         # Thiết bị (24 bản ghi mẫu)
│   ├── borrowers.csv       # Người mượn (12 bản ghi mẫu)
│   └── borrow_records.csv  # Phiếu mượn (63 bản ghi mẫu, có cả dòng lỗi)
│
├── output\
│   └── report.txt          # Báo cáo được ghi khi chạy pipeline
│
├── requirements.txt    # streamlit
└── README.md
```

### Vai trò các module

| Module | Vai trò | Cấu trúc dữ liệu |
|---|---|---|
| `cleaners.py` | Đọc CSV, làm sạch chuỗi / mã / ngày | List, Dict |
| `validators.py` | Trùng mã, tham chiếu, quá hạn, thất thoát | Set |
| `statistics.py` | Thống kê, lọc, top, số ngày quá hạn | List, Tuple, Dict, Set + `sorted` & `lambda` |
| `reports.py` | Tạo nội dung báo cáo, ghi file | List |
| `main.py` | CLI: đọc → sạch → kiểm tra → thống kê → báo cáo | — |
| `data_store.py` | Đọc RAW / ghi CSV atomic (insert, update, delete, mã kế tiếp) | Dict, List |
| `app.py` | Chỉ ĐIỀU PHỐI: nạp dữ liệu, dựng shell, gọi page đang mở | — |
| `pages/*.py` | Mỗi page một module, hàm `render(analysis)`; CRUD nằm ở đây | — |
| `ui/*` | Component UI: shell, sidebar, header, filter, KPI, chart, bảng, form, dialog | — |
| `styles/*` | Design tokens + CSS (mọi giá trị trực quan đi qua CSS variables) | — |
| `utils/helpers.py` | Helper thuần cho UI (không chứa business logic) | — |

> Lưu ý: `statistics.py` trùng tên với thư viện chuẩn `statistics`,
> nên trong module này **không** import thư viện chuẩn đó (tránh shadowing).

---

## 📊 Dashboard Streamlit — 7 module

Sidebar gồm 2 nhóm điều hướng và mỗi mục là một module riêng (URL dạng
`?page=<slug>` nên tải lại trang vẫn ở đúng module):

| Nhóm | Mục | Nội dung |
|---|---|---|
| Quản lý | **Tổng quan** | Bộ lọc · 4 KPI · biểu đồ cột (lượt mượn theo loại) 8 phần + biểu đồ thanh ngang (trạng thái thiết bị) 4 phần · bảng phiếu mượn · cảnh báo cần xử lý · Top thiết bị / Top người mượn |
| Quản lý | **Phiếu mượn** | Toolbar (tìm kiếm · trạng thái · khoảng thời gian · đặt lại) + bảng 9 cột; chọn dòng → Xem / Sửa / Xóa |
| Quản lý | **Thiết bị** | Toolbar (tìm kiếm · loại · trạng thái · sắp xếp · đặt lại) + bảng (Mã, Tên, Loại, Trạng thái, Lượt mượn) + CRUD |
| Quản lý | **Người mượn** | Toolbar (tìm kiếm · lớp · sắp xếp · đặt lại) + bảng (Mã, Họ tên, Lớp, Lượt mượn, Đang mượn) + CRUD |
| Quản lý | **Cảnh báo** | 3 nhóm: Quá hạn (kèm số ngày) · Thất thoát · Cần kiểm tra dữ liệu; mỗi mục có nút xem chi tiết |
| Quản lý | **Báo cáo** | 4 KPI · biểu đồ cột theo loại · **donut** phân bố trạng thái · biểu đồ đường theo tháng (chỉ tháng có dữ liệu) · cảnh báo nghiệp vụ · báo cáo văn bản |
| Dữ liệu | **CSV** | Trạng thái từng file (số dòng thô/hợp lệ, cập nhật gần nhất, kết quả kiểm tra), preview, thay thế file bằng bản tải lên (kiểm tra đủ cột + xác nhận) |

### CRUD hoạt động thế nào

- Không tạo database / API mới: dữ liệu vẫn là `data/*.csv`.
- `data_store.py` ghi **atomic** (file tạm → `os.replace`) và chỉ đổi đúng bản ghi
  liên quan; đọc RAW nên giữ nguyên cả những dòng dữ liệu lỗi đang dùng để kiểm thử.
- Form dùng `validators.validate_candidate_*` — chính các quy tắc nghiệp vụ hiện có
  (bắt buộc, trùng mã, tham chiếu thiết bị/người mượn, logic ngày, logic trạng thái).
  Lỗi hiển thị ngay trong form và **không ghi** gì vào file.
- Xóa luôn qua bước xác nhận; mã mới (`PM0xx`, `TB0xx`, `SV0xx`) được suy ra từ mã
  lớn nhất đang có, không sinh số ngẫu nhiên.
- Sau mỗi thao tác ghi, cache pipeline được xoá nên dashboard tự làm mới.

Kiến trúc UI: `app.py` (điều phối) → `pages/*` (module) → `ui/*` (component) →
`styles/*` (design tokens + CSS). Mọi số liệu hiển thị đều lấy từ
`statistics.compute_all` / `validators` — không có số liệu giả, không hardcode KPI.

### Kiểm thử

```bash
python -m pytest tests -q   # cần cài thêm pytest
```

- `tests/test_ui.py`: helper thuần (nhãn trạng thái, lọc thời gian, format ngày, icon).
- `tests/test_data_store.py`: CRUD ở tầng dữ liệu trên file CSV tạm (insert/update/delete,
  mã kế tiếp, không đụng dòng khác) + validation ứng viên của form.
- `tests/test_app_smoke.py`: chạy THẬT `app.py` bằng `streamlit.testing.v1.AppTest`
  (KPI, biểu đồ, bảng, bộ lọc, tìm kiếm) trên trang Tổng quan.
- `tests/test_pages.py`: render cả 7 page, điều hướng, và luồng CRUD của trang Phiếu mượn
  (chọn dòng → action bar → dialog xem/sửa/xóa, xác nhận trước khi xóa, tạo phiếu qua form
  rồi xoá lại; fixture tự khôi phục `data/*.csv` sau khi test).
- `tests/test_states.py`: các khối trạng thái (hướng dẫn khởi đầu, không có kết quả,
  lỗi dữ liệu, dải gợi ý) — kiểm tra **CTA thật sự gọi callback** khi bấm, không chỉ hiển thị chữ.
- `tests/test_pages.py` còn kiểm tra **phân trang** (Prev/Next, địa chỉ `x–y / z`, Prev disabled
  ở trang đầu) và **đặt trạng thái hàng loạt** cho thiết bị (đổi đúng trường `status`, không
  đụng dòng khác).

Mọi thay đổi dữ liệu (upload CSV hoặc sửa file trong `data/`) đều đi qua
**toàn bộ pipeline**:

```
CSV → cleaners → validators → statistics → reports → dashboard
```

`app.py` chỉ gọi lại các module trên (UI + điều phối), **không sao chép**
logic xử lý dữ liệu; các KPI và biểu đồ đều lấy từ `statistics.compute_all`.

---

## ⚠ Trạng thái lỗi trên UI (không hiện traceback)

| Tình huống | Thông báo |
|---|---|
| File rỗng / chỉ có header | *"Không có dữ liệu để phân tích."* |
| Không còn bản ghi hợp lệ | *"Không có bản ghi hợp lệ."* |
| Sai cấu trúc (thiếu cột) | *"File 'devices.csv' không đúng cấu trúc. Thiếu các cột: ..."* |

Ngoài ra mọi lỗi runtime đều được bắt và hiển thị dưới dạng thông báo thân thiện.

### Trạng thái giao diện luôn có bước tiếp theo

Không khối trạng thái nào chỉ nói "không có gì" — mỗi khối đều nói rõ việc cần làm:

| Trạng thái | Gợi ý trên UI | Hành động kèm theo |
|---|---|---|
| Hệ thống chưa có dữ liệu | 3 bước bắt đầu (kiểm tra CSV → thay file → quay lại) | **Mở trang Dữ liệu CSV** |
| Bộ lọc không ra kết quả | Nới mốc thời gian / loại / trạng thái / từ khoá | **Đặt lại bộ lọc** |
| Lỗi đọc dữ liệu | Nêu lỗi an toàn + việc cần kiểm tra | **Thử lại** (đọc lại CSV) |
| Bảng có dòng để thao tác | "Bấm vào một dòng…" (dải gợi ý) | – (chọn dòng để mở Sửa/Xóa) |
| CRUD thành công | Notice trong trang + toast góc màn hình | – |

---

## 🚀 Cài đặt & chạy

### 1. Cài đặt thư viện

```bash
pip install -r requirements.txt
```

### 2. Chạy dashboard (khuyên dùng để demo)

```bash
streamlit run app.py
```

### 3. Chạy pipeline CLI (sinh báo cáo)

```bash
python main.py
```

Kết quả: báo cáo được ghi vào `output\report.txt`.

---

## 🧪 Dữ liệu mẫu (sample data)

Các file CSV trong `data/` (header tiếng Anh, ngày dạng `dd/mm/yyyy`) hiện có:
**24 thiết bị, 12 người mượn, 64 dòng phiếu mượn** — bao gồm đủ tình huống:
trả đúng hạn, trả muộn, đang mượn, quá hạn, thiết bị thất thoát, cùng một số dòng
lỗi chủ đích để kiểm thử `cleaners` / `validators`.

- `devices.csv`: `device_id,device_name,category,status`
- `borrowers.csv`: `borrower_id,name,class_name`
- `borrow_records.csv`: `borrow_id,borrower_id,device_id,borrow_date,due_date,return_date,status`

> Có thể thay thế dữ liệu ở trang **Dữ liệu CSV** (upload + kiểm tra đủ cột + xác nhận) —
> dữ liệu luôn đi qua toàn bộ pipeline (cleaners → validators → statistics).

---

## 📌 Lộ trình phát triển

- **Phase 1 ✅:** khung ứng dụng, các file CSV có header.
- **Phase 2 ✅:** dữ liệu mẫu, thống kê + bộ lọc (Dictionary / sorted + lambda),
  báo cáo text, dashboard Streamlit (6 trang + upload + trạng thái lỗi).
- **Phase 3 ✅:** tách tầng UI, design system, SaaS shell 7 module + CRUD ghi thẳng vào CSV.
- **Phase 4 (mở):** tinh chỉnh quy tắc (ngưỡng thất thoát), nâng cao phần làm sạch
  (dữ liệu nhiễu, tập dữ liệu lớn), bổ sung nhật ký thao tác nếu cần.
