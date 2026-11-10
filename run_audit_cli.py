# -*- coding: utf-8 -*-
"""
Script chạy nhanh rà soát chuyên môn VTVL từ dòng lệnh và xuất file Excel báo cáo.
"""

import sys
from pathlib import Path
from core.audit_pipeline import run_full_audit
from exporters.excel_report_builder import build_excel_audit_report


def main():
    if len(sys.argv) < 2:
        print('Cách dùng: python run_audit_cli.py "<đường dẫn file bộ biểu VTVL .xlsx>"')
        sys.exit(1)
    input_file = sys.argv[1]
    res = run_full_audit(input_file)
    stem = Path(input_file).stem
    out_dir = Path(__file__).resolve().parent / "ket_qua_ra_soat"
    out_file = out_dir / f"Bao_cao_Ra_soat_Chuyen_mon_Gio_VTVL_{stem}.xlsx"
    saved = build_excel_audit_report(res, str(out_file))

    print("=== KẾT QUẢ RÀ SOÁT CHUYÊN MÔN VTVL ===")
    print("File đầu vào:", res["file_path"])
    print("File báo cáo Excel:", saved)
    print("Thống kê phát hiện:", res["stats"])
    print("Tổng hợp đơn vị:", res["unit_totals"])
    print("Tổng hợp C3 (G, H, J):", res["headcount_totals"])
    print("\n--- PHÂN BỔ GIỮA CÁC BAN / BỘ PHẬN ---")
    for d in res["departments"]:
        print(
            f"  * {d['dept_name']} ({d['dept_code']}): "
            f"Số VTVL={d['so_vtvl']} (0 người={d['so_vtvl_0_nguoi_c3']}), "
            f"Tổng giờ={d['tong_gio_rong']:,.1f}h (Định mức={d['fte_theo_gio']:.2f} người), "
            f"Hiện có D1={d['n_d1']}, Đề xuất C3={d['n_c3']:g}, "
            f"Tải D1={d['gio_bq_d1']:,.0f}h/ng ({d['ty_le_tai_d1_pct']:.1f}%), "
            f"Tải C3={d['gio_bq_c3']:,.0f}h/ng ({d['ty_le_tai_c3_pct']:.1f}%) "
            f"=> [{d['status_label']}]"
        )


if __name__ == "__main__":
    main()
