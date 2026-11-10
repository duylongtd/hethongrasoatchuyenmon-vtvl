# -*- coding: utf-8 -*-
"""
Bộ đọc dữ liệu Bộ biểu VTVL từ file Excel (.xlsx).
Đọc nhanh các biểu A1, A2, B1, C1, C3, D1, D2 (dừng sớm khi hết vùng dữ liệu để xử lý file 30.000 dòng dưới 0.5 giây).
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import openpyxl

from .dept_parser import parse_department, classify_role_level, detect_org_type

STANDARD_HOURS = 1904.0
MAX_EMPTY_STREAK = 50


def _to_float(val: Any, default: float = 0.0) -> float:
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _to_opt_float(val: Any) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _to_str(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


# ---------------------------------------------------------------------------
# Dữ liệu sheet trích sẵn từ trình duyệt (dùng khi deploy Vercel: không gửi cả file .xlsx
# vì vượt giới hạn 4,5 MB của request). Định dạng payload:
#   {"file_name": "...", "sheet_names": [...tất cả sheet...],
#    "sheets": {"6. C1_VTVL": {"start_row": 3, "rows": [[...], ...]}, ...}}
# Các lớp dưới đây giả lập đúng phần API openpyxl mà bộ đọc đang dùng (sheetnames, wb[name],
# ws.iter_rows(min_row, max_row, max_col, values_only=True)) để logic đọc giữ nguyên 100%.
# ---------------------------------------------------------------------------
SHEET_SPECS: Dict[str, Dict[str, Any]] = {
    # tên sheet: số cột cần đọc, cột khóa để xác định dòng trống (0-based), giới hạn dòng
    "1. A1_NhiemVu": {"max_col": 3, "key_cols": [0], "max_row": 500},
    "2. A2_CongViec": {"max_col": 9, "key_cols": [0]},
    "3. B1_KhoiLuong": {"max_col": 19, "key_cols": [0, 1]},
    "6. C1_VTVL": {"max_col": 12, "key_cols": [0]},
    "8. C3_NhuCau": {"max_col": 15, "key_cols": [0]},
    "9. D1_NhanLuc": {"max_col": 12, "key_cols": [0, 1]},
    "10. D2_PhuongAn": {"max_col": 14, "key_cols": [0]},
}
MAX_PAYLOAD_ROWS_PER_SHEET = 60000


class _JsonSheet:
    def __init__(self, rows: List[List[Any]], start_row: int):
        self._rows = rows
        self._start = start_row

    def iter_rows(self, min_row: int = 1, max_row: Optional[int] = None, max_col: Optional[int] = None,
                  values_only: bool = True):
        last = self._start + len(self._rows) - 1
        end = last if max_row is None else min(max_row, last)
        for idx in range(min_row, end + 1):
            i = idx - self._start
            row = list(self._rows[i]) if 0 <= i < len(self._rows) else []
            if max_col is not None:
                row = (row + [None] * max_col)[:max_col]
            yield tuple(row)


class _JsonWorkbook:
    def __init__(self, payload: Dict[str, Any]):
        sheets = payload.get("sheets")
        if not isinstance(sheets, dict):
            raise ValueError("Dữ liệu gửi lên không hợp lệ: thiếu 'sheets'.")
        self._sheets: Dict[str, _JsonSheet] = {}
        for name, s in sheets.items():
            if name not in SHEET_SPECS or not isinstance(s, dict):
                continue
            rows = s.get("rows") or []
            if not isinstance(rows, list) or len(rows) > MAX_PAYLOAD_ROWS_PER_SHEET:
                raise ValueError(f"Dữ liệu sheet '{name}' không hợp lệ hoặc quá lớn.")
            max_col = SHEET_SPECS[name]["max_col"]
            clean = []
            for r in rows:
                if not isinstance(r, list):
                    raise ValueError(f"Dữ liệu sheet '{name}' không hợp lệ.")
                clean.append([v if isinstance(v, (str, int, float, bool)) or v is None else str(v) for v in r[:max_col]])
            self._sheets[name] = _JsonSheet(clean, int(s.get("start_row") or 1))
        names = payload.get("sheet_names")
        self.sheetnames = [str(n) for n in names] if isinstance(names, list) else list(self._sheets.keys())
        # Sheet có trong file nhưng không gửi kèm -> coi như rỗng
        self.sheetnames = [n for n in self.sheetnames if n in self._sheets or n not in SHEET_SPECS]

    def __getitem__(self, name: str) -> _JsonSheet:
        return self._sheets[name]

    def close(self) -> None:
        pass


def load_vtvl_workbook(file_path: str, sheets_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Đọc toàn bộ dữ liệu cốt lõi phục vụ rà soát chuyên môn giờ làm việc và biên chế.
    - file_path: đường dẫn file .xlsx; hoặc chỉ là tên file khi truyền sheets_payload.
    - sheets_payload: dữ liệu sheet đã trích sẵn từ trình duyệt (xem SHEET_SPECS).
    """
    path = Path(file_path)
    if sheets_payload is not None:
        wb = _JsonWorkbook(sheets_payload)
    else:
        if not path.exists():
            raise FileNotFoundError(f"Không tìm thấy file: {file_path}")
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    sheet_names = wb.sheetnames

    # 1. Đọc C1_VTVL
    c1_map: Dict[str, Dict[str, Any]] = {}
    if "6. C1_VTVL" in sheet_names:
        ws = wb["6. C1_VTVL"]
        empty_streak = 0
        for row_idx, r in enumerate(ws.iter_rows(min_row=3, max_col=12, values_only=True), 3):
            ma_vtvl = _to_str(r[0] if len(r) > 0 else None)
            if not ma_vtvl:
                empty_streak += 1
                if empty_streak > MAX_EMPTY_STREAK:
                    break
                continue
            empty_streak = 0
            ten_vtvl = _to_str(r[1] if len(r) > 1 else None)
            loai_nl = _to_str(r[2] if len(r) > 2 else None)
            quyet_dinh = _to_str(r[3] if len(r) > 3 else None)
            gio_chuan = _to_float(r[4] if len(r) > 4 else None, STANDARD_HOURS)
            trang_thai = _to_str(r[6] if len(r) > 6 else None)
            gio_rieng = _to_opt_float(r[7] if len(r) > 7 else None)
            che_do = _to_str(r[9] if len(r) > 9 else None)

            # Ban/bộ phận và cấp chức danh được gán sau khi biết khối đơn vị (bước 1c)
            dept_code = dept_name = role_group = suggested_method = ""

            c1_map[ma_vtvl] = {
                "row": row_idx,
                "ma_vtvl": ma_vtvl,
                "ten_vtvl": ten_vtvl,
                "loai_nhan_luc": loai_nl,
                "quyet_dinh": quyet_dinh,
                "gio_chuan": gio_chuan if gio_chuan > 0 else STANDARD_HOURS,
                "trang_thai": trang_thai,
                "gio_rieng": gio_rieng,
                "che_do": che_do,
                "dept_code": dept_code,
                "dept_name": dept_name,
                "role_group": role_group,
                "suggested_method": suggested_method,
            }

    # 1b. Đọc tên cơ quan tại biểu A1 (cột C "Cơ quan") để nhận diện đơn vị theo QĐ 2398/QĐ-UBND
    co_quan_counts: Dict[str, int] = {}
    if "1. A1_NhiemVu" in sheet_names:
        ws = wb["1. A1_NhiemVu"]
        empty_streak = 0
        for r in ws.iter_rows(min_row=3, max_row=500, max_col=3, values_only=True):
            ma_nv = _to_str(r[0] if len(r) > 0 else None)
            if not ma_nv:
                empty_streak += 1
                if empty_streak > MAX_EMPTY_STREAK:
                    break
                continue
            empty_streak = 0
            co_quan = _to_str(r[2] if len(r) > 2 else None)
            if co_quan:
                co_quan_counts[co_quan] = co_quan_counts.get(co_quan, 0) + 1
    co_quan_a1 = max(co_quan_counts, key=co_quan_counts.get) if co_quan_counts else ""

    # 1c. Xác định khối đơn vị (Đảng / chính quyền - sự nghiệp) rồi nhận diện Ban/bộ phận, cấp chức danh
    org_type = detect_org_type(co_quan_a1, list(c1_map.keys()))
    for code_c1, c1 in c1_map.items():
        c1["dept_code"], c1["dept_name"] = parse_department(code_c1, c1["ten_vtvl"], org_type)
        c1["role_group"], c1["suggested_method"] = classify_role_level(code_c1, c1["ten_vtvl"], org_type)

    # 2. Đọc A2_CongViec
    a2_map: Dict[str, Dict[str, Any]] = {}
    if "2. A2_CongViec" in sheet_names:
        ws = wb["2. A2_CongViec"]
        empty_streak = 0
        for row_idx, r in enumerate(ws.iter_rows(min_row=3, max_col=9, values_only=True), 3):
            ma_cv = _to_str(r[0] if len(r) > 0 else None)
            if not ma_cv:
                empty_streak += 1
                if empty_streak > MAX_EMPTY_STREAK:
                    break
                continue
            empty_streak = 0
            a2_map[ma_cv] = {
                "row": row_idx,
                "ma_cv": ma_cv,
                "ma_nv": _to_str(r[1] if len(r) > 1 else None),
                "ma_vtvl": _to_str(r[2] if len(r) > 2 else None),
                "ten_cv": _to_str(r[3] if len(r) > 3 else None),
                "san_pham": _to_str(r[4] if len(r) > 4 else None),
                "don_vi_tinh": _to_str(r[5] if len(r) > 5 else None),
                "can_cu": _to_str(r[7] if len(r) > 7 else None),
            }

    # 3. Đọc B1_KhoiLuong
    b1_rows: List[Dict[str, Any]] = []
    b1_by_vtvl: Dict[str, List[Dict[str, Any]]] = {}
    if "3. B1_KhoiLuong" in sheet_names:
        ws = wb["3. B1_KhoiLuong"]
        empty_streak = 0
        for row_idx, r in enumerate(ws.iter_rows(min_row=3, max_col=19, values_only=True), 3):
            ma_cv = _to_str(r[0] if len(r) > 0 else None)
            ma_vtvl = _to_str(r[1] if len(r) > 1 else None)
            if not ma_cv and not ma_vtvl:
                empty_streak += 1
                if empty_streak > MAX_EMPTY_STREAK:
                    break
                continue
            empty_streak = 0
            if not ma_vtvl and ma_cv in a2_map:
                ma_vtvl = a2_map[ma_cv]["ma_vtvl"]

            so_sp = _to_float(r[2] if len(r) > 2 else None, 0.0)
            phut_do = _to_opt_float(r[3] if len(r) > 3 else None)
            gio_bo_sung = _to_float(r[4] if len(r) > 4 else None, 0.0)
            gio_sp = _to_opt_float(r[5] if len(r) > 5 else None)
            gio_tong = _to_opt_float(r[6] if len(r) > 6 else None)
            nguon_sl = _to_str(r[7] if len(r) > 7 else None)
            nguon_tg = _to_str(r[8] if len(r) > 8 else None)
            trang_thai_tg = _to_str(r[9] if len(r) > 9 else None)
            ky = _to_str(r[10] if len(r) > 10 else None)
            ma_sp_dm = _to_str(r[11] if len(r) > 11 else None)
            nhom_sp = _to_str(r[12] if len(r) > 12 else None)
            phut_chuan = _to_opt_float(r[13] if len(r) > 13 else None)
            phut_dung = _to_opt_float(r[15] if len(r) > 15 else None)

            if phut_dung is None:
                phut_dung = phut_do if phut_do is not None else (phut_chuan or 0.0)
            if gio_sp is None:
                gio_sp = (so_sp * (phut_dung or 0.0)) / 60.0
            if gio_tong is None:
                gio_tong = gio_sp + gio_bo_sung

            a2_info = a2_map.get(ma_cv, {})
            item = {
                "row": row_idx,
                "ma_cv": ma_cv,
                "ma_vtvl": ma_vtvl,
                "ten_cv": a2_info.get("ten_cv", ""),
                "san_pham": a2_info.get("san_pham", ""),
                "don_vi_tinh": a2_info.get("don_vi_tinh", ""),
                "so_sp": so_sp,
                "phut_do": phut_do,
                "gio_bo_sung": gio_bo_sung,
                "gio_sp": gio_sp,
                "gio_tong": gio_tong,
                "nguon_sl": nguon_sl,
                "nguon_tg": nguon_tg,
                "trang_thai_tg": trang_thai_tg,
                "ky": ky,
                "ma_sp_dm": ma_sp_dm,
                "nhom_sp": nhom_sp,
                "phut_chuan": phut_chuan,
                "phut_dung": phut_dung,
            }
            b1_rows.append(item)
            b1_by_vtvl.setdefault(ma_vtvl, []).append(item)

    # 4. Đọc C3_NhuCau
    c3_map: Dict[str, Dict[str, Any]] = {}
    if "8. C3_NhuCau" in sheet_names:
        ws = wb["8. C3_NhuCau"]
        empty_streak = 0
        for row_idx, r in enumerate(ws.iter_rows(min_row=3, max_col=15, values_only=True), 3):
            ma_vtvl = _to_str(r[0] if len(r) > 0 else None)
            if not ma_vtvl:
                empty_streak += 1
                if empty_streak > MAX_EMPTY_STREAK:
                    break
                continue
            empty_streak = 0
            phuong_phap = _to_str(r[1] if len(r) > 1 else None)
            gio_b1 = _to_opt_float(r[2] if len(r) > 2 else None)
            gio_b2 = _to_float(r[3] if len(r) > 3 else None, 0.0)
            gio_rong = _to_opt_float(r[4] if len(r) > 4 else None)
            gio_pp2_c1 = _to_float(r[5] if len(r) > 5 else None, STANDARD_HOURS)
            nguoi_pp2_col_g = _to_opt_float(r[6] if len(r) > 6 else None)
            nguoi_pp1_col_h = _to_opt_float(r[7] if len(r) > 7 else None)
            nguoi_pp3_col_i = _to_opt_float(r[8] if len(r) > 8 else None)
            nguoi_bo_tri_col_j = _to_opt_float(r[9] if len(r) > 9 else None)
            giai_trinh_k = _to_str(r[10] if len(r) > 10 else None)
            trang_thai_l = _to_str(r[11] if len(r) > 11 else None)
            canh_bao_m = _to_str(r[12] if len(r) > 12 else None)

            sum_b1 = sum(x["gio_tong"] for x in b1_by_vtvl.get(ma_vtvl, []))
            if gio_b1 is None:
                gio_b1 = sum_b1
            if gio_rong is None:
                gio_rong = gio_b1 + gio_b2
            quychuan = gio_pp2_c1 if gio_pp2_c1 > 0 else STANDARD_HOURS
            fte_theo_gio = gio_rong / quychuan

            c3_map[ma_vtvl] = {
                "row": row_idx,
                "ma_vtvl": ma_vtvl,
                "phuong_phap": phuong_phap,
                "gio_b1": gio_b1,
                "gio_b1_tinh_lai": sum_b1,
                "gio_b2": gio_b2,
                "gio_rong": gio_rong,
                "gio_chuan": quychuan,
                "fte_theo_gio": fte_theo_gio,
                "nguoi_pp2_col_g": nguoi_pp2_col_g,
                "nguoi_pp1_col_h": nguoi_pp1_col_h,
                "nguoi_pp3_col_i": nguoi_pp3_col_i,
                "nguoi_bo_tri_col_j": nguoi_bo_tri_col_j if nguoi_bo_tri_col_j is not None else 0.0,
                "giai_trinh": giai_trinh_k,
                "trang_thai": trang_thai_l,
                "canh_bao": canh_bao_m,
            }

    # 5. Đọc D1_NhanLuc
    d1_rows: List[Dict[str, Any]] = []
    d1_by_vtvl: Dict[str, List[Dict[str, Any]]] = {}
    if "9. D1_NhanLuc" in sheet_names:
        ws = wb["9. D1_NhanLuc"]
        empty_streak = 0
        for row_idx, r in enumerate(ws.iter_rows(min_row=3, max_col=12, values_only=True), 3):
            ma_nl = _to_str(r[0] if len(r) > 0 else None)
            ma_vtvl = _to_str(r[1] if len(r) > 1 else None)
            if not ma_nl and not ma_vtvl:
                empty_streak += 1
                if empty_streak > MAX_EMPTY_STREAK:
                    break
                continue
            empty_streak = 0
            item = {
                "row": row_idx,
                "ma_nl": ma_nl,
                "ma_vtvl": ma_vtvl,
                "loai_nl": _to_str(r[2] if len(r) > 2 else None),
                "gio_quy_doi": _to_float(r[3] if len(r) > 3 else None, STANDARD_HOURS),
                "gio_danh_cho_vtvl": _to_float(r[4] if len(r) > 4 else None, STANDARD_HOURS),
                "gio_viec_khac": _to_float(r[5] if len(r) > 5 else None, 0.0),
                "noi_tinh_bc": _to_str(r[6] if len(r) > 6 else None),
                "nguon": _to_str(r[7] if len(r) > 7 else None),
                "trang_thai": _to_str(r[8] if len(r) > 8 else None),
            }
            d1_rows.append(item)
            d1_by_vtvl.setdefault(ma_vtvl, []).append(item)

    # 6. Đọc D2_PhuongAn
    d2_by_vtvl: Dict[str, List[Dict[str, Any]]] = {}
    if "10. D2_PhuongAn" in sheet_names:
        ws = wb["10. D2_PhuongAn"]
        empty_streak = 0
        for row_idx, r in enumerate(ws.iter_rows(min_row=3, max_col=14, values_only=True), 3):
            ma_vtvl = _to_str(r[0] if len(r) > 0 else None)
            if not ma_vtvl:
                empty_streak += 1
                if empty_streak > MAX_EMPTY_STREAK:
                    break
                continue
            empty_streak = 0
            nam_val = r[1] if len(r) > 1 else None
            try:
                nam = int(float(nam_val)) if nam_val is not None else None
            except (ValueError, TypeError):
                nam = None
            item = {
                "row": row_idx,
                "ma_vtvl": ma_vtvl,
                "nam": nam,
                "can_bo_tri_col_c": _to_opt_float(r[2] if len(r) > 2 else None),
                "co_the_bo_tri_col_d": _to_opt_float(r[3] if len(r) > 3 else None),
                "bien_che_giao_col_e": _to_opt_float(r[4] if len(r) > 4 else None),
                "dieu_chuyen_col_f": _to_opt_float(r[5] if len(r) > 5 else None),
                "de_nghi_dieu_chinh_col_g": _to_opt_float(r[6] if len(r) > 6 else None),
                "giai_trinh_col_h": _to_str(r[7] if len(r) > 7 else None),
                "trang_thai_col_i": _to_str(r[8] if len(r) > 8 else None),
                "canh_bao_col_j": _to_str(r[9] if len(r) > 9 else None),
                "pp2_tham_khao_col_k": _to_opt_float(r[10] if len(r) > 10 else None),
                "c3_tham_khao_col_l": _to_opt_float(r[11] if len(r) > 11 else None),
            }
            d2_by_vtvl.setdefault(ma_vtvl, []).append(item)

    wb.close()

    all_vtvl_codes = list(c1_map.keys())
    for k in c3_map.keys():
        if k not in c1_map:
            all_vtvl_codes.append(k)

    positions: List[Dict[str, Any]] = []
    for code in all_vtvl_codes:
        c1 = c1_map.get(code, {})
        c3 = c3_map.get(code, {})
        d1_list = d1_by_vtvl.get(code, [])
        d2_list = d2_by_vtvl.get(code, [])
        b1_list = b1_by_vtvl.get(code, [])

        ten_vtvl = c1.get("ten_vtvl") or "Chưa khai báo tại C1"
        dept_code, dept_name = parse_department(code, ten_vtvl, org_type)
        role_group, suggested_method = classify_role_level(code, ten_vtvl, org_type)

        gio_chuan = c3.get("gio_chuan") or c1.get("gio_chuan") or STANDARD_HOURS
        gio_rong = c3.get("gio_rong")
        if gio_rong is None:
            gio_rong = sum(x["gio_tong"] for x in b1_list)

        fte_gio = gio_rong / gio_chuan if gio_chuan > 0 else 0.0
        n_d1 = len(d1_list)
        gio_d1_cung_cap = sum(x["gio_danh_cho_vtvl"] for x in d1_list)
        n_c3 = c3.get("nguoi_bo_tri_col_j", 0.0) or 0.0

        positions.append({
            "ma_vtvl": code,
            "ten_vtvl": ten_vtvl,
            "loai_nhan_luc": c1.get("loai_nhan_luc", ""),
            "dept_code": dept_code,
            "dept_name": dept_name,
            "role_group": role_group,
            "suggested_method": suggested_method,
            "phuong_phap_c3": c3.get("phuong_phap", ""),
            "gio_chuan": gio_chuan,
            "gio_b1": c3.get("gio_b1", gio_rong),
            "gio_b2": c3.get("gio_b2", 0.0),
            "gio_rong": gio_rong,
            "fte_theo_gio": fte_gio,
            "n_d1": n_d1,
            "gio_d1_cung_cap": gio_d1_cung_cap,
            "n_c3": n_c3,
            "nguoi_pp2_col_g": c3.get("nguoi_pp2_col_g"),
            "nguoi_pp1_col_h": c3.get("nguoi_pp1_col_h"),
            "nguoi_pp3_col_i": c3.get("nguoi_pp3_col_i"),
            "giai_trinh_c3": c3.get("giai_trinh", ""),
            "c1_row": c1.get("row"),
            "c3_row": c3.get("row"),
            "b1_tasks": b1_list,
            "d1_staff": d1_list,
            "d2_plans": d2_list,
        })

    return {
        "file_name": path.name,
        "file_path": str(path),
        "sheet_names": sheet_names,
        "co_quan_a1": co_quan_a1,
        "org_type": org_type,
        "standard_hours": STANDARD_HOURS,
        "positions": positions,
        "b1_rows": b1_rows,
        "d1_rows": d1_rows,
        "a2_map": a2_map,
    }
