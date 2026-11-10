# -*- coding: utf-8 -*-
"""
Bộ phân tích và nhận diện Ban / Bộ phận / Khối từ Mã VTVL và Tên VTVL.
Hỗ trợ cả mô hình chính quyền địa phương 2 cấp (Đảng ủy, MTTQ, HĐND, UBND) và Sở/Ngành, Đơn vị sự nghiệp.
"""

import re
from typing import Dict, List, Tuple

DEPT_MAPPING: Dict[str, str] = {
    "TT": "Thường trực Đảng ủy",
    "XDĐ": "Ban Xây dựng Đảng",
    "XDD": "Ban Xây dựng Đảng",
    "TC": "Ban Tổ chức",
    "TG": "Ban Tuyên giáo và Dân vận",
    "DV": "Ban Dân vận",
    "NC": "Ban Nội chính",
    "UBKT": "Cơ quan Ủy ban Kiểm tra",
    "KT": "Cơ quan Ủy ban Kiểm tra",
    "VP": "Văn phòng Đảng ủy",
    "VPĐU": "Văn phòng Đảng ủy",
    "CTUBMTTQ": "Cơ quan Ủy ban MTTQ & Đoàn thể",
    "PCTUBMTTQ": "Cơ quan Ủy ban MTTQ & Đoàn thể",
    "UBMTTQ": "Cơ quan Ủy ban MTTQ & Đoàn thể",
    "MTTQ": "Cơ quan Ủy ban MTTQ & Đoàn thể",
    "TTCT": "Trung tâm Chính trị",
    "HĐND": "Thường trực & các Ban HĐND",
    "HDND": "Thường trực & các Ban HĐND",
    "UBND": "Lãnh đạo UBND",
    "VPHĐND": "Văn phòng HĐND & UBND",
    "VPUBND": "Văn phòng HĐND & UBND",
    "VHXH": "Phòng Văn hóa - Xã hội",
    "KTHT": "Phòng Kinh tế, Hạ tầng & Đô thị",
    "TTHCC": "Trung tâm Phục vụ Hành chính công",
}


# ---------------------------------------------------------------------------
# Phân loại khối đơn vị của file bộ biểu
#   "dang"        : Đảng ủy xã/phường, cơ quan Tỉnh ủy, MTTQ & đoàn thể -> giữ nguyên cách nhận diện cũ
#   "chinh_quyen" : Sở/ban/ngành, UBND-HĐND xã, đơn vị sự nghiệp (trạm y tế, trường, trung tâm...)
# ---------------------------------------------------------------------------
ORG_DANG = "dang"
ORG_CHINH_QUYEN = "chinh_quyen"

_DANG_ORG_KEYWORDS = [
    "đảng ủy", "đảng uỷ", "đảng bộ", "tỉnh ủy", "tỉnh uỷ", "huyện ủy", "thành ủy",
    "mặt trận tổ quốc", "mttq", "đoàn thanh niên", "hội liên hiệp phụ nữ", "hội nông dân",
    "hội cựu chiến binh", "công đoàn",
]
# Ký hiệu trong mã VTVL chỉ dùng ở khối Đảng/MTTQ
_DANG_TOKENS = {"TT", "XDĐ", "XDD", "TC", "TG", "DV", "NC", "UBKT", "KT", "VP", "VPĐU",
                "CTUBMTTQ", "PCTUBMTTQ", "UBMTTQ", "MTTQ", "TTCT"}
# Ký hiệu trong mã VTVL của khối chính quyền cấp xã
_CHINH_QUYEN_TOKENS = {"HĐND", "HDND", "UBND", "VPHĐND", "VPUBND", "VHXH", "KTHT", "TTHCC"}


def detect_org_type(co_quan: str, ma_vtvl_list: List[str]) -> str:
    """Xác định file thuộc khối Đảng hay khối chính quyền/sự nghiệp."""
    cq = (co_quan or "").lower()
    if any(kw in cq for kw in _DANG_ORG_KEYWORDS):
        return ORG_DANG
    tokens = []
    for code in ma_vtvl_list:
        parts = str(code).strip().split("_")
        if len(parts) >= 2:
            tok = parts[1].upper()
            tokens.append("TT" if re.match(r"^TT\d*$", tok) else tok)
    if tokens:
        dang_share = sum(1 for t in tokens if t in _DANG_TOKENS or "MTTQ" in t) / len(tokens)
        if dang_share >= 0.5:
            return ORG_DANG
    if not cq and not tokens:
        return ORG_DANG  # không đủ thông tin: giữ cách nhận diện cũ
    return ORG_CHINH_QUYEN


# Bộ phận được nêu trực tiếp trong tên chức danh (khối chính quyền / sự nghiệp).
# (pattern, nhãn cố định | None = lấy cụm khớp)
_NAMED_UNIT_PATTERNS = [
    (r"\bvăn phòng (hđnd|ubnd|hội đồng nhân dân|ủy ban nhân dân|uỷ ban nhân dân)\b", "Văn phòng HĐND & UBND"),
    (r"\bvăn phòng sở\b", "Văn phòng Sở"),
    (r"\bvăn phòng ban\b", "Văn phòng Ban"),
    (r"\b(phòng (?!thuộc\b|chống\b|ngừa\b|cháy\b|bệnh\b)[^,;()]+)", None),
    (r"\b(ban chỉ huy quân sự[^,;()]*)", None),
    (r"\b(chi cục (?!trưởng\b|phó\b)[^,;()]+)", None),
    (r"\b(trạm (?!trưởng\b)[^,;()]+)", None),
    (r"\b(trung tâm [^,;()]+)", None),
    (r"\b(trường (?!hợp\b)[^,;()]+)", None),
]
_SCHOOL_KEYWORDS = ["hiệu trưởng", "giáo viên", "tổng phụ trách đội", "bảo mẫu", "cấp dưỡng"]
_HEALTH_KEYWORDS = ["bác sĩ", "y sĩ", "điều dưỡng", "hộ sinh", "dược sĩ", "dược sỹ", "kỹ thuật viên y", "trạm trưởng"]

# Nhóm vị trí việc làm theo Nghị định 62/2020/NĐ-CP (dùng khi chức danh không nêu bộ phận)
NHOM_LANH_DAO = ("LDQL", "Nhóm Lãnh đạo, quản lý")
NHOM_DUNG_CHUNG = ("CMDC", "Nhóm Chuyên môn dùng chung")
NHOM_HO_TRO = ("HTPV", "Nhóm Hỗ trợ, phục vụ")
NHOM_CHUYEN_NGANH = ("CMCN", "Nhóm Chuyên môn chuyên ngành")

_LEADER_RE = re.compile(
    r"^(phó )?(giám đốc|chủ tịch|trưởng|chánh|chi cục trưởng|hiệu trưởng|trạm trưởng|đội trưởng|đội phó|chỉ huy (trưởng|phó))"
)
_HO_TRO_KEYWORDS = ["thủ quỹ", "nhân viên phục vụ", "lái xe", "bảo vệ", "tạp vụ", "nhân viên kỹ thuật"]
_DUNG_CHUNG_KEYWORDS = [
    "hành chính - văn phòng", "hành chính – văn phòng", "hành chính, văn phòng", "tổng hợp", "văn thư", "lưu trữ",
    "kế toán", "tài chính", "pháp chế", "thanh tra", "quản trị công sở", "quản lý tài sản", "công nghệ thông tin",
    "chuyển đổi số", "thi đua", "khen thưởng", "tổ chức cán bộ", "kiểm soát thủ tục hành chính",
    "tiếp công dân", "khiếu nại", "tố cáo", "phòng chống tham nhũng", "phòng, chống tham nhũng",
    "quản lý đầu tư",
]


def _named_unit(name_lower: str, name_orig: str = ""):
    for pattern, fixed in _NAMED_UNIT_PATTERNS:
        m = re.search(pattern, name_lower)
        if m:
            # Lấy đúng chữ hoa/thường từ tên gốc (lower() giữ nguyên độ dài chuỗi tiếng Việt)
            src = name_orig if len(name_orig) == len(name_lower) else name_lower
            label = fixed if fixed else src[m.start(1):m.end(1)]
            label = re.sub(r"\s+", " ", label).strip(" -–")
            return label[:1].upper() + label[1:]
    if any(k in name_lower for k in _SCHOOL_KEYWORDS):
        return "Trường học"
    if any(k in name_lower for k in _HEALTH_KEYWORDS):
        return "Trạm Y tế / Cơ sở y tế"
    return None


def _nhom_nd62(name_lower: str) -> Tuple[str, str]:
    if _LEADER_RE.search(name_lower):
        return NHOM_LANH_DAO
    if any(k in name_lower for k in _HO_TRO_KEYWORDS):
        return NHOM_HO_TRO
    if any(k in name_lower for k in _DUNG_CHUNG_KEYWORDS):
        return NHOM_DUNG_CHUNG
    return NHOM_CHUYEN_NGANH


def normalize_dept_code(label: str) -> str:
    words = re.findall(r"[A-Za-zÀ-ỹĐđ0-9]+", label)
    return "".join(w[0].upper() for w in words)[:10] or "KHAC"


def parse_department_chinh_quyen(ma_vtvl: str, ten_vtvl: str = "") -> Tuple[str, str]:
    """
    Khối chính quyền / sự nghiệp (bộ biểu không có cột Phòng/Bộ phận):
      1. Ký hiệu chính quyền xã trong mã VTVL (HĐND, UBND, VHXH, KTHT, TTHCC...)
      2. Bộ phận nêu trong tên chức danh (Văn phòng Sở, Phòng ..., Chi cục ..., Trạm ..., Trung tâm ..., Trường ...)
      3. Nhóm vị trí việc làm theo NĐ 62/2020 (Lãnh đạo, quản lý / Chuyên môn chuyên ngành / dùng chung / Hỗ trợ, phục vụ)
    """
    parts = str(ma_vtvl or "").strip().split("_")
    if len(parts) >= 2 and parts[1].upper() in _CHINH_QUYEN_TOKENS:
        token = parts[1].upper()
        norm = {"HDND": "HĐND", "VPUBND": "VPHĐND"}.get(token, token)
        return (norm, DEPT_MAPPING[token])
    name_lower = (ten_vtvl or "").lower().strip()
    unit = _named_unit(name_lower, (ten_vtvl or "").strip())
    # Lãnh đạo Văn phòng/Phòng xếp vào nhóm Lãnh đạo, quản lý (tránh tách nhóm 1-2 người)
    if unit and _LEADER_RE.search(name_lower) and unit.lower().startswith(("văn phòng", "phòng")):
        return NHOM_LANH_DAO
    if unit:
        return (normalize_dept_code(unit), unit)
    return _nhom_nd62(name_lower)


def classify_role_level_chinh_quyen(ten_vtvl: str = "") -> Tuple[str, str]:
    """Cấp chức danh cho khối chính quyền / sự nghiệp."""
    name = (ten_vtvl or "").lower().strip()
    is_pho = name.startswith("phó ") or name.startswith(("đội phó", "chỉ huy phó"))
    don_vi = re.search(r"^(phó )?(giám đốc|chủ tịch|chi cục trưởng|hiệu trưởng|trạm trưởng|chánh thanh tra)", name) \
        or re.search(r"^(phó )?trưởng ban\b", name)
    bo_phan = re.search(r"^(phó )?(trưởng phòng|chánh văn phòng|trưởng khoa|tổ trưởng)|^đội (trưởng|phó)|^chỉ huy (trưởng|phó)", name)
    if don_vi:
        return ("Lãnh đạo đơn vị (cấp phó)", "PP1 hoặc PP1+PP2") if is_pho else ("Lãnh đạo đơn vị (cấp trưởng)", "PP1")
    if bo_phan:
        return ("Lãnh đạo phòng/bộ phận (cấp phó)", "PP1 hoặc PP1+PP2") if is_pho \
            else ("Lãnh đạo phòng/bộ phận (cấp trưởng)", "PP1 hoặc PP1+PP2")
    if any(k in name for k in _HO_TRO_KEYWORDS):
        return ("Hỗ trợ, phục vụ", "PP2 (hoặc hợp đồng NĐ 111/2022)")
    return ("Chuyên môn, nghiệp vụ", "PP2")


def parse_department(ma_vtvl: str, ten_vtvl: str = "", org_type: str = ORG_DANG) -> Tuple[str, str]:
    """
    Trả về (ma_ban_chuan, ten_ban_hien_thi) từ mã VTVL và tên VTVL.
    Ví dụ:
      'A27.103_XDĐ_CV01' -> ('XDĐ', 'Ban Xây dựng Đảng')
      'A27.103_KT_KTV'   -> ('UBKT', 'Cơ quan Ủy ban Kiểm tra')
      'I27.103_CTUBMTTQ' -> ('MTTQ', 'Cơ quan Ủy ban MTTQ & Đoàn thể')
    """
    if org_type == ORG_CHINH_QUYEN:
        return parse_department_chinh_quyen(ma_vtvl, ten_vtvl)
    if not ma_vtvl:
        return ("KHAC", "Bộ phận khác")

    code = str(ma_vtvl).strip()
    parts = code.split("_")
    unit_prefix = parts[0] if parts else ""

    if len(parts) >= 2:
        token = parts[1].upper()
        # Gom nhóm TT01, TT02 -> TT
        if re.match(r"^TT\d*$", token):
            return ("TT", DEPT_MAPPING["TT"])
        # Gom nhóm KT (Kiểm tra viên) vào UBKT
        if token in ("UBKT", "KT"):
            return ("UBKT", DEPT_MAPPING["UBKT"])
        # Gom nhóm MTTQ
        if "MTTQ" in token or unit_prefix.startswith("I"):
            return ("MTTQ", DEPT_MAPPING["MTTQ"])
        if token in DEPT_MAPPING:
            norm_code = "XDĐ" if token == "XDD" else token
            return (norm_code, DEPT_MAPPING[token])

    # Fallback dựa trên tên VTVL
    name_lower = (ten_vtvl or "").lower()
    if "bí thư" in name_lower:
        return ("TT", DEPT_MAPPING["TT"])
    if "xây dựng đảng" in name_lower or "tổ chức" in name_lower or "tuyên giáo" in name_lower or "dân vận" in name_lower:
        return ("XDĐ", DEPT_MAPPING["XDĐ"])
    if "kiểm tra" in name_lower:
        return ("UBKT", DEPT_MAPPING["UBKT"])
    if "văn phòng" in name_lower or "cơ yếu" in name_lower or "văn thư" in name_lower or "thủ quỹ" in name_lower:
        return ("VP", DEPT_MAPPING["VP"])
    if "mặt trận" in name_lower or "mttq" in name_lower or "chính trị - xã hội" in name_lower:
        return ("MTTQ", DEPT_MAPPING["MTTQ"])

    if len(parts) >= 2:
        return (parts[1].upper(), f"Bộ phận {parts[1].upper()}")
    return ("KHAC", "Bộ phận khác")


def classify_role_level(ma_vtvl: str, ten_vtvl: str = "", org_type: str = ORG_DANG) -> Tuple[str, str]:
    """
    Phân loại nhóm chức danh để kiểm tra phương pháp định biên (PP1, PP1+PP2, PP2).
    Trả về (loai_vi_tri, phuong_phap_chuan_goi_y)
    """
    if org_type == ORG_CHINH_QUYEN:
        return classify_role_level_chinh_quyen(ten_vtvl)
    name = (ten_vtvl or "").lower().strip()
    code = (ma_vtvl or "").upper().strip()

    # Cấp trưởng / Thường trực
    if any(
        kw in name
        for kw in [
            "bí thư",
            "trưởng ban",
            "chủ nhiệm ủy ban kiểm tra",
            "chánh văn phòng",
            "chủ tịch ủy ban mttq",
            "chủ tịch hđnd",
            "chủ tịch ubnd",
            "giám đốc",
            "trưởng phòng",
        ]
    ) and not any(p in name for p in ["phó trưởng", "phó chủ nhiệm", "phó chánh", "phó chủ tịch", "phó giám đốc"]):
        if "phó bí thư" in name:
            return ("Thường trực (Cấp phó)", "PP1")
        return ("Lãnh đạo cấp trưởng / Thường trực", "PP1")

    # Cấp phó
    if any(
        kw in name
        for kw in [
            "phó trưởng ban",
            "phó chủ nhiệm",
            "phó chánh văn phòng",
            "phó chủ tịch",
            "cấp phó",
            "phó giám đốc",
            "phó trưởng phòng",
        ]
    ):
        return ("Lãnh đạo cấp phó", "PP1 hoặc PP1+PP2")

    # Ủy viên UBKT chuyên trách
    if "ủy viên ủy ban kiểm tra" in name or code.endswith("_UV"):
        return ("Ủy viên chuyên trách", "PP2 (hoặc PP1 theo cơ cấu)")

    # Chuyên viên, kiểm tra viên, kế toán, văn thư, cơ yếu...
    return ("Chuyên môn, nghiệp vụ / Hỗ trợ", "PP2")
