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
│                        #   + sample_data.py (sinh dữ liệu mẫu, không chứa Streamlit)
├── tests\              # pytest: sample_data (16 test: sinh/chuẩn/ID/FK/ghi nối/backup/flow)
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
| Quản lý | **Tổng quan** | Bộ lọc · 5 KPI · biểu đồ cột (lượt mượn theo loại) 8 phần + biểu đồ thanh ngang (trạng thái thiết bị) 4 phần · bảng phiếu mượn · cảnh báo cần xử lý · Top thiết bị / Top người mượn |
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
python -m pytest tests -q
```

| File | Nội dung |
|---|---|
| `test_data_safety.py` (11 test) | CSV thiếu/rỗng/chỉ-header/khoảng trắng/sai encoding/thiếu cột/ngoặc kép lỗi/cột thừa/trùng mã/FK lạ/ngày sai/status lạ đều không crash |
| `test_sample_data.py` (16 test) | Sinh mẫu đúng schema, không trùng ID, FK hợp lệ, ghi nối giữ byte cũ, backup/restore |
| `test_crud_safety.py` (17 test) | Phân trang, update khóa lạ, bulk-status qua validation, delete count, mã kế tiếp |
| `test_dashboard_stats.py` (8 test) | Đếm theo thứ, kỳ trước, chuỗi delta, markup pill KPI |
| `test_ui_polish.py` (7 test) | Tokens status, variant badge, màu chart, CSS dùng biến |
| `test_app_pages.py` (5 test) + `test_borrowing_header_actions.py` (4 test) | AppTest 7 trang + nút header bảng phiếu |
| `test_alerts_filter.py` (3 test) | Lọc cảnh báo theo query/severity/kết hợp |

Tổng: **71 test**, toàn bộ xanh (`python -m pytest tests -q`).

### Kiến thức Python được sử dụng

| Kiến thức | Thể hiện ở |
|---|---|
| Function, Module | Mọi file đều là module hàm thuần (cleaners/validators/statistics/reports) |
| String | `normalize_text`, `normalize_id`, chuẩn hóa mã/trạng thái (cleaners) |
| List, Tuple | Danh sách bản ghi (List); Top-N `(mã, lượt)` và `DEVICE_COLUMNS` (Tuple) |
| Range | Sinh mã kế tiếp, chia trang, kiểm tra theo dòng |
| Dictionary | `devices_by_id`/`borrowers_by_id` tra cứu O(1) + JOIN (statistics) |
| Set | Đối chiếu FK, trùng mã, mâu thuẫn danh mục, thất thoát (validators, 14 điểm dùng) |
| CSV | Đọc/ghi toàn bộ qua `csv` + atomic write (data_store) |
| try/except | File thiếu/rỗng/sai encoding không crash (cleaners + data_store) |
| lambda, sorted | `sorted(..., key=lambda ...)` xếp Top-N, quá hạn, tháng (statistics ×5) |
| Streamlit | Dashboard 7 module (app.py + pages/ + ui/) |

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

### 4. Deploy lên Streamlit Community Cloud (miễn phí)

1. Vào [share.streamlit.io](https://share.streamlit.io) → đăng nhập bằng GitHub.
2. **Create app** → chọn repo này, branch `main`, main file **`app.py`**.
3. App chạy với `requirements.txt` và theme đã có sẵn trong repo.

**Lưu ý dữ liệu khi chạy trên cloud:** Streamlit Community Cloud chạy app trong
container không có ổ đĩa bền vững — mọi thao tác CRUD ghi vào `data/*.csv`
chỉ tồn tại tạm thời và **mất đi khi app ngủ/restart/redeploy** (app sẽ trở lại
đúng dữ liệu trong repo). Cách khắc phục theo mức tăng dần:
| Cách | Chịu được | Độ phức tạp |
|---|---|---|
| Chạy local (`streamlit run app.py`) | mọi thứ, persist vĩnh viễn | 0 |
| Export CSV từ mỗi trang CRUD sau khi nhập liệu | mất khi app restart | 0 |
| Đồng bộ `data/` về repo qua GitHub (push từ chỗ khác) | chừng nào chưa redeploy | thấp |
| Gắn volume bền: Google Drive API / Dropbox / S3 | restart + redeploy | trung |
| Đổi sang SQLite + Streamlit `st.connection` | mọi thao tác CRUD online | cao hơn |

Demo/bảo vệ thì chạy **local** là chuẩn nhất; bản cloud dùng để xem giao diện.

### Known limitations (giới hạn đã biết)

| Giới hạn | Biểu hiện | Cách xử lý |
|---|---|---|
| Cloud ephemeral (không ổ đĩa bền) | CRUD trên cloud mất sau restart/redeploy | Chạy local hoặc Export CSV sau khi nhập |
| Font chart là webfont | Biểu đồ Altair/Vega dùng `Source Sans 3`, nếu máy chặn Google Fonts sẽ rớt về `Segoe UI`/sans-serif hệ thống | Không ảnh hưởng số liệu; giao diện vẫn đọc tốt |
| Bảng rộng trên màn hình hẹp | Streamlit cho cuộn ngang trong khối bảng; header bảng "dính" theo cơ chế mặc định của Streamlit | Dùng màn hình ≥1024px để xem đủ 9 cột phiếu mượn |
| Animation tôn trọng `prefers-reduced-motion` | Máy bật giảm chuyển động sẽ thấy giao diện tĩnh (không page-enter/KPI stagger) | Chủ đích vì accessibility, không phải lỗi |
| Cache theo mtime | `st.cache_data` khóa theo mtime_ns của 3 file CSV; sửa file bằng tay trong lúc app chạy vẫn tự làm mới ở rerun kế tiếp | Nhấn Rerun nếu vừa sửa file ngoài app |

---

## 🧪 Dữ liệu mẫu (sample data)

Các file CSV trong `data/` (header tiếng Anh, ngày dạng `dd/mm/yyyy`) hiện có:
**60 thiết bị** (Laptop, Máy chiếu, Tablet, Màn hình, Camera, Loa, Micro, Chuột,
Bàn phím, Ổ điện, Phấn - Bảng, Đèn - Quạt, Cáp - Điều khiển), **250 người mượn**,
**276 dòng phiếu mượn thô (275 phiếu hợp lệ sau làm sạch, 11 bản ghi lỗi)**
— bao gồm đủ tình huống:
trả đúng hạn, trả muộn, đang mượn, quá hạn, thiết bị thất thoát, cùng một số dòng
lỗi chủ đích để kiểm thử `cleaners` / `validators`.

- `devices.csv`: `device_id,device_name,category,status`
- `borrowers.csv`: `borrower_id,name,class_name,phone` (`borrower_id` là mã sinh viên; `phone` tuỳ chọn, nếu nhập phải 10 số bắt đầu bằng 0)
- `borrow_records.csv`: `borrow_id,borrower_id,device_id,borrow_date,due_date,return_date,status`

> Có thể thay thế dữ liệu ở trang **Dữ liệu CSV** (upload + kiểm tra đủ cột + xác nhận) —
> dữ liệu luôn đi qua toàn bộ pipeline (cleaners → validators → statistics).

### Thêm dữ liệu mẫu (trang Dữ liệu CSV)

Card **"Dữ liệu mẫu"** cho phép thêm nhanh dữ liệu demo/test trực tiếp trên giao diện:

- Button **"+ Thêm dữ liệu mẫu"** (primary) → dialog xác nhận: chọn số lượng
  mỗi loại (`5 / 10 / 20 / 50` — phiếu mượn sinh gấp đôi để đủ tình huống),
  tick chọn loại (`Thiết bị / Người mượn / Phiếu mượn`), xem tổng
  (`Thiết bị +10 · Người mượn +10 · Phiếu mượn +20 · Tổng +40`) rồi **Xác nhận thêm**.
- Dữ liệu được **ghi nối** vào đúng 3 file CSV hiện tại (`devices.csv`,
  `borrowers.csv`, `borrow_records.csv`) — không database, không API.
- **Không trùng ID:** mã mới nối tiếp mã lớn nhất đang có
  (qua `data_store.next_sequential_id`, ví dụ `TB060 → TB061`), không hardcode.
- **Hợp lệ:** mọi bản ghi đều qua `validators.validate_candidate_*` trước khi ghi;
  phiếu mới đủ variation (đã trả / đang mượn / quá hạn / thất thoát), FK luôn
  trỏ tới mã tồn tại, ngày thỏa `borrow_date ≤ due_date`.
- Ghi qua `data_store.write_rows` (**atomic**, giữ nguyên dòng cũ),
  xong tự **xóa cache + rerun** nên dashboard/biểu đồ/cảnh báo cập nhật ngay.
- Button **"Khôi phục dữ liệu mẫu"** (riêng một cấp, có xác nhận + cảnh báo):
  hoàn tác lần thêm gần nhất từ bản sao lưu tự động trong `data/.sample_backup/`
  (được tạo trước mỗi lần ghi). Chưa có sao lưu thì button disabled.

> ⚠ Dữ liệu demo được **ghi trực tiếp vào CSV thật** (giống mọi thao tác CRUD).

---

## 📌 Lộ trình phát triển

- **Phase 1 ✅:** khung ứng dụng, các file CSV có header.
- **Phase 2 ✅:** dữ liệu mẫu, thống kê + bộ lọc (Dictionary / sorted + lambda),
  báo cáo text, dashboard Streamlit (6 trang + upload + trạng thái lỗi).
- **Phase 3 ✅:** tách tầng UI, design system, SaaS shell 7 module + CRUD ghi thẳng vào CSV.
- **Phase 4 (mở):** tinh chỉnh quy tắc (ngưỡng thất thoát), nâng cao phần làm sạch
  (dữ liệu nhiễu, tập dữ liệu lớn), bổ sung nhật ký thao tác nếu cần.

---

## ▶️ Demo flow (5 phút)

1. `streamlit run app.py` → trang **Dashboard**: 5 KPI + pill delta (bật filter "30 ngày" để thấy delta so kỳ trước).
2. Biểu đồ **Ngày mượn nhiều nhất** (cột đỉnh tô đậm) + **gauge Tỷ lệ đúng hạn** → nút "Xem báo cáo".
3. Trang **Phiếu mượn**: tìm kiếm, lọc trạng thái, nút "Mới nhất", chọn dòng → Xem/Sửa/Xóa (ô mã khóa khi sửa).
4. Trang **Cảnh báo**: 3 nhóm Quá hạn / Thất thoát / Cần kiểm tra, bấm Chi tiết từng mục.
5. Trang **Dữ liệu CSV**: "+ Thêm dữ liệu mẫu" (chọn số lượng, xác nhận, dashboard cập nhật ngay) và "Khôi phục" để hoàn tác.
6. `python main.py` → xem tóm tắt console + `output/report.txt`.
7. `python -m pytest tests -q` → toàn bộ test xanh.
