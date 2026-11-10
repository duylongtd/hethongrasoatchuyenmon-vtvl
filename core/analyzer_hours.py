# -*- coding: utf-8 -*-
"""
Module 1: Rà soát bất thường về giờ làm việc của VTVL so với chuẩn 1.904 giờ/người/năm.
Đã cập nhật theo yêu cầu Lãnh đạo:
- Vị trí kiêm nhiệm (tên vị trí có 'kiêm nhiệm', hoặc giải trình C3 ghi 'kiêm nhiệm', hoặc bố trí 0 người để kiêm nhiệm)
  được gắn CẢNH BÁO (vàng) để rà soát; không áp các ngưỡng giờ/người vì không có người bố trí riêng.
"""

import re
from typing import Any, Dict, List


def is_concurrent_position(pos: Dict[str, Any]) -> bool:
    """
    Xác định vị trí kiêm nhiệm:
    - Tên VTVL có từ 'kiêm nhiệm'
    - Giải trình C3 (cột K) có ghi 'kiêm nhiệm'
    - Vị trí có n_c3 == 0 (không bố trí người riêng, thực hiện kiêm nhiệm)
    """
    ten = (pos.get("ten_vtvl") or "").lower()
    giai_trinh = (pos.get("giai_trinh_c3") or "").lower()
    n_c3 = pos.get("n_c3") or 0.0
    if "kiêm nhiệm" in ten or "kiêm nhiệm" in giai_trinh or n_c3 == 0:
        return True
    return False


def analyze_hours_anomalies(data: Dict[str, Any]) -> Dict[str, Any]:
    positions: List[Dict[str, Any]] = data["positions"]
    std_hours: float = data.get("standard_hours", 1904.0)

    position_hour_evals: List[Dict[str, Any]] = []
    findings: List[Dict[str, Any]] = []
    b1_anomalies: List[Dict[str, Any]] = []

    for pos in positions:
        code = pos["ma_vtvl"]
        name = pos["ten_vtvl"]
        dept_name = pos["dept_name"]
        c3_row = pos["c3_row"] or "?"
        gio_rong = pos["gio_rong"]
        gio_chuan = pos["gio_chuan"] or std_hours
        fte = pos["fte_theo_gio"]
        n_d1 = pos["n_d1"]
        n_c3 = pos["n_c3"]
        b1_tasks = pos["b1_tasks"]
        kiem_nhiem = is_concurrent_position(pos)

        gio_tren_nguoi_d1 = (gio_rong / n_d1) if n_d1 > 0 else None
        gio_tren_nguoi_c3 = (gio_rong / n_c3) if n_c3 > 0 else None
        ty_le_d1_pct = (gio_tren_nguoi_d1 / gio_chuan * 100.0) if gio_tren_nguoi_d1 is not None else None
        ty_le_c3_pct = (gio_tren_nguoi_c3 / gio_chuan * 100.0) if gio_tren_nguoi_c3 is not None else None

        pos_flags: List[str] = []
        severity = "HOP_LY"

        # Quét B1 để phục vụ bảng phụ B1 và kiểm tra phút lẻ
        decimal_b1_rows = []
        target_hour_texts = set()
        mismatch_text_rows = []
        high_min_rows = []

        for t in b1_tasks:
            r_idx = t["row"]
            phut_do = t["phut_do"]
            nguon_tg = t["nguon_tg"] or ""
            gio_tong_t = t["gio_tong"] or 0.0

            m_target = re.search(r"tổng mục tiêu\s*([\d.,]+)\s*giờ/năm", nguon_tg, re.IGNORECASE)
            if m_target:
                target_hour_texts.add(m_target.group(1))

            if phut_do is not None:
                if abs(phut_do - round(phut_do, 1)) > 1e-4 or (abs(phut_do - round(phut_do)) > 1e-4 and phut_do > 10):
                    decimal_b1_rows.append(f"D{r_idx}={phut_do}")

                m_decl = re.search(r"Thời gian kê khai cho 01 sản phẩm:\s*([\d.,]+)\s*phút", nguon_tg)
                if m_decl:
                    decl_val = float(m_decl.group(1).replace(",", "."))
                    if abs(phut_do - decl_val) > 1e-4:
                        mismatch_text_rows.append(f"Dòng {r_idx}: Cột D={phut_do} phút != Thuyết minh cột I={decl_val:g} phút")

                if phut_do >= 480 or gio_tong_t >= 1000:
                    high_min_rows.append(t)
                    b1_anomalies.append({
                        "row": r_idx,
                        "ma_vtvl": code,
                        "ten_vtvl": name,
                        "dept_name": dept_name,
                        "ma_cv": t["ma_cv"],
                        "ten_cv": t["ten_cv"],
                        "so_sp": t["so_sp"],
                        "phut_do": phut_do,
                        "gio_tong": gio_tong_t,
                        "issue_type": "Thời gian/SP hoặc Tổng giờ CV rất lớn",
                        "detail": (
                            f"SL={t['so_sp']:g} SP/năm × {phut_do:g} phút/SP = {gio_tong_t:,.1f} giờ/năm (Thiếu mã SP chuẩn cột L)"
                            if not t["ma_sp_dm"]
                            else f"SL={t['so_sp']:g} × {phut_do:g} phút = {gio_tong_t:,.1f}h"
                        ),
                    })

        # Vị trí kiêm nhiệm: gắn CẢNH BÁO vàng (không áp ngưỡng giờ/người)
        if kiem_nhiem:
            severity = "CANH_BAO"
            if "kiêm nhiệm" in (name or "").lower():
                ly_do = "tên vị trí ghi 'kiêm nhiệm'"
            elif "kiêm nhiệm" in (pos.get("giai_trinh_c3") or "").lower():
                ly_do = f"giải trình C3 (cột K) ghi 'kiêm nhiệm'"
            else:
                ly_do = "C3 bố trí 0 người riêng (thực hiện kiêm nhiệm)"
            pos_flags.append(f"Vị trí kiêm nhiệm - cần rà soát ({ly_do})")
            findings.append({
                "severity": "CANH_BAO",
                "category": "Vị trí kiêm nhiệm (cần rà soát phân công, giờ làm việc)",
                "dept_name": dept_name,
                "ma_vtvl": code,
                "ten_vtvl": name,
                "cell_ref": f"8. C3_NhuCau!C{c3_row}, J{c3_row}, K{c3_row}",
                "current_value": f"Giờ ròng = {gio_rong:,.2f}h ({fte:.2f} định mức) | D1 = {n_d1} người | C3 = {n_c3:g} người",
                "benchmark": "Vị trí kiêm nhiệm phải xác định rõ người kiêm nhiệm và cộng giờ vào vị trí nhận kiêm nhiệm",
                "detail": (
                    f"Vị trí '{name}' được xác định là kiêm nhiệm vì {ly_do}. "
                    f"Khối lượng {gio_rong:,.1f} giờ/năm cần được phân giao cho nhân sự cụ thể tại D1."
                ),
                "recommendation": "Ghi rõ nhân sự kiêm nhiệm tại D1 và kiểm tra tổng giờ của người kiêm nhiệm không vượt định mức 1.904h.",
            })

        if not kiem_nhiem:
            # 1. Kiểm tra giờ quá thấp (< 50% chuẩn = 952h)
            if gio_rong < 0.5 * gio_chuan:
                severity = "CANH_BAO"
                pos_flags.append(f"Giờ quá thấp ({gio_rong:,.1f}h = {fte*100:.1f}% định mức 1 người)")
                findings.append({
                    "severity": severity,
                    "category": "Giờ làm việc quá thấp (< 50% chuẩn 1.904h)",
                    "dept_name": dept_name,
                    "ma_vtvl": code,
                    "ten_vtvl": name,
                    "cell_ref": f"8. C3_NhuCau!C{c3_row}, E{c3_row}",
                    "current_value": f"{gio_rong:,.2f} giờ/năm ({fte:.2f} định mức 1.904h)",
                    "benchmark": f">= {0.5*gio_chuan:,.0f} giờ/năm (tối thiểu 0.5 định mức) hoặc chuẩn {gio_chuan:,.0f}h/người",
                    "detail": (
                        f"Vị trí '{name}' chỉ phát sinh {gio_rong:,.2f} giờ/năm (bằng {fte*100:.1f}% của 1.904h), "
                        f"đang bố trí {n_c3:.0f} người tại C3 (mỗi người chỉ đạt {ty_le_c3_pct:.1f}% định mức giờ)."
                    ),
                    "recommendation": "Rà soát lại biểu B1 xem có kê khai thiếu đầu việc thường xuyên của vị trí này không.",
                })

            # 2. Kiểm tra giờ bình quân / người hiện có (D1) quá cao (> 120% của 1.904h = 2.285h)
            if gio_tren_nguoi_d1 is not None and gio_tren_nguoi_d1 > 1.20 * gio_chuan:
                severity = "NGHIEM_TRONG"
                pos_flags.append(f"Quá tải so với nhân sự D1 ({gio_tren_nguoi_d1:,.1f}h/người = {ty_le_d1_pct:.1f}%)")
                findings.append({
                    "severity": "NGHIEM_TRONG",
                    "category": "Giờ làm việc quá cao so với nhân sự hiện có (D1)",
                    "dept_name": dept_name,
                    "ma_vtvl": code,
                    "ten_vtvl": name,
                    "cell_ref": f"8. C3_NhuCau!E{c3_row} & 9. D1_NhanLuc",
                    "current_value": f"{gio_rong:,.2f} giờ / {n_d1} người D1 = {gio_tren_nguoi_d1:,.1f} giờ/người ({ty_le_d1_pct:.1f}%)",
                    "benchmark": f"1.904 giờ/người/năm (ngưỡng tối đa 120% = {1.2*gio_chuan:,.0f}h)",
                    "detail": (
                        f"Tổng giờ ròng của vị trí là {gio_rong:,.2f}h (tương đương {fte:.2f} người), nhưng thực tế tại biểu D1 "
                        f"chỉ có {n_d1} người đang đảm nhiệm -> bình quân {gio_tren_nguoi_d1:,.1f} giờ/người/năm ({ty_le_d1_pct:.1f}% định mức 1.904h)."
                    ),
                    "recommendation": "Kiểm tra xem khối lượng tại B1 có bị kê cao để xin thêm biên chế ở C3 hay nhân sự thực tế đang bị quá tải.",
                })
            elif gio_tren_nguoi_d1 is not None and gio_tren_nguoi_d1 < 0.70 * gio_chuan and gio_rong >= 0.5 * gio_chuan:
                if severity == "HOP_LY":
                    severity = "CANH_BAO"
                pos_flags.append(f"Thấp tải so với nhân sự D1 ({gio_tren_nguoi_d1:,.1f}h/người = {ty_le_d1_pct:.1f}%)")
                findings.append({
                    "severity": "CANH_BAO",
                    "category": "Giờ làm việc bình quân thấp so với nhân sự hiện có (D1)",
                    "dept_name": dept_name,
                    "ma_vtvl": code,
                    "ten_vtvl": name,
                    "cell_ref": f"8. C3_NhuCau!E{c3_row} & 9. D1_NhanLuc",
                    "current_value": f"{gio_rong:,.2f} giờ / {n_d1} người D1 = {gio_tren_nguoi_d1:,.1f} giờ/người ({ty_le_d1_pct:.1f}%)",
                    "benchmark": "1.904 giờ/người/năm (ngưỡng 70% - 115%)",
                    "detail": (
                        f"Biểu D1 hiện có {n_d1} người nhưng tổng giờ B1/C3 chỉ đạt {gio_rong:,.2f}h "
                        f"(bình quân {gio_tren_nguoi_d1:,.1f}h/người = {ty_le_d1_pct:.1f}% chuẩn 1.904h)."
                    ),
                    "recommendation": "Rà soát lại việc phân giao nhiệm vụ cho nhân sự hiện có tại D1 hoặc điều chuyển bớt sang vị trí thiếu người.",
                })

            # 3. Kiểm tra dấu hiệu "Tính ngược" (Reverse-engineering) tại B1 & C3
            nearest_mult = round(fte)
            diff_mult_pct = abs(fte - nearest_mult) / nearest_mult * 100.0 if nearest_mult > 0 else 100.0

            if decimal_b1_rows or target_hour_texts or mismatch_text_rows or (nearest_mult >= 1 and diff_mult_pct <= 2.0):
                if severity == "HOP_LY":
                    severity = "CANH_BAO"
                reasons = []
                if nearest_mult >= 1 and diff_mult_pct <= 2.0:
                    reasons.append(
                        f"Tổng giờ {gio_rong:,.2f}h xấp xỉ {nearest_mult} × 1.904h = {nearest_mult*gio_chuan:,.0f}h (lệch chỉ {diff_mult_pct:.2f}%)"
                    )
                if target_hour_texts:
                    reasons.append(
                        f"Cột I biểu B1 ghi rõ phân bổ ngược theo 'tổng mục tiêu {', '.join(sorted(target_hour_texts))} giờ/năm'"
                    )
                if decimal_b1_rows:
                    sample_dec = ", ".join(decimal_b1_rows[:4])
                    if len(decimal_b1_rows) > 4:
                        sample_dec += f" (... +{len(decimal_b1_rows)-4} dòng)"
                    reasons.append(f"Số phút/SP tại B1 bị chia lẻ thập phân bất thường ({sample_dec})")
                if mismatch_text_rows:
                    reasons.append("; ".join(mismatch_text_rows[:2]))

                pos_flags.append("Nghi vấn 'Tính ngược' giờ B1")
                findings.append({
                    "severity": "CANH_BAO",
                    "category": "Dấu hiệu 'Tính ngược' (Goal-Seek) thời gian tại B1 để khớp giờ mục tiêu",
                    "dept_name": dept_name,
                    "ma_vtvl": code,
                    "ten_vtvl": name,
                    "cell_ref": f"3. B1_KhoiLuong (các dòng của {code}) & 8. C3_NhuCau!C{c3_row}",
                    "current_value": f"Tổng giờ = {gio_rong:,.3f}h ({fte:.4f} định mức)",
                    "benchmark": "Phút/SP tại B1 phải đo đếm thực tế hoặc tra DM_SAN_PHAM (số nguyên/chuẩn), không chia ngược từ tổng giờ mục tiêu",
                    "detail": " | ".join(reasons),
                    "recommendation": (
                        "Yêu cầu đơn vị áp dụng đúng định mức thời gian chuẩn tại 11. DM_SAN_PHAM "
                        "hoặc kê khai số phút thực tế chẵn, không nhân hệ số lẻ để ép tổng giờ."
                    ),
                })

        position_hour_evals.append({
            "ma_vtvl": code,
            "ten_vtvl": name,
            "dept_code": pos["dept_code"],
            "dept_name": dept_name,
            "phuong_phap": pos["phuong_phap_c3"],
            "is_kiem_nhiem": kiem_nhiem,
            "gio_rong": gio_rong,
            "gio_chuan": gio_chuan,
            "fte_theo_gio": fte,
            "n_d1": n_d1,
            "n_c3": n_c3,
            "gio_tren_nguoi_d1": gio_tren_nguoi_d1,
            "gio_tren_nguoi_c3": gio_tren_nguoi_c3,
            "ty_le_d1_pct": ty_le_d1_pct,
            "ty_le_c3_pct": ty_le_c3_pct,
            "so_cong_viec_b1": len(b1_tasks),
            "so_dong_phut_le": len(decimal_b1_rows),
            "so_cv_gio_lon": len(high_min_rows),
            "severity": severity,
            "flags": pos_flags,
        })

    return {
        "position_hour_evals": position_hour_evals,
        "findings": findings,
        "b1_anomalies": b1_anomalies,
    }
