# -*- coding: utf-8 -*-
"""
Pipeline tổng hợp kết quả rà soát chuyên môn VTVL (Giờ làm việc, Thêm/Bớt người, Cân đối giữa các Ban, Đối chiếu biên chế giao theo QĐ 2398/QĐ-UBND).
"""

from typing import Any, Dict, Optional
from .excel_loader import load_vtvl_workbook
from .analyzer_hours import analyze_hours_anomalies
from .analyzer_headcount import analyze_headcount_proposals
from .analyzer_department import analyze_department_balance
from .qd2398_data import lookup_qd2398_by_unit


def run_full_audit(file_path: str, sheets_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    raw_data = load_vtvl_workbook(file_path, sheets_payload)
    hours_res = analyze_hours_anomalies(raw_data)
    headcount_res = analyze_headcount_proposals(raw_data)
    dept_res = analyze_department_balance(raw_data)
    qd2398_res = lookup_qd2398_by_unit(
        raw_data["file_name"],
        raw_data.get("co_quan_a1", ""),
        raw_data["positions"],
        raw_data["d1_rows"],
    )

    all_findings = []
    for f in dept_res["findings"]:
        f_copy = dict(f)
        f_copy["module"] = "3. Cân đối giữa các Ban"
        all_findings.append(f_copy)
    for f in hours_res["findings"]:
        f_copy = dict(f)
        f_copy["module"] = "1. Bất thường Giờ làm việc"
        all_findings.append(f_copy)
    for f in headcount_res["findings"]:
        f_copy = dict(f)
        f_copy["module"] = "2. Bất hợp lý Thêm/Bớt người"
        all_findings.append(f_copy)

    sev_order = {"NGHIEM_TRONG": 0, "CANH_BAO": 1, "HOP_LY": 2}
    all_findings.sort(key=lambda x: sev_order.get(x["severity"], 9))

    critical_count = sum(1 for f in all_findings if f["severity"] == "NGHIEM_TRONG")
    warning_count = sum(1 for f in all_findings if f["severity"] == "CANH_BAO")

    return {
        "file_name": raw_data["file_name"],
        "file_path": raw_data["file_path"],
        "standard_hours": raw_data["standard_hours"],
        "qd2398_info": qd2398_res["info"],
        "qd2398_chuoi_da_thu": qd2398_res["chuoi_da_thu"],
        "co_quan_a1": raw_data.get("co_quan_a1", ""),
        "unit_totals": dept_res["unit_totals"],
        "headcount_totals": headcount_res["summary_totals"],
        "departments": dept_res["departments"],
        "position_hour_evals": hours_res["position_hour_evals"],
        "headcount_comparisons": headcount_res["comparisons"],
        "b1_anomalies": hours_res["b1_anomalies"],
        "all_findings": all_findings,
        "stats": {
            "total_findings": len(all_findings),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "hours_findings_count": len(hours_res["findings"]),
            "headcount_findings_count": len(headcount_res["findings"]),
            "dept_findings_count": len(dept_res["findings"]),
        },
    }
