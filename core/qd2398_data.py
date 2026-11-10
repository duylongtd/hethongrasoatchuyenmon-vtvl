# -*- coding: utf-8 -*-
"""
Tra cứu biên chế giao theo Quyết định số 2398/QĐ-UBND ngày 04/10/2026 của UBND tỉnh Hà Tĩnh
(Phụ lục 1: Công chức; Phụ lục 2: Viên chức; Phụ lục 3: Hội; Phụ lục 4A-4D: Giáo dục năm học 2026-2027).

Dữ liệu nằm trong core/qd2398_data.json, sinh từ các file phụ lục bằng scripts/build_qd2398_data.py.
Nhận diện đơn vị theo thứ tự ưu tiên:
  1. Cột "Cơ quan" tại biểu 1. A1_NhiemVu
  2. Tên file
  3. Nội dung biểu D1 (Nơi tính BC, Nguồn) và tên VTVL tại C1
"""

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DATA_FILE = Path(__file__).resolve().parent / "qd2398_data.json"

PHU_LUC_ORDER = ["1", "2", "3", "4A", "4B", "4C", "4D"]

SO_LIEU_LABELS = {
    "tong_giao": "Tổng giao",
    "chinh_thuc": "Giao chính thức",
    "doi_du": "Giao dôi dư",
    "bien_che": "Biên chế",
    "ho_tro_nsnn": "Hỗ trợ bằng NSNN",
    "so_truong": "Số trường",
    "quan_ly": "Quản lý",
    "doi": "Đội",
    "giao_vien": "Giáo viên",
    "gv_chinh_thuc": "GV chính thức",
    "gv_doi_du": "GV dôi dư",
    "cm_dung_chung": "Chuyên môn dùng chung",
    "vtvl_ho_tro": "VTVL hỗ trợ",
    "hop_dong_111": "HĐ theo NĐ 111/2022",
    "hop_dong_235": "HĐ theo NĐ 235/2026",
    "tu_dam_bao": "Tự đảm bảo kinh phí",
}

# Từ viết tắt hay gặp trong tên cơ quan -> dạng đầy đủ (dùng sinh thêm từ khóa)
ABBREVIATIONS = [
    ("ubnd", "uy ban nhan dan"),
    ("hdnd", "hoi dong nhan dan"),
    ("dbqh", "dai bieu quoc hoi"),
    ("tt", "trung tam"),
    ("bv", "benh vien"),
]

# Tên đơn vị con dùng chung giữa nhiều Sở -> phải ghép tên Sở cha để phân biệt
GENERIC_CHILD_NAMES = {"van phong so", "co quan so"}


def remove_accents(text: str) -> str:
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    norm = unicodedata.normalize("NFD", text)
    return "".join(c for c in norm if unicodedata.category(c) != "Mn")


def normalize_key(text: str) -> str:
    ascii_str = remove_accents(text).lower()
    return re.sub(r"[^a-z0-9]+", " ", ascii_str).strip()


def _strip_xa_prefix(key: str) -> str:
    return re.sub(r"^(xa|phuong)\s+", "", key)


def _expand_abbreviations(key: str) -> List[str]:
    variants = {key}
    for short, full in ABBREVIATIONS:
        for v in list(variants):
            padded = f" {v} "
            if f" {short} " in padded:
                variants.add(padded.replace(f" {short} ", f" {full} ").strip())
            if f" {full} " in padded:
                variants.add(padded.replace(f" {full} ", f" {short} ").strip())
    return list(variants)


@lru_cache(maxsize=1)
def _load() -> Dict[str, Any]:
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Thiếu dữ liệu QĐ 2398/QĐ-UBND: {DATA_FILE}. Chạy: python scripts/build_qd2398_data.py"
        )
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def _unit_keys(u: Dict[str, Any]) -> List[str]:
    """Từ khóa nhận diện của 1 dòng phụ lục. Rỗng = không dùng để nhận diện."""
    if u.get("xa"):
        return [_strip_xa_prefix(normalize_key(u["xa"]))]
    # Dòng tổng hợp của PL2 (Bệnh viện, Trung tâm, Tuyến tỉnh...) và dòng THPT gộp: tên chung chung
    if u["phu_luc"] == "2" and u.get("la_dong_tong_hop"):
        return []
    if u["phu_luc"] == "4D" or u["ten"].lower().startswith("biên chế bậc học"):
        return []
    key = normalize_key(u["ten"])
    if key in GENERIC_CHILD_NAMES and u.get("ten_cha"):
        cha = re.sub(r"^so\s+", "", normalize_key(u["ten_cha"]))
        key = f"{key} {cha}"
    keys = _expand_abbreviations(key)
    # "Lãnh đạo, Văn phòng UBND tỉnh" -> cũng nhận "Văn phòng UBND tỉnh"
    keys += [re.sub(r"^lanh dao\s+", "", k) for k in keys if k.startswith("lanh dao ")]
    return [k for k in set(keys) if len(k) >= 4]


@lru_cache(maxsize=1)
def _index() -> List[Tuple[str, Dict[str, Any]]]:
    idx = []
    for u in _load()["units"]:
        for k in _unit_keys(u):
            idx.append((k, u))
    return idx


def _rank(u: Dict[str, Any]) -> int:
    return PHU_LUC_ORDER.index(u["phu_luc"]) if u["phu_luc"] in PHU_LUC_ORDER else 99


def _find_in_text(text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    norm = f" {normalize_key(text)} "
    if not norm.strip():
        return None
    hits = [(k, u) for k, u in _index() if f" {k} " in norm]
    if not hits:
        return None
    # Ưu tiên từ khóa dài nhất (cụ thể nhất), sau đó theo thứ tự phụ lục (PL1 trước)
    hits.sort(key=lambda h: (-len(h[0]), _rank(h[1])))
    return hits[0]


def _so_lieu_list(so_lieu: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{"nhan": SO_LIEU_LABELS.get(k, k), "gia_tri": v} for k, v in so_lieu.items()]


def _brief(u: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ten": u["ten"],
        "phu_luc": u["phu_luc"],
        "tong_giao": u["so_lieu"].get("tong_giao"),
    }


def lookup_qd2398_by_unit(
    file_name: str,
    co_quan_a1: str = "",
    positions: Optional[List[Dict[str, Any]]] = None,
    d1_rows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Trả về {"info": {...} | None, "chuoi_da_thu": [...]}.
    info chứa biên chế giao của đơn vị theo QĐ 2398/QĐ-UBND và các dòng phụ lục liên quan.
    """
    data = _load()
    vb = data["van_ban"]

    sources: List[Tuple[str, str]] = []
    if co_quan_a1:
        sources.append(("Cột 'Cơ quan' biểu 1. A1_NhiemVu", co_quan_a1))
    sources.append(("Tên file", Path(file_name).stem))
    extra = []
    for r in (d1_rows or [])[:10]:
        extra += [r.get("noi_tinh_bc") or "", r.get("nguon") or ""]
    for p in (positions or [])[:10]:
        extra.append(p.get("ten_vtvl") or "")
    if any(extra):
        sources.append(("Nội dung biểu D1/C1", " ; ".join(x for x in extra if x)))

    tried = [{"nguon": s, "chuoi": t[:160]} for s, t in sources]
    for source_label, text in sources:
        hit = _find_in_text(text)
        if not hit:
            continue
        key, u = hit
        units = data["units"]
        if u.get("xa"):
            # Cùng xã/phường ở các phụ lục khác (Trạm Y tế, TT Dịch vụ tổng hợp, trường học)
            same = [x for x in units if x.get("xa") and _strip_xa_prefix(normalize_key(x["xa"])) == key]
            same.sort(key=_rank)
            primary = same[0]
            lien_quan = [_brief(x) for x in same[1:]]
            don_vi_con = []
        else:
            primary = u
            lien_quan = []
            don_vi_con = [
                _brief(x) for x in units
                if x["phu_luc"] == u["phu_luc"] and x.get("ten_cha") == u["ten"] and x["nhom"] == u["nhom"]
            ]
        sl = primary["so_lieu"]
        info = {
            "van_ban": f"{vb['ten_ngan']} ngày {vb['ngay']}",
            "ten": primary["ten"],
            "ten_cha": primary.get("ten_cha"),
            "phu_luc": primary["phu_luc"],
            "phu_luc_ten": data["phu_luc_ten"].get(primary["phu_luc"], ""),
            "nhom": primary["nhom"],
            "stt": primary["stt"],
            "tong_giao": sl.get("tong_giao"),
            "chinh_thuc": sl.get("chinh_thuc"),
            "doi_du": sl.get("doi_du"),
            "so_lieu": _so_lieu_list(sl),
            "don_vi_con": don_vi_con,
            "lien_quan": lien_quan,
            "ghi_chu": primary.get("ghi_chu", ""),
            "nguon_nhan_dien": source_label,
            "chuoi_nhan_dien": text[:160],
            "tu_khoa_khop": key,
        }
        return {"info": info, "chuoi_da_thu": tried}

    return {"info": None, "chuoi_da_thu": tried}
