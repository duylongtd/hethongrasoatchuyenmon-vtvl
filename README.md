# Hệ thống rà soát chuyên môn VTVL (Sở, ban, ngành – Xã, phường)

Rà soát bộ biểu Vị trí việc làm (A1, A2, B1, C1, C3, D1, D2): giờ làm việc so với chuẩn 1.904 giờ/người/năm,
đề xuất thêm/bớt người (D1 ↔ C3 ↔ D2), cân đối giữa các bộ phận, và đối chiếu biên chế giao theo
**Quyết định số 2398/QĐ-UBND ngày 04/10/2026** của UBND tỉnh Hà Tĩnh (Phụ lục 1–4).

## Chạy trên máy

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py          # http://127.0.0.1:8050
```

Dòng lệnh: `.venv/bin/python run_audit_cli.py "<file bộ biểu .xlsx>"` → báo cáo Excel trong `ket_qua_ra_soat/`.

## Quy tắc chính

- **Nhận diện đơn vị** (QĐ 2398): cột "Cơ quan" biểu `1. A1_NhiemVu` → tên file → nội dung D1/C1.
  Xã/phường lấy Phụ lục 1 (công chức) làm số chính, kèm Trạm Y tế, TT Dịch vụ tổng hợp, trường học cùng địa bàn.
- **Bộ phận / nhóm chức danh** (bộ biểu không có cột Phòng): ký hiệu trong mã VTVL (HĐND, UBND, VHXH, KTHT, TTHCC)
  → bộ phận nêu trong tên chức danh (Phòng…, Chi cục…, Trạm…, Trung tâm…, Trường…)
  → nhóm vị trí việc làm theo NĐ 62/2020 (Lãnh đạo, quản lý / Chuyên môn chuyên ngành / Chuyên môn dùng chung / Hỗ trợ, phục vụ).
- **Vị trí kiêm nhiệm**: cảnh báo vàng.

## Cập nhật dữ liệu QĐ 2398

Phụ lục gốc nằm trong `data/qd2398/`. Khi có phụ lục mới:

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python scripts/build_qd2398_data.py   # tự đối chiếu mọi dòng tổng, lệch là dừng
```

## Deploy Vercel

Vercel tự nhận `app` (FastAPI) trong `app.py` và cài `requirements.txt`.
Trên Vercel: file chỉ ghi vào `/tmp/vtvl`; API theo đường dẫn chỉ đọc file đã tải lên (`ALLOW_LOCAL_PATHS=0`).

> ⚠️ Vercel giới hạn **4,5 MB** cho thân request của Function. Bộ biểu 30.000 dòng thường 6–43 MB
> nên tải trực tiếp lên `/api/audit-upload` sẽ bị từ chối (413) cho tới khi chuyển sang đọc file ngay trên trình duyệt
> và chỉ gửi phần dữ liệu cần thiết.

## Bảo mật dữ liệu

`uploads/`, `ket_qua_ra_soat/` và mọi file `.xlsx` bị loại khỏi git (`.gitignore`) – không đưa bộ biểu thật của đơn vị lên repo.
