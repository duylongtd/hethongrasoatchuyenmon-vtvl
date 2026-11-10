# -*- coding: utf-8 -*-
"""
Module 2: Rà soát các vị trí có đề xuất bố trí Thêm / Bớt người không hợp lý so với giờ làm việc
và đối chiếu liên biểu Giờ B1/C3 <-> Nhân lực hiện có D1 <-> Nhu cầu C3 <-> Phương án D2.
"""

import re
from typing import Any, Dict, List


def analyze_headcount_proposals(data: Dict[str, Any]) -> Dict[str, Any]:
    positions: List[Dict[str, Any]] = data["positions"]
    std_hours: float = data.get("standard_hours", 1904.0)

    comparisons: List[Dict[str, Any]] = []
    findings: List[Dict[str, Any]] = []

    # Tính tổng SH (cột H), SG (cột G), TJ (cột J) tại biểu C3
    sum_col_g = sum((p["nguoi_pp2_col_g"] or 0.0) for p in positions)
    sum_col_h = sum((p["nguoi_pp1_col_h"] or 0.0) for p in positions)
    sum_col_j = sum((p["n_c3"] or 0.0) for p in positions)
    sum_d1 = sum(p["n_d1"] for p in positions)
    sum_fte = sum(p["fte_theo_gio"] for p in positions)

    sh_plus_sg = sum_col_h + sum_col_g
    diff_sh_sg_pct = ((sh_plus_sg - sum_col_j) / sum_col_j * 100.0) if sum_col_j > 0 else 0.0

    c3_rows = [p["c3_row"] for p in positions if p.get("c3_row")]
    c3_range_ref = f"8. C3_NhuCau!G{min(c3_rows)}:J{max(c3_rows)}" if c3_rows else "8. C3_NhuCau (cột G, H, J)"

    # Kiểm tra ngưỡng 10% toàn biểu C3 (SH + SG so với TJ)
    if sum_col_j > 0 and abs(diff_sh_sg_pct) > 10.0:
        findings.append({
            "severity": "NGHIEM_TRONG",
            "category": "Vi phạm ngưỡng 10% tổng người tại biểu C3 (SH + SG so với Tổng cột J)",
            "dept_name": "Toàn đơn vị",
            "ma_vtvl": "TOÀN_ĐƠN_VỊ",
            "ten_vtvl": "Tổng hợp biểu 8. C3_NhuCau",
            "cell_ref": c3_range_ref,
            "current_value": f"SH ({sum_col_h:g}) + SG ({sum_col_g:.2f}) = {sh_plus_sg:.2f} người vs Cột J (TJ) = {sum_col_j:g} người (Lệch {diff_sh_sg_pct:+.1f}%)",
            "benchmark": f"|SH + SG - TJ| <= 10% × TJ (tức trong khoảng {0.9*sum_col_j:.1f} đến {1.1*sum_col_j:.1f} người)",
            "detail": (
                f"Tổng cột H (PP1 = {sum_col_h:g}) cộng tổng cột G (PP2 = {sum_col_g:.2f}) bằng {sh_plus_sg:.2f} người, "
                f"vượt {diff_sh_sg_pct:+.1f}% so với tổng người cần bố trí cột J ({sum_col_j:g} người). "
                "Nguyên nhân chính: Các vị trí chọn phương pháp PP2 và PP1+PP2 vẫn bị nhập số người vào cột H (Người PP1), làm nhân đôi số liệu."
            ),
            "recommendation": "Đối với các dòng áp dụng PP2 tại C3, để trống cột H (Người PP1); kiểm tra lại phương pháp định biên theo đúng chức danh.",
        })

    for pos in positions:
        code = pos["ma_vtvl"]
        name = pos["ten_vtvl"]
        dept_name = pos["dept_name"]
        c3_row = pos["c3_row"] or "?"
        phuong_phap = pos["phuong_phap_c3"]
        suggested_method = pos["suggested_method"]
        gio_rong = pos["gio_rong"]
        gio_chuan = pos["gio_chuan"] or std_hours
        fte = pos["fte_theo_gio"]
        n_d1 = pos["n_d1"]
        n_c3 = pos["n_c3"]
        col_g = pos["nguoi_pp2_col_g"]
        col_h = pos["nguoi_pp1_col_h"]
        giai_trinh_c3 = pos["giai_trinh_c3"] or ""
        d2_plans = pos["d2_plans"]

        delta_c3_vs_d1 = n_c3 - n_d1
        delta_c3_vs_fte = n_c3 - fte

        # Phân tích D2 qua các năm 2027-2031
        d2_c_vals = [p["can_bo_tri_col_c"] for p in d2_plans if p["can_bo_tri_col_c"] is not None]
        d2_d_vals = [p["co_the_bo_tri_col_d"] for p in d2_plans if p["co_the_bo_tri_col_d"] is not None]
        n_d2_col_c = d2_c_vals[0] if d2_c_vals else None
        n_d2_col_d = d2_d_vals[0] if d2_d_vals else None

        # Quét lời giải trình cột H của D2 xem có đề xuất tăng/giảm hoặc con số lệch với cột C không
        d2_narrative_nums = set()
        d2_reduce_mentions = []
        d2_c3_mismatch_mentions = []
        for p in d2_plans:
            txt = p["giai_trinh_col_h"] or ""
            yr = p["nam"]
            r_d2 = p["row"]
            # Bắt mẫu "bố trí XX người" hoặc "dự kiến bố trí XX người"
            for m in re.finditer(r"(?:dự kiến\s+)?bố trí\s+0?(\d+)\s+người", txt, re.IGNORECASE):
                num_in_txt = int(m.group(1))
                d2_narrative_nums.add(num_in_txt)
                if p["can_bo_tri_col_c"] is not None and num_in_txt != round(p["can_bo_tri_col_c"]):
                    d2_c3_mismatch_mentions.append(
                        f"Năm {yr} (D2!H{r_d2}): Cột C ghi {p['can_bo_tri_col_c']:g} người nhưng cột H ghi 'bố trí {num_in_txt:02d} người'"
                    )
            if "giảm" in txt.lower() and "không thuộc phương án giảm" not in txt.lower():
                d2_reduce_mentions.append(f"Năm {yr} (D2!H{r_d2}): {txt}")

        issues: List[str] = []
        severity = "HOP_LY"

        # 1. Đề xuất THÊM người so với hiện có D1 (n_c3 > n_d1) hoặc vượt quá giờ làm việc
        if delta_c3_vs_d1 > 0:
            # Nếu tăng người nhưng giờ làm việc/người sau tăng lại thấp hoặc thiếu căn cứ ở D2
            load_after_add = (gio_rong / n_c3) if n_c3 > 0 else 0.0
            if fte < n_c3 - 0.15 and phuong_phap != "PP1":
                severity = "NGHIEM_TRONG"
                issues.append(f"Đề xuất tăng +{delta_c3_vs_d1:g} người (D1={n_d1} -> C3={n_c3:g}) vượt định mức giờ ({fte:.2f} người)")
            else:
                severity = "CANH_BAO"
                issues.append(
                    f"Đề xuất bổ sung +{delta_c3_vs_d1:g} người so với thực tế D1 (hiện có {n_d1} người -> C3 đề xuất {n_c3:g} người, giờ quy đổi = {fte:.2f})"
                )
            findings.append({
                "severity": severity,
                "category": "Đề xuất TĂNG người so với nhân lực hiện có (D1 -> C3)",
                "dept_name": dept_name,
                "ma_vtvl": code,
                "ten_vtvl": name,
                "cell_ref": f"8. C3_NhuCau!J{c3_row} & 9. D1_NhanLuc",
                "current_value": f"Hiện có D1: {n_d1} người | Đề xuất C3: {n_c3:g} người (Tăng +{delta_c3_vs_d1:g}) | Giờ ròng: {gio_rong:,.1f}h ({fte:.2f} người)",
                "benchmark": f"Tải bình quân sau khi bố trí {n_c3:g} người đạt {load_after_add:,.1f}h/người ({load_after_add/gio_chuan*100:.1f}% chuẩn)",
                "detail": (
                    f"Vị trí '{name}' hiện có {n_d1} người tại biểu D1, đề xuất tăng lên {n_c3:g} người tại C3 (+{delta_c3_vs_d1:g} người). "
                    + (
                        f"Tuy nhiên tại biểu D2 cột D (Số người có thể bố trí) lại đang ghi {n_d2_col_d:g} người và cột G (Đề nghị điều chỉnh) ghi 0."
                        if n_d2_col_d is not None
                        else ""
                    )
                ),
                "recommendation": f"Làm rõ nguồn biên chế bổ sung (+{delta_c3_vs_d1:g} người lấy từ điều chuyển nội bộ hay tuyển mới) và cập nhật đúng cột D, F, G tại biểu 10. D2_PhuongAn.",
            })

        # 2. Đề xuất BỚT người so với hiện có D1 (n_c3 < n_d1) hoặc cắt về 0 người khi vẫn có giờ
        if delta_c3_vs_d1 < 0:
            load_after_cut = (gio_rong / n_c3) if n_c3 > 0 else float("inf")
            severity = "NGHIEM_TRONG"
            issues.append(
                f"Đề xuất giảm {delta_c3_vs_d1:g} người so với thực tế D1 (D1={n_d1} -> C3={n_c3:g}, giờ quy đổi={fte:.2f})"
            )
            findings.append({
                "severity": "NGHIEM_TRONG",
                "category": "Đề xuất GIẢM người so với nhân lực hiện có (D1 -> C3)",
                "dept_name": dept_name,
                "ma_vtvl": code,
                "ten_vtvl": name,
                "cell_ref": f"8. C3_NhuCau!J{c3_row} & 9. D1_NhanLuc",
                "current_value": f"Hiện có D1: {n_d1} người | Đề xuất C3: {n_c3:g} người (Giảm {delta_c3_vs_d1:g}) | Giờ ròng: {gio_rong:,.1f}h ({fte:.2f} người)",
                "benchmark": "Phải có phương án điều chuyển nhân sự dôi dư tại biểu D2 cột F",
                "detail": (
                    f"Thực tế tại biểu D1 đang có {n_d1} nhân sự đảm nhiệm vị trí '{name}', nhưng biểu C3 chỉ đề xuất bố trí {n_c3:g} người "
                    f"(giảm {abs(delta_c3_vs_d1):g} người). "
                    + (
                        f"Trong khi đó tại biểu D2 cột C vẫn ghi {n_d2_col_c:g} người và chưa thể hiện phương án điều chuyển người dôi dư."
                        if n_d2_col_c is not None
                        else "Trong khi đó biểu D2 cột C đang để trống, chưa thể hiện phương án điều chuyển người dôi dư."
                    )
                ),
                "recommendation": (
                    f"Đối chiếu lại danh sách nhân sự tại D1 ({n_d1} người) và nhu cầu C3 ({n_c3:g} người); "
                    f"nếu giảm {abs(delta_c3_vs_d1):g} người phải ghi rõ điều chuyển đi đâu tại D2."
                ),
            })

        # 3. Vị trí có khối lượng công việc nhưng bố trí 0 người (bỏ trống đẩy sang kiêm nhiệm)
        if n_c3 == 0 and gio_rong > 0:
            severity = "NGHIEM_TRONG"
            issues.append(f"Bố trí 0 người dù có {gio_rong:,.1f}h việc ({fte:.2f} định mức) -> đẩy sang kiêm nhiệm")
            findings.append({
                "severity": "NGHIEM_TRONG",
                "category": "Bố trí 0 người cho vị trí có phát sinh giờ làm việc (Đẩy sang kiêm nhiệm)",
                "dept_name": dept_name,
                "ma_vtvl": code,
                "ten_vtvl": name,
                "cell_ref": f"8. C3_NhuCau!G{c3_row}:J{c3_row}",
                "current_value": f"Giờ ròng = {gio_rong:,.1f}h ({fte:.2f} người) nhưng bố trí C3 = 0 người (D1 = {n_d1} người)",
                "benchmark": "Vị trí có giờ làm việc phải có người đảm nhận hoặc cộng giờ kiêm nhiệm vào vị trí nhận kiêm nhiệm",
                "detail": (
                    f"Vị trí '{name}' có {gio_rong:,.1f} giờ/năm ({fte:.2f} định mức) nhưng biểu C3 bố trí 0 người"
                    + (f" (giải trình C3: '{giai_trinh_c3[:150]}')" if giai_trinh_c3 else "")
                    + f". Khối lượng này chưa có người chuyên trách; hiện D1 có {n_d1} người gắn mã vị trí này."
                ),
                "recommendation": "Gộp công việc sang vị trí kiêm nhiệm thực tế hoặc xác định rõ nhân sự nào tại D1 gánh phần giờ này (cột E, F của D1).",
            })

        # 4. Đề xuất giảm người tại thuyết minh D2 trái ngược với giờ làm việc (ví dụ XDĐ_CV02)
        if d2_reduce_mentions:
            severity = "NGHIEM_TRONG"
            n_sau_giam = max(1.0, (n_c3 - 1))
            load_if_reduced = gio_rong / n_sau_giam
            issues.append(f"Thuyết minh D2 đề xuất giảm người dù giờ ròng = {gio_rong:,.1f}h ({fte:.2f} định mức)")
            findings.append({
                "severity": "NGHIEM_TRONG",
                "category": "Đề xuất giảm người tại D2 bất hợp lý so với khối lượng giờ làm việc",
                "dept_name": dept_name,
                "ma_vtvl": code,
                "ten_vtvl": name,
                "cell_ref": f"10. D2_PhuongAn (các dòng của {code})",
                "current_value": f"Giờ ròng = {gio_rong:,.1f}h ({fte:.2f} định mức) | C3 bố trí {n_c3:g} người | Thuyết minh D2 có đề xuất giảm người",
                "benchmark": f"{gio_chuan:,.0f} giờ/người/năm (nếu giảm 1 người, còn {n_sau_giam:g} người thì bình quân {load_if_reduced:,.1f}h/người = {load_if_reduced/gio_chuan*100:.1f}% định mức)",
                "detail": (
                    f"Vị trí '{name}' có khối lượng {gio_rong:,.1f}h/năm (tương đương {fte:.2f} người theo định mức). "
                    f"Tuy nhiên tại biểu D2 lại ghi: {' | '.join(d2_reduce_mentions[:2])}. "
                    f"Nếu giảm còn {n_sau_giam:g} người thì mỗi người phải gánh {load_if_reduced:,.1f}h/năm ({load_if_reduced/gio_chuan*100:.0f}% định mức chuẩn)."
                ),
                "recommendation": "Bỏ đề xuất giảm người tại thuyết minh D2 hoặc phải cắt giảm/chuyển giao bớt đầu việc tại B1 tương ứng trước khi giảm biên chế.",
            })

        # 5. Mâu thuẫn số liệu cột C và lời thuyết minh cột H tại D2 (ví dụ XDĐ_CV01, UBKT_PCN)
        if d2_c3_mismatch_mentions:
            severity = "NGHIEM_TRONG"
            issues.append("Mâu thuẫn giữa số người cột C và lời giải trình cột H tại biểu D2")
            findings.append({
                "severity": "NGHIEM_TRONG",
                "category": "Mâu thuẫn giữa số liệu và lời giải trình tại biểu 10. D2_PhuongAn",
                "dept_name": dept_name,
                "ma_vtvl": code,
                "ten_vtvl": name,
                "cell_ref": f"10. D2_PhuongAn (các dòng của {code})",
                "current_value": "; ".join(d2_c3_mismatch_mentions[:2]),
                "benchmark": "Số người trong lời giải trình cột H phải khớp với số người cột C của D2 và cột J của C3",
                "detail": (
                    f"Tại vị trí '{name}', số người cần bố trí ở C3 (cột J) và D2 (cột C) là {n_c3:g} người, "
                    f"nhưng nội dung giải trình ở cột H của D2 lại viết khác: {'; '.join(d2_c3_mismatch_mentions[:3])}."
                ),
                "recommendation": "Sửa lại nội dung thuyết minh tại cột H biểu D2 hoặc điều chỉnh lại số lượng bố trí cho thống nhất giữa C3, D1 và D2.",
            })

        # 6. Cột D của D2 ("Số người có thể bố trí") không khớp thực tế nhân lực hiện có tại D1
        if n_d2_col_d is not None and round(n_d2_col_d) != n_d1:
            if severity == "HOP_LY":
                severity = "CANH_BAO"
            issues.append(f"D2 cột D ghi có thể bố trí {n_d2_col_d:g} người != D1 thực tế có {n_d1} người")
            findings.append({
                "severity": "CANH_BAO",
                "category": "Lệch số người hiện có giữa biểu D1 và cột D biểu D2",
                "dept_name": dept_name,
                "ma_vtvl": code,
                "ten_vtvl": name,
                "cell_ref": f"10. D2_PhuongAn!D{d2_plans[0]['row']} vs 9. D1_NhanLuc",
                "current_value": f"D2 cột D = {n_d2_col_d:g} người vs D1 hiện có = {n_d1} người",
                "benchmark": "Số người có thể bố trí tại D2 (cột D) phải phản ánh đúng nhân lực thực tế tại D1",
                "detail": (
                    f"Biểu D1 có {n_d1} nhân sự gắn mã '{code}', nhưng sang biểu D2 cột D đơn vị điền đồng loạt bằng {n_d2_col_d:g} người."
                ),
                "recommendation": f"Cập nhật cột D của D2 từ {n_d2_col_d:g} thành {n_d1} người cho khớp với danh sách nhân sự tại D1.",
            })

        # 7. Lỗi nhập đồng thời cả cột G (PP2) và cột H (PP1) hoặc dùng 'phần dư lớn nhất' cho chức danh PP1
        if phuong_phap == "PP2" and col_h is not None and col_h > 0:
            if severity == "HOP_LY":
                severity = "CANH_BAO"
            issues.append(f"Chọn PP2 nhưng vẫn nhập Người PP1 (cột H = {col_h:g})")
        if phuong_phap == "PP1" and "phần dư lớn nhất" in giai_trinh_c3.lower():
            if severity == "HOP_LY":
                severity = "CANH_BAO"
            issues.append("Chọn PP1 (theo chức danh) nhưng giải trình lại chia theo 'phần dư lớn nhất' của giờ B1")
            findings.append({
                "severity": "CANH_BAO",
                "category": "Mâu thuẫn phương pháp PP1 và cách tính theo giờ (Phần dư lớn nhất)",
                "dept_name": dept_name,
                "ma_vtvl": code,
                "ten_vtvl": name,
                "cell_ref": f"8. C3_NhuCau!B{c3_row}, H{c3_row}, K{c3_row}",
                "current_value": f"Phương pháp: {phuong_phap} | Bố trí: {n_c3:g} người | Giải trình: 'Áp dụng phần dư lớn nhất...'",
                "benchmark": f"Phương pháp gợi ý theo chức danh: {suggested_method}",
                "detail": (
                    f"Vị trí '{name}' khai báo phương pháp là PP1 (định biên cứng theo chức danh/cơ cấu), "
                    f"nhưng trong cột K lại giải trình chia biên chế theo tỷ lệ giờ B1 và làm tròn bằng 'phần dư lớn nhất'."
                ),
                "recommendation": "Nếu tính biên chế theo khối lượng giờ công việc thì chuyển sang PP2 hoặc PP1+PP2; nếu giữ PP1 thì thuyết minh theo quyết định giao cơ cấu cấp phó/ủy viên.",
            })

        comparisons.append({
            "ma_vtvl": code,
            "ten_vtvl": name,
            "dept_code": pos["dept_code"],
            "dept_name": dept_name,
            "role_group": pos["role_group"],
            "phuong_phap": phuong_phap,
            "suggested_method": suggested_method,
            "gio_rong": gio_rong,
            "ngay_lam_viec_quy_doi": gio_rong / 8.0,
            "fte_theo_gio": fte,
            "n_d1": n_d1,
            "n_c3": n_c3,
            "n_d2_col_c": n_d2_col_c,
            "n_d2_col_d": n_d2_col_d,
            "col_g_pp2": col_g,
            "col_h_pp1": col_h,
            "delta_c3_vs_d1": delta_c3_vs_d1,
            "delta_c3_vs_fte": delta_c3_vs_fte,
            "d2_narrative_nums": sorted(list(d2_narrative_nums)),
            "d2_reduce_flag": len(d2_reduce_mentions) > 0,
            "d2_mismatch_flag": len(d2_c3_mismatch_mentions) > 0,
            "severity": severity,
            "issues": issues,
        })

    return {
        "summary_totals": {
            "sum_col_g": sum_col_g,
            "sum_col_h": sum_col_h,
            "sh_plus_sg": sh_plus_sg,
            "sum_col_j": sum_col_j,
            "diff_sh_sg_pct": diff_sh_sg_pct,
            "sum_d1": sum_d1,
            "sum_fte": sum_fte,
        },
        "comparisons": comparisons,
        "findings": findings,
    }
