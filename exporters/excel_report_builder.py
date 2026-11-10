# -*- coding: utf-8 -*-
"""
Bộ xuất báo cáo Excel thẩm định chuyên môn giờ làm việc & bố trí nhân sự VTVL.
"""

from pathlib import Path
from typing import Any, Dict
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


HEADER_FILL = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
HEADER_FONT = Font(name="Times New Roman", size=11, bold=True, color="FFFFFF")
SUBHEADER_FILL = PatternFill(start_color="DBEAFE", end_color="DBEAFE", fill_type="solid")
TITLE_FONT = Font(name="Times New Roman", size=14, bold=True, color="1E3A8A")
BODY_FONT = Font(name="Times New Roman", size=11)
BOLD_FONT = Font(name="Times New Roman", size=11, bold=True)

CRIT_FILL = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
WARN_FILL = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
OK_FILL = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")

THIN_BORDER = Border(
    left=Side(style="thin", color="CBD5E1"),
    right=Side(style="thin", color="CBD5E1"),
    top=Side(style="thin", color="CBD5E1"),
    bottom=Side(style="thin", color="CBD5E1"),
)


def _style_header_row(ws, row_idx: int, num_cols: int):
    ws.row_dimensions[row_idx].height = 28
    for c in range(1, num_cols + 1):
        cell = ws.cell(row=row_idx, column=c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN_BORDER


def _auto_fit_columns(ws, max_width: int = 48):
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            lines = val_str.split("\n")
            for ln in lines:
                if len(ln) > max_len:
                    max_len = len(ln)
        ws.column_dimensions[col_letter].width = max(12, min(max_len + 4, max_width))


def build_excel_audit_report(audit_result: Dict[str, Any], output_path: str) -> str:
    wb = openpyxl.Workbook()
    # Xóa sheet mặc định
    wb.remove(wb.active)

    file_name = audit_result["file_name"]
    std_h = audit_result["standard_hours"]
    qd = audit_result.get("qd2398_info")
    if qd:
        so_lieu_str = ", ".join(f"{x['nhan']} = {x['gia_tri']}" for x in qd["so_lieu"])
        qd_str = f" | {qd['van_ban']} - Phụ lục {qd['phu_luc']} ({qd['ten']}): {so_lieu_str}"
    else:
        qd_str = " | Chưa nhận diện được tên đơn vị theo Phụ lục QĐ 2398/QĐ-UBND"

    # =========================================================================
    # SHEET 1: TỔNG HỢP CÂN ĐỐI GIỮA CÁC BAN / BỘ PHẬN
    # =========================================================================
    ws1 = wb.create_sheet("1_CanDoi_GiuaCacBan")
    ws1["A1"] = f"BÁO CÁO PHÂN TÍCH CÂN ĐỐI TẢI TRỌNG & NHÂN SỰ GIỮA CÁC BAN ({file_name})"
    ws1["A1"].font = TITLE_FONT
    ws1["A2"] = (
        f"Chuẩn định mức: {std_h:,.0f} giờ/người/năm | "
        f"Tổng giờ đơn vị: {audit_result['unit_totals']['total_hours']:,.1f}h "
        f"({audit_result['unit_totals']['total_fte']:.2f} định mức) | "
        f"Nhân sự hiện có D1: {audit_result['unit_totals']['total_d1']} người | "
        f"Đề xuất bố trí C3: {audit_result['unit_totals']['total_c3']:g} người"
        + qd_str
    )
    ws1["A2"].font = BOLD_FONT

    headers1 = [
        "Mã Ban",
        "Tên Ban / Bộ phận",
        "Tổng số VTVL",
        "Số VTVL bố trí 0 người",
        "Tổng giờ ròng (B1/C3)",
        "Tỷ trọng giờ (%)",
        "Định mức người theo giờ (Giờ/1904)",
        "Nhân sự hiện có (D1)",
        "Đề xuất bố trí (C3)",
        "Chênh lệch D1 so với Định mức giờ",
        "Giờ bình quân / người hiện có (D1)",
        "Hiệu suất tải D1 (%)",
        "Giờ bình quân / người đề xuất (C3)",
        "Hiệu suất tải C3 (%)",
        "Số giờ bị bỏ trống 0 người (Đẩy kiêm nhiệm)",
        "Đánh giá phân bổ liên Ban",
        "Chi tiết nhận xét chuyên môn",
    ]
    for col_idx, h in enumerate(headers1, 1):
        ws1.cell(row=4, column=col_idx, value=h)
    _style_header_row(ws1, 4, len(headers1))

    for idx, d in enumerate(audit_result["departments"], 5):
        row_vals = [
            d["dept_code"],
            d["dept_name"],
            d["so_vtvl"],
            d["so_vtvl_0_nguoi_c3"],
            round(d["tong_gio_rong"], 2),
            round(d["ty_trong_gio_pct"], 1),
            round(d["fte_theo_gio"], 2),
            d["n_d1"],
            d["n_c3"],
            round(d["thieu_hut_d1_so_voi_gio"], 2),
            round(d["gio_bq_d1"], 1),
            round(d["ty_le_tai_d1_pct"], 1),
            round(d["gio_bq_c3"], 1),
            round(d["ty_le_tai_c3_pct"], 1),
            round(d["gio_treo_0_nguoi"], 1),
            d["status_label"],
            "\n".join(d["notes"]),
        ]
        fill = CRIT_FILL if d["severity"] == "NGHIEM_TRONG" else (WARN_FILL if d["severity"] == "CANH_BAO" else OK_FILL)
        for c_i, val in enumerate(row_vals, 1):
            cell = ws1.cell(row=idx, column=c_i, value=val)
            cell.font = BODY_FONT
            cell.border = THIN_BORDER
            cell.alignment = Alignment(vertical="center", wrap_text=(c_i in (2, 16, 17)))
            if c_i in (12, 14, 15, 16):
                cell.fill = fill
    _auto_fit_columns(ws1)

    # =========================================================================
    # SHEET 2: BẤT THƯỜNG GIỜ LÀM VIỆC CỦA TỪNG VTVL SO VỚI 1.904 GIỜ
    # =========================================================================
    ws2 = wb.create_sheet("2_BatThuong_GioLamViec")
    ws2["A1"] = f"RÀ SOÁT BẤT THƯỜNG GIỜ LÀM VIỆC CỦA VTVL SO VỚI CHUẨN {std_h:,.0f} GIỜ/NGƯỜI ({file_name})"
    ws2["A1"].font = TITLE_FONT

    headers2 = [
        "STT",
        "Ban / Bộ phận",
        "Mã VTVL",
        "Tên Vị trí việc làm",
        "Phương pháp C3",
        "Tổng giờ ròng (B1/C3)",
        "Quy đổi người chuẩn (Giờ/1904)",
        "Nhân sự hiện có (D1)",
        "Đề xuất bố trí (C3)",
        "Giờ / người hiện có D1",
        "% Tải so với 1904h (theo D1)",
        "Giờ / người đề xuất C3",
        "% Tải so với 1904h (theo C3)",
        "Số đầu việc B1",
        "Số dòng B1 phút lẻ bất thường",
        "Mức độ",
        "Cảnh báo chuyên môn về Giờ làm việc",
    ]
    for col_idx, h in enumerate(headers2, 1):
        ws2.cell(row=3, column=col_idx, value=h)
    _style_header_row(ws2, 3, len(headers2))

    for i, p in enumerate(audit_result["position_hour_evals"], 1):
        r_idx = i + 3
        is_kn = p.get("is_kiem_nhiem", False)
        if is_kn:
            sev_label = "CẢNH BÁO (KIÊM NHIỆM)"
            flag_text = " | ".join(p["flags"]) if p["flags"] else "Vị trí kiêm nhiệm - cần rà soát"
        else:
            sev_label = "NGHIÊM TRỌNG" if p["severity"] == "NGHIEM_TRONG" else ("CẢNH BÁO" if p["severity"] == "CANH_BAO" else "BÌNH THƯỜNG")
            flag_text = " | ".join(p["flags"]) if p["flags"] else "Đạt ngưỡng chuẩn"
        fill = CRIT_FILL if p["severity"] == "NGHIEM_TRONG" else (WARN_FILL if p["severity"] == "CANH_BAO" else OK_FILL)
        row_vals = [
            i,
            p["dept_name"],
            p["ma_vtvl"],
            p["ten_vtvl"],
            p["phuong_phap"],
            round(p["gio_rong"], 2),
            round(p["fte_theo_gio"], 3),
            p["n_d1"],
            p["n_c3"],
            round(p["gio_tren_nguoi_d1"], 1) if p["gio_tren_nguoi_d1"] is not None else "0 người D1",
            round(p["ty_le_d1_pct"], 1) if p["ty_le_d1_pct"] is not None else "N/A",
            round(p["gio_tren_nguoi_c3"], 1) if p["gio_tren_nguoi_c3"] is not None else "0 người C3",
            round(p["ty_le_c3_pct"], 1) if p["ty_le_c3_pct"] is not None else "Kiêm nhiệm",
            p["so_cong_viec_b1"],
            p["so_dong_phut_le"],
            sev_label,
            flag_text,
        ]
        for c_i, val in enumerate(row_vals, 1):
            cell = ws2.cell(row=r_idx, column=c_i, value=val)
            cell.font = BODY_FONT
            cell.border = THIN_BORDER
            cell.alignment = Alignment(vertical="center", wrap_text=(c_i in (2, 4, 17)))
            if c_i in (6, 11, 13, 15, 16, 17) and p["severity"] != "HOP_LY":
                cell.fill = fill
    _auto_fit_columns(ws2)

    # =========================================================================
    # SHEET 3: ĐỐI CHIẾU ĐỀ XUẤT THÊM / BỚT NGƯỜI (GIỜ - D1 - C3 - D2)
    # =========================================================================
    ws3 = wb.create_sheet("3_BatHopLy_ThemBotNguoi")
    ws3["A1"] = f"RÀ SOÁT ĐỀ XUẤT BỐ TRÍ THÊM / BỚT NGƯỜI SO VỚI GIỜ LÀM VIỆC ({file_name})"
    ws3["A1"].font = TITLE_FONT
    ht = audit_result["headcount_totals"]
    ws3["A2"] = (
        f"Kiểm tra ngưỡng 10% tại C3: Tổng cột H (SH={ht['sum_col_h']:g}) + Tổng cột G (SG={ht['sum_col_g']:.2f}) = "
        f"{ht['sh_plus_sg']:.2f} người vs Tổng cột J (TJ={ht['sum_col_j']:g} người) -> Chênh lệch: {ht['diff_sh_sg_pct']:+.1f}%"
    )
    ws3["A2"].font = BOLD_FONT

    headers3 = [
        "STT",
        "Ban / Bộ phận",
        "Mã VTVL",
        "Tên Vị trí việc làm",
        "Phương pháp C3",
        "Phương pháp đúng gợi ý",
        "Tổng giờ ròng (h)",
        "Ngày làm việc quy đổi (Giờ/8h)",
        "Người quy đổi theo giờ (FTE)",
        "Nhân sự hiện có (D1)",
        "Đề xuất bố trí C3 (Cột J)",
        "Tăng/Giảm (C3 so với D1)",
        "Chênh lệch (C3 so với Giờ FTE)",
        "D2 Cột C (Cần bố trí)",
        "D2 Cột D (Có thể bố trí)",
        "Số người nêu trong thuyết minh D2",
        "Mức độ",
        "Phát hiện bất hợp lý về Thêm/Bớt người & Đối chiếu D1-C3-D2",
    ]
    for col_idx, h in enumerate(headers3, 1):
        ws3.cell(row=4, column=col_idx, value=h)
    _style_header_row(ws3, 4, len(headers3))

    for i, c in enumerate(audit_result["headcount_comparisons"], 1):
        r_idx = i + 4
        sev_label = "NGHIÊM TRỌNG" if c["severity"] == "NGHIEM_TRONG" else ("CẢNH BÁO" if c["severity"] == "CANH_BAO" else "HỢP LÝ")
        fill = CRIT_FILL if c["severity"] == "NGHIEM_TRONG" else (WARN_FILL if c["severity"] == "CANH_BAO" else OK_FILL)
        row_vals = [
            i,
            c["dept_name"],
            c["ma_vtvl"],
            c["ten_vtvl"],
            c["phuong_phap"],
            c["suggested_method"],
            round(c["gio_rong"], 2),
            round(c.get("ngay_lam_viec_quy_doi", c["gio_rong"] / 8.0), 1),
            round(c["fte_theo_gio"], 2),
            c["n_d1"],
            c["n_c3"],
            c["delta_c3_vs_d1"],
            round(c["delta_c3_vs_fte"], 2),
            c["n_d2_col_c"] if c["n_d2_col_c"] is not None else "",
            c["n_d2_col_d"] if c["n_d2_col_d"] is not None else "",
            ", ".join(str(x) for x in c["d2_narrative_nums"]),
            sev_label,
            "\n".join(c["issues"]) if c["issues"] else "Khớp hợp lý",
        ]
        for c_i, val in enumerate(row_vals, 1):
            cell = ws3.cell(row=r_idx, column=c_i, value=val)
            cell.font = BODY_FONT
            cell.border = THIN_BORDER
            cell.alignment = Alignment(vertical="center", wrap_text=(c_i in (2, 4, 18)))
            if c_i in (12, 13, 16, 17, 18) and c["severity"] != "HOP_LY":
                cell.fill = fill
    _auto_fit_columns(ws3)

    # =========================================================================
    # SHEET 4: DANH SÁCH CHI TIẾT CẢNH BÁO THEO Ô & KIẾN NGHỊ XỬ LÝ
    # =========================================================================
    ws4 = wb.create_sheet("4_ChiTiet_CanhBao_TheoO")
    ws4["A1"] = f"DANH MỤC CHI TIẾT CÁC PHÁT HIỆN BẤT THƯỜNG & KIẾN NGHỊ CHỈNH SỬA ({file_name})"
    ws4["A1"].font = TITLE_FONT

    headers4 = [
        "STT",
        "Mức độ",
        "Nhóm rà soát",
        "Loại bất thường",
        "Ban / Bộ phận",
        "Mã VTVL",
        "Tên Vị trí việc làm",
        "Vị trí Sheet & Ô",
        "Giá trị hiện tại trong biểu",
        "Chuẩn đối chiếu / Yêu cầu",
        "Phân tích chi tiết bất thường",
        "Kiến nghị hướng xử lý",
    ]
    for col_idx, h in enumerate(headers4, 1):
        ws4.cell(row=3, column=col_idx, value=h)
    _style_header_row(ws4, 3, len(headers4))

    for i, f in enumerate(audit_result["all_findings"], 1):
        r_idx = i + 3
        sev_label = "NGHIÊM TRỌNG" if f["severity"] == "NGHIEM_TRONG" else "CẢNH BÁO"
        fill = CRIT_FILL if f["severity"] == "NGHIEM_TRONG" else WARN_FILL
        row_vals = [
            i,
            sev_label,
            f["module"],
            f["category"],
            f["dept_name"],
            f["ma_vtvl"],
            f["ten_vtvl"],
            f["cell_ref"],
            f["current_value"],
            f["benchmark"],
            f["detail"],
            f["recommendation"],
        ]
        for c_i, val in enumerate(row_vals, 1):
            cell = ws4.cell(row=r_idx, column=c_i, value=val)
            cell.font = BODY_FONT
            cell.border = THIN_BORDER
            cell.alignment = Alignment(vertical="center", wrap_text=(c_i >= 4))
            if c_i in (2, 4):
                cell.fill = fill
    _auto_fit_columns(ws4)

    # =========================================================================
    # SHEET 5: CÁC CÔNG VIỆC TẠI B1 CÓ THỜI GIAN LỚN ĐỘT BIẾN
    # =========================================================================
    ws5 = wb.create_sheet("5_CongViec_B1_GioLon")
    ws5["A1"] = f"DANH SÁCH CÔNG VIỆC TẠI BIỂU B1 CÓ THỜI GIAN/SP (>=480 PHÚT) HOẶC TỔNG GIỜ (>=1000H) ({file_name})"
    ws5["A1"].font = TITLE_FONT

    headers5 = [
        "STT",
        "Dòng tại B1",
        "Ban / Bộ phận",
        "Mã VTVL",
        "Tên VTVL",
        "Mã Công việc",
        "Tên Công việc (từ A2)",
        "Số SP/năm (Cột C)",
        "Phút/SP kê khai (Cột D)",
        "Tổng giờ/năm (Cột G)",
        "Nhận xét",
    ]
    for col_idx, h in enumerate(headers5, 1):
        ws5.cell(row=3, column=col_idx, value=h)
    _style_header_row(ws5, 3, len(headers5))

    for i, b in enumerate(audit_result["b1_anomalies"], 1):
        r_idx = i + 3
        row_vals = [
            i,
            f"3. B1_KhoiLuong!D{b['row']}, G{b['row']}",
            b["dept_name"],
            b["ma_vtvl"],
            b["ten_vtvl"],
            b["ma_cv"],
            b["ten_cv"],
            b["so_sp"],
            round(b["phut_do"], 4) if b["phut_do"] is not None else "",
            round(b["gio_tong"], 2),
            b["detail"],
        ]
        for c_i, val in enumerate(row_vals, 1):
            cell = ws5.cell(row=r_idx, column=c_i, value=val)
            cell.font = BODY_FONT
            cell.border = THIN_BORDER
            cell.alignment = Alignment(vertical="center", wrap_text=(c_i in (5, 7, 11)))
            if c_i in (9, 10):
                cell.fill = WARN_FILL
    _auto_fit_columns(ws5)

    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(out_p))
    return str(out_p)
