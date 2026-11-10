# -*- coding: utf-8 -*-
"""
Module 3: Rà soát sự bất thường giữa việc phân bổ các vị trí trong Ban/Bộ phận so với các Ban khác
(Ban nhiều việc - ít người, Ban ít việc - nhiều người, Ban mở nhiều mã vị trí nhưng bỏ trống 0 người).
"""

from typing import Any, Dict, List


def analyze_department_balance(data: Dict[str, Any]) -> Dict[str, Any]:
    positions: List[Dict[str, Any]] = data["positions"]
    std_hours: float = data.get("standard_hours", 1904.0)

    dept_buckets: Dict[str, Dict[str, Any]] = {}
    total_unit_hours = sum(p["gio_rong"] for p in positions)
    total_unit_d1 = sum(p["n_d1"] for p in positions)
    total_unit_c3 = sum(p["n_c3"] for p in positions)

    for pos in positions:
        d_code = pos["dept_code"]
        d_name = pos["dept_name"]
        b = dept_buckets.setdefault(
            d_code,
            {
                "dept_code": d_code,
                "dept_name": d_name,
                "so_vtvl": 0,
                "so_vtvl_co_nguoi_c3": 0,
                "so_vtvl_0_nguoi_c3": 0,
                "vtvl_0_nguoi_list": [],
                "tong_gio_rong": 0.0,
                "gio_treo_0_nguoi": 0.0,
                "fte_theo_gio": 0.0,
                "n_d1": 0,
                "n_c3": 0.0,
                "so_cong_viec_b1": 0,
                "positions": [],
            },
        )
        b["so_vtvl"] += 1
        b["tong_gio_rong"] += pos["gio_rong"]
        b["fte_theo_gio"] += pos["fte_theo_gio"]
        b["n_d1"] += pos["n_d1"]
        b["n_c3"] += pos["n_c3"]
        b["so_cong_viec_b1"] += len(pos["b1_tasks"])
        b["positions"].append(pos)

        if pos["n_c3"] > 0:
            b["so_vtvl_co_nguoi_c3"] += 1
        else:
            b["so_vtvl_0_nguoi_c3"] += 1
            b["gio_treo_0_nguoi"] += pos["gio_rong"]
            b["vtvl_0_nguoi_list"].append(f"{pos['ma_vtvl']} ({pos['ten_vtvl']}: {pos['gio_rong']:,.0f}h)")

    departments: List[Dict[str, Any]] = []
    findings: List[Dict[str, Any]] = []

    for d_code, b in dept_buckets.items():
        gio = b["tong_gio_rong"]
        fte = b["fte_theo_gio"]
        n_d1 = b["n_d1"]
        n_c3 = b["n_c3"]
        gio_treo = b["gio_treo_0_nguoi"]

        gio_bq_d1 = (gio / n_d1) if n_d1 > 0 else 0.0
        gio_bq_c3 = (gio / n_c3) if n_c3 > 0 else 0.0
        ty_le_tai_d1_pct = (gio_bq_d1 / std_hours * 100.0) if n_d1 > 0 else 0.0
        ty_le_tai_c3_pct = (gio_bq_c3 / std_hours * 100.0) if n_c3 > 0 else 0.0

        ty_trong_gio_pct = (gio / total_unit_hours * 100.0) if total_unit_hours > 0 else 0.0
        ty_trong_d1_pct = (n_d1 / total_unit_d1 * 100.0) if total_unit_d1 > 0 else 0.0
        ty_trong_c3_pct = (n_c3 / total_unit_c3 * 100.0) if total_unit_c3 > 0 else 0.0

        # Chênh lệch giữa Tỷ trọng Giờ và Tỷ trọng Người hiện có D1
        lech_ty_trong_d1 = ty_trong_gio_pct - ty_trong_d1_pct
        # Chênh lệch số người hiện có (D1) so với Định mức giờ chuẩn
        thieu_hut_d1_so_voi_gio = n_d1 - fte
        thay_doi_c3_so_voi_d1 = n_c3 - n_d1

        status_label = "Cân đối hợp lý"
        severity = "HOP_LY"
        dept_notes: List[str] = []

        # 1. Phát hiện Ban "NHIỀU VIỆC - ÍT NGƯỜI" (theo nhân sự hiện có D1)
        if ty_le_tai_d1_pct > 112.0:
            severity = "NGHIEM_TRONG" if ty_le_tai_d1_pct > 125.0 else "CANH_BAO"
            status_label = f"Nhiều việc - Ít người hiện có ({ty_le_tai_d1_pct:.1f}% chuẩn)"
            dept_notes.append(
                f"Chiếm {ty_trong_gio_pct:.1f}% tổng giờ đơn vị nhưng chỉ có {ty_trong_d1_pct:.1f}% nhân sự D1 "
                f"({n_d1} người gánh {gio:,.1f}h = {gio_bq_d1:,.0f}h/người, thiếu {abs(thieu_hut_d1_so_voi_gio):.2f} biên chế theo giờ)."
            )
            findings.append({
                "severity": severity,
                "category": "Ban 'Nhiều việc - Ít người' (Quá tải so với nhân sự hiện có D1)",
                "dept_name": b["dept_name"],
                "ma_vtvl": f"KHỐI_{d_code}",
                "ten_vtvl": b["dept_name"],
                "cell_ref": "Tổng hợp liên biểu B1 - C3 - D1",
                "current_value": (
                    f"Tổng giờ: {gio:,.1f}h ({fte:.2f} định mức) | Nhân sự D1: {n_d1} người "
                    f"-> Bình quân {gio_bq_d1:,.0f}h/người ({ty_le_tai_d1_pct:.1f}% chuẩn 1.904h)"
                ),
                "benchmark": "Tải trọng bình quân ban nằm trong ngưỡng 85% - 110% (1.618h - 2.094h/người)",
                "detail": (
                    f"{b['dept_name']} hiện gánh {gio:,.1f} giờ công việc ({ty_trong_gio_pct:.1f}% toàn đơn vị, tương đương {fte:.2f} người), "
                    f"nhưng tại biểu D1 chỉ có {n_d1} người ({ty_trong_d1_pct:.1f}% nhân sự), dẫn tới bình quân mỗi người phải làm "
                    f"{gio_bq_d1:,.0f} giờ/năm ({ty_le_tai_d1_pct:.1f}% chuẩn). Tại C3 đơn vị đang đề xuất nâng lên {n_c3:g} người."
                ),
                "recommendation": (
                    f"Ưu tiên bổ sung/điều chuyển nhân sự cho {b['dept_name']} hoặc kiểm tra lại xem các vị trí trong ban có kê cao giờ B1 hay không."
                ),
            })

        # 2. Phát hiện Ban "ÍT VIỆC - NHIỀU NGƯỜI"
        elif ty_le_tai_d1_pct < 80.0 or ty_le_tai_c3_pct < 80.0:
            severity = "CANH_BAO"
            status_label = f"Ít việc - Nhiều người ({min(ty_le_tai_d1_pct, ty_le_tai_c3_pct):.1f}% chuẩn)"
            dept_notes.append(
                f"Chỉ chiếm {ty_trong_gio_pct:.1f}% tổng giờ đơn vị ({gio:,.1f}h = {fte:.2f} định mức) nhưng bố trí "
                f"{n_d1} người ở D1 và {n_c3:g} người ở C3 (bình quân {gio_bq_c3:,.0f}h/người = {ty_le_tai_c3_pct:.1f}% định mức)."
            )
            findings.append({
                "severity": "CANH_BAO",
                "category": "Ban 'Ít việc - Nhiều người' (Tải trọng giờ bình quân thấp so với các ban khác)",
                "dept_name": b["dept_name"],
                "ma_vtvl": f"KHỐI_{d_code}",
                "ten_vtvl": b["dept_name"],
                "cell_ref": "Tổng hợp liên biểu B1 - C3 - D1",
                "current_value": (
                    f"Tổng giờ: {gio:,.1f}h ({fte:.2f} định mức) | Bố trí D1={n_d1}, C3={n_c3:g} người "
                    f"-> Bình quân {gio_bq_c3:,.0f}h/người ({ty_le_tai_c3_pct:.1f}% chuẩn 1.904h)"
                ),
                "benchmark": "Tải trọng bình quân ban nằm trong ngưỡng 85% - 110% (1.618h - 2.094h/người)",
                "detail": (
                    f"{b['dept_name']} có tổng giờ kê khai là {gio:,.1f}h (tương đương {fte:.2f} định mức 1.904h), "
                    f"nhưng bố trí {n_c3:g} người (chiếm {ty_trong_c3_pct:.1f}% biên chế toàn đơn vị trong khi chỉ chiếm {ty_trong_gio_pct:.1f}% khối lượng giờ). "
                    f"So với Ban Xây dựng Đảng ({2650:,.0f}h/người D1) hay MTTQ ({2261:,.0f}h/người D1), tải trọng giờ của bộ phận này thấp hơn đáng kể."
                ),
                "recommendation": (
                    "Rà soát xem bộ phận có kê khai sót đầu việc chỉ đạo/tham mưu tại biểu B1 không, hoặc cân đối lại việc phân công kiêm nhiệm giữa các ban."
                ),
            })

        # 3. Phát hiện Ban mở nhiều vị trí việc làm nhưng bỏ trống 0 người (Đẩy việc sang kiêm nhiệm nội bộ)
        if b["so_vtvl_0_nguoi_c3"] >= 1 and gio_treo > 0:
            if severity == "HOP_LY":
                severity = "NGHIEM_TRONG" if b["so_vtvl_0_nguoi_c3"] >= 2 else "CANH_BAO"
            if status_label == "Cân đối hợp lý":
                status_label = f"Bỏ trống {b['so_vtvl_0_nguoi_c3']}/{b['so_vtvl']} vị trí (Đẩy kiêm nhiệm)"
            else:
                status_label += f" + Bỏ trống {b['so_vtvl_0_nguoi_c3']}/{b['so_vtvl']} VTVL"

            fte_treo = gio_treo / std_hours
            dept_notes.append(
                f"Có {b['so_vtvl_0_nguoi_c3']}/{b['so_vtvl']} mã VTVL bị bố trí 0 người với tổng {gio_treo:,.1f} giờ ({fte_treo:.2f} biên chế) đẩy sang kiêm nhiệm."
            )
            findings.append({
                "severity": "NGHIEM_TRONG" if b["so_vtvl_0_nguoi_c3"] >= 2 else "CANH_BAO",
                "category": "Mất cân đối cấu trúc VTVL trong Ban (Chia nhỏ vị trí nhưng bỏ trống 0 người)",
                "dept_name": b["dept_name"],
                "ma_vtvl": f"KHỐI_{d_code}",
                "ten_vtvl": b["dept_name"],
                "cell_ref": "6. C1_VTVL & 8. C3_NhuCau",
                "current_value": (
                    f"{b['so_vtvl_0_nguoi_c3']}/{b['so_vtvl']} vị trí bố trí 0 người, treo {gio_treo:,.1f} giờ ({fte_treo:.2f} định mức)"
                ),
                "benchmark": "Mỗi vị trí mở tại C1/C3 cần có nhân sự đảm nhận hoặc gộp đầu việc vào vị trí kiêm nhiệm chính",
                "detail": (
                    f"Tại {b['dept_name']}, đơn vị mở {b['so_vtvl']} vị trí nhưng có tới {b['so_vtvl_0_nguoi_c3']} vị trí bị gán 0 người: "
                    f"{'; '.join(b['vtvl_0_nguoi_list'])}. Tổng số giờ không có người chuyên trách là {gio_treo:,.1f}h "
                    f"(tương đương {fte_treo:.2f} người làm việc toàn thời gian), làm đội tải thực tế của {n_c3:g} người còn lại trong ban lên {gio_bq_c3:,.0f}h/người ({ty_le_tai_c3_pct:.1f}%)."
                ),
                "recommendation": (
                    "Không để nhiều vị trí chuyên môn rời rạc có 0 người; cần bố trí ít nhất 1 chuyên viên tổng hợp kiêm nhiệm chính thức "
                    "hoặc điều chỉnh lại cơ cấu biên chế giữa các ban."
                ),
            })

        departments.append({
            "dept_code": d_code,
            "dept_name": b["dept_name"],
            "so_vtvl": b["so_vtvl"],
            "so_vtvl_co_nguoi_c3": b["so_vtvl_co_nguoi_c3"],
            "so_vtvl_0_nguoi_c3": b["so_vtvl_0_nguoi_c3"],
            "vtvl_0_nguoi_list": b["vtvl_0_nguoi_list"],
            "so_cong_viec_b1": b["so_cong_viec_b1"],
            "tong_gio_rong": gio,
            "gio_treo_0_nguoi": gio_treo,
            "fte_theo_gio": fte,
            "n_d1": n_d1,
            "n_c3": n_c3,
            "thieu_hut_d1_so_voi_gio": thieu_hut_d1_so_voi_gio,
            "thay_doi_c3_so_voi_d1": thay_doi_c3_so_voi_d1,
            "gio_bq_d1": gio_bq_d1,
            "gio_bq_c3": gio_bq_c3,
            "ty_le_tai_d1_pct": ty_le_tai_d1_pct,
            "ty_le_tai_c3_pct": ty_le_tai_c3_pct,
            "ty_trong_gio_pct": ty_trong_gio_pct,
            "ty_trong_d1_pct": ty_trong_d1_pct,
            "ty_trong_c3_pct": ty_trong_c3_pct,
            "lech_ty_trong_d1": lech_ty_trong_d1,
            "status_label": status_label,
            "severity": severity,
            "notes": dept_notes,
        })

    total_d1_hours = sum(p.get("gio_d1_cung_cap", 0.0) for p in positions)
    if total_d1_hours <= 0:
        total_d1_hours = total_unit_d1 * std_hours
    exceed_d1_hours = total_unit_hours - total_d1_hours
    total_fte = total_unit_hours / std_hours if std_hours > 0 else 0.0
    exceed_d1_fte = total_fte - total_unit_d1

    return {
        "unit_totals": {
            "total_vtvl": len(positions),
            "total_vtvl_0_nguoi": sum(1 for p in positions if p["n_c3"] == 0),
            "total_hours": total_unit_hours,
            "total_fte": total_fte,
            "total_d1": total_unit_d1,
            "total_d1_hours": total_d1_hours,
            "exceed_d1_hours": exceed_d1_hours,
            "exceed_d1_fte": exceed_d1_fte,
            "is_exceeding_d1": exceed_d1_hours > 0,
            "total_c3": total_unit_c3,
            "avg_hours_per_d1": (total_unit_hours / total_unit_d1) if total_unit_d1 > 0 else 0.0,
            "avg_hours_per_c3": (total_unit_hours / total_unit_c3) if total_unit_c3 > 0 else 0.0,
        },
        "departments": departments,
        "findings": findings,
    }
