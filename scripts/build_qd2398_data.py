# -*- coding: utf-8 -*-
"""
Sinh dữ liệu biên chế giao theo Quyết định số 2398/QĐ-UBND ngày 04/10/2026 của UBND tỉnh Hà Tĩnh
từ các file phụ lục .docx trong data/qd2398/ ra core/qd2398_data.json.

Chỉ cần chạy lại khi có phụ lục mới (cần python-docx):
    pip install python-docx
    python scripts/build_qd2398_data.py

Ứng dụng khi chạy chỉ đọc file JSON, không cần python-docx.
Script tự đối chiếu các dòng tổng với dòng chi tiết; lệch là dừng (fail loudly), không sinh dữ liệu sai.
"""

import json
import re
import sys
from pathlib import Path

import docx

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "data" / "qd2398"
OUT = BASE / "core" / "qd2398_data.json"

VAN_BAN = {
    "so_hieu": "2398/QĐ-UBND",
    "ngay": "04/10/2026",
    "co_quan_ban_hanh": "UBND tỉnh Hà Tĩnh",
    "trich_yeu": (
        "Giao biên chế công chức trong các cơ quan, tổ chức hành chính; số lượng người làm việc trong "
        "các đơn vị sự nghiệp công lập, tổ chức hội và chỉ tiêu lao động hợp đồng năm 2026"
    ),
    "ten_ngan": "QĐ 2398/QĐ-UBND",
}

PHU_LUC_TEN = {
    "1": "Phụ lục 1 - Biên chế cán bộ, công chức và HĐ theo NĐ 111/2022 trong cơ quan, tổ chức hành chính",
    "2": "Phụ lục 2 - Số lượng người làm việc và HĐ trong đơn vị sự nghiệp công lập (nhóm 3, 4)",
    "3": "Phụ lục 3 - Số lượng người làm việc trong các tổ chức hội",
    "4A": "Phụ lục 4A - Số lượng người làm việc tại các Trường Mầm non năm học 2026-2027",
    "4B": "Phụ lục 4B - Số lượng người làm việc tại các Trường Tiểu học năm học 2026-2027",
    "4C": "Phụ lục 4C - Số lượng người làm việc tại các Trường THCS năm học 2026-2027",
    "4D": "Phụ lục 4D - Số lượng người làm việc tại các Trường THPT năm học 2026-2027",
}


def table_rows(fn: str, ti: int):
    """Đọc bảng thứ ti, bỏ ô gộp ngang trùng lặp."""
    t = docx.Document(str(SRC / fn)).tables[ti]
    out = []
    for r in t.rows:
        cells, prev = [], None
        for c in r.cells:
            if c._tc is prev:
                continue
            prev = c._tc
            cells.append(" ".join(c.text.split()))
        out.append(cells)
    return out


def num(x: str) -> int:
    x = (x or "").replace(".", "").replace(",", "").strip()
    return int(x) if re.fullmatch(r"-?\d+", x) else 0


def check(label: str, got: int, exp: int):
    if got != exp:
        sys.exit(f"[LỖI] {label}: cộng chi tiết = {got} nhưng dòng tổng ghi {exp}")


units = []
tong_hop = {}


def add(phu_luc, nhom, stt, ten, so_lieu, *, ten_cha=None, xa=None, tong_hop_dong=False, ghi_chu=""):
    units.append({
        "id": f"PL{phu_luc}-{len(units) + 1}",
        "phu_luc": phu_luc,
        "nhom": nhom,
        "stt": stt,
        "ten": ten,
        "ten_cha": ten_cha,
        "xa": xa,
        "la_dong_tong_hop": tong_hop_dong,
        "so_lieu": so_lieu,
        "ghi_chu": ghi_chu,
    })


# ---------------- Phụ lục 1: Công chức ----------------
R = table_rows("Phu-luc-1-Cong-chuc-541.docx", 1)[2:]
cols1 = ["tong_giao", "chinh_thuc", "doi_du", "hop_dong_111"]


def sl1(r):
    return {k: num(r[i + 2]) for i, k in enumerate(cols1)}


tong_hop["1"] = {"tong": sl1(R[0]), "du_phong": num(R[-1][2])}
nhom, parent = None, None
sums = {}
for r in R[1:-1]:
    stt, ten = r[0], r[1]
    if stt in ("I", "II"):
        nhom = f"{stt}. {ten}"
        sums[nhom] = {"ghi": sl1(r), "tinh": dict.fromkeys(cols1, 0)}
        continue
    is_xa = stt.isdigit() and nhom.startswith("II")
    if "." in stt:
        add("1", nhom, stt, ten, sl1(r), ten_cha=parent["ten"], ghi_chu=r[6] if len(r) > 6 else "")
        parent["_con"] += 1
        for k in cols1:
            parent["_tinh"][k] += sl1(r)[k]
        continue
    add("1", nhom, stt, ten, sl1(r), xa=ten if is_xa else None, ghi_chu=r[6] if len(r) > 6 else "")
    parent = units[-1]
    parent["_con"], parent["_tinh"] = 0, dict.fromkeys(cols1, 0)
    for k in cols1:
        sums[nhom]["tinh"][k] += sl1(r)[k]
for u in units:
    if u.get("_con"):
        u["la_dong_tong_hop"] = True
        for k in ("tong_giao", "hop_dong_111"):
            check(f"PL1 {u['ten']} {k}", u["_tinh"][k], u["so_lieu"][k])
    u.pop("_con", None)
    u.pop("_tinh", None)
for nh, s in sums.items():
    for k in cols1:
        check(f"PL1 {nh} {k}", s["tinh"][k], s["ghi"][k])
    tong_hop["1"][nh] = s["ghi"]
for k in cols1:
    check(f"PL1 tổng A {k}", sum(s["ghi"][k] for s in sums.values()), tong_hop["1"]["tong"][k])

# ---------------- Phụ lục 2: Viên chức ----------------
R = table_rows("Phu-luc-2-Vien-chuc-nhom-3.4-963.docx", 1)[2:]
cols2 = ["tong_giao", "chinh_thuc", "doi_du", "hop_dong_235", "tu_dam_bao"]


def sl2(r):
    return {k: num(r[i + 2]) for i, k in enumerate(cols2)}


tong_hop["2"] = {"tong": sl2(R[0]), "du_phong": num(R[-1][2])}
# Văn bản gốc đánh STT lệch (khối Văn hóa ghi "-", con đầu ghi "III", "VI" dùng 2 lần)
# => nhận diện nhóm theo TÊN thay vì STT.
SECTION_RE = re.compile(r"^(Đơn vị sự nghiệp|Trạm Y tế cấp xã|TT DỊCH VỤ TỔNG HỢP CẤP XÃ)", re.IGNORECASE)
nhom, nhom_xa = None, None
stack = []  # (level, unit)
sec_sum = {}
for r in R[1:-1]:
    stt, ten = r[0], r[1]
    if SECTION_RE.match(ten):
        nhom = ten
        nhom_xa = "Trạm Y tế" if ten.lower().startswith("trạm y tế") else ("TT Dịch vụ tổng hợp" if "DỊCH VỤ" in ten.upper() else None)
        sec_sum[nhom] = {"ghi": sl2(r), "tinh": dict.fromkeys(cols2, 0)}
        stack = []
        continue
    ghi_chu = r[7] if len(r) > 7 else ""
    if nhom_xa:
        add("2", nhom, stt, f"{nhom_xa} - {ten}", sl2(r), xa=ten, ghi_chu=ghi_chu)
        for k in cols2:
            sec_sum[nhom]["tinh"][k] += sl2(r)[k]
        continue
    # cấp: "1" / "III"(lỗi đánh số) = 1 ; "1.1" = 2 ; "-" = con của dòng gần nhất
    if stt == "-":
        level = (stack[-1][0] + 1) if stack else 1
        if stack and stack[-1][1]["stt"] == "-":
            level = stack[-1][0]
    elif "." in stt:
        level = 2
    else:
        level = 1
    while stack and stack[-1][0] >= level:
        stack.pop()
    cha = stack[-1][1] if stack else None
    add("2", nhom, stt, ten, sl2(r), ten_cha=cha["ten"] if cha else None, ghi_chu=ghi_chu)
    u = units[-1]
    u["_lv"] = level
    if cha is None:
        for k in cols2:
            sec_sum[nhom]["tinh"][k] += sl2(r)[k]
    stack.append((level, u))
# đánh dấu dòng tổng hợp (có con) và kiểm tra cộng con
by_parent = {}
for u in units:
    if u["phu_luc"] == "2" and u["ten_cha"]:
        by_parent.setdefault((u["nhom"], u["ten_cha"]), []).append(u)
for u in units:
    if u["phu_luc"] != "2":
        continue
    ch = by_parent.get((u["nhom"], u["ten"]))
    if ch:
        u["la_dong_tong_hop"] = True
        for k in ("tong_giao", "hop_dong_235", "tu_dam_bao"):
            check(f"PL2 {u['ten']} {k}", sum(c["so_lieu"][k] for c in ch), u["so_lieu"][k])
    u.pop("_lv", None)
for nh, s in sec_sum.items():
    for k in ("tong_giao", "hop_dong_235", "tu_dam_bao"):
        check(f"PL2 {nh} {k}", s["tinh"][k], s["ghi"][k])
    tong_hop["2"][nh] = s["ghi"]
for k in ("tong_giao", "chinh_thuc", "doi_du", "hop_dong_235", "tu_dam_bao"):
    check(f"PL2 tổng A {k}", sum(s["ghi"][k] for s in sec_sum.values()), tong_hop["2"]["tong"][k])

# ---------------- Phụ lục 3: Hội ----------------
R = table_rows("Phu-luc-3-Hoi-780.docx", 1)[2:]
cols3 = ["tong_giao", "bien_che", "ho_tro_nsnn", "hop_dong_235"]


def sl3(r):
    return {k: num(r[i + 2]) for i, k in enumerate(cols3)}


tong_hop["3"] = {"tong": sl3(R[0])}
for r in R[1:]:
    add("3", "Tổ chức hội", r[0], r[1], sl3(r), ghi_chu=r[6] if len(r) > 6 else "")
for k in cols3:
    check(f"PL3 {k}", sum(u["so_lieu"][k] for u in units if u["phu_luc"] == "3"), tong_hop["3"]["tong"][k])

# ---------------- Phụ lục 4A/4B/4C/4D: Giáo dục ----------------
PL4 = "Phu-luc-4-bien-che-giao-duc-nam-hoc-26-27.docx"
for code, ti, cols, nhom_ten in [
    ("4A", 1, ["so_truong", "quan_ly", "giao_vien", "gv_chinh_thuc", "gv_doi_du", "cm_dung_chung", "tong_giao"], "Trường Mầm non"),
    ("4B", 3, ["so_truong", "quan_ly", "doi", "giao_vien", "gv_chinh_thuc", "gv_doi_du", "cm_dung_chung", "tong_giao"], "Trường Tiểu học"),
    ("4C", 5, ["so_truong", "quan_ly", "doi", "giao_vien", "gv_chinh_thuc", "gv_doi_du", "cm_dung_chung", "tong_giao"], "Trường THCS"),
]:
    R = table_rows(PL4, ti)[2:]
    tot = R[0]
    off = len(tot) - (len(cols) + 2)  # dòng TỔNG có thể gộp ô STT

    def sl4(r, o=0):
        return {k: num(r[i + 2 + o]) for i, k in enumerate(cols)}

    tong_hop[code] = {"tong": sl4(tot, off)}
    for r in R[1:]:
        ten = r[1] if r[1].lower().startswith(("xã", "phường")) else f"Xã {r[1]}"
        add(code, nhom_ten, r[0], f"{nhom_ten} - {ten}", sl4(r), xa=ten)
    for k in cols:
        check(f"PL{code} {k}", sum(u["so_lieu"][k] for u in units if u["phu_luc"] == code), tong_hop[code]["tong"][k])

R = table_rows(PL4, 7)[2:]
r = R[0]
sl4d = {k: num(r[i + 1]) for i, k in enumerate(
    ["so_truong", "quan_ly", "giao_vien", "gv_chinh_thuc", "gv_doi_du", "vtvl_ho_tro", "tong_giao", "hop_dong_235"])}
add("4D", "Trường THPT", "", r[0], sl4d)
tong_hop["4D"] = {"tong": sl4d}

# Đối chiếu chéo: PL2 mục "Mầm non, phổ thông các cấp" = PL4A..4D
pl2 = {u["ten"]: u["so_lieu"] for u in units if u["phu_luc"] == "2"}
for ten2, code in [("Biên chế bậc học Mầm non", "4A"), ("Biên chế bậc học tiểu học", "4B"),
                   ("Biên chế bậc học Trung học cơ sở", "4C"), ("Biên chế bậc học Trung học phổ thông", "4D")]:
    check(f"PL2 '{ten2}' vs PL{code}", tong_hop[code]["tong"]["tong_giao"], pl2[ten2]["tong_giao"])

# Đối chiếu với thân Quyết định (Điều 1)
check("QĐ: giao các cơ quan, đơn vị SNCL", tong_hop["2"]["tong"]["tong_giao"], 24962)
check("QĐ: tổng SNCL kể cả dự phòng", tong_hop["2"]["tong"]["tong_giao"] + tong_hop["2"]["du_phong"], 25526)
check("QĐ: tự đảm bảo một phần", tong_hop["2"]["tong"]["tu_dam_bao"], 695)

data = {
    "van_ban": VAN_BAN,
    "phu_luc_ten": PHU_LUC_TEN,
    "tong_hop": tong_hop,
    "units": units,
}
OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"OK: {len(units)} dòng đơn vị -> {OUT.relative_to(BASE)}")
for pl in PHU_LUC_TEN:
    print(f"  PL{pl}: {sum(1 for u in units if u['phu_luc'] == pl)} dòng")
