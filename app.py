# -*- coding: utf-8 -*-
"""
Ứng dụng Web Dashboard & API Rà soát Chuyên môn Giờ làm việc và Phân bổ Nhân sự VTVL
(khối sở, ban, ngành và xã, phường - đối chiếu biên chế giao theo QĐ 2398/QĐ-UBND).

Chạy local:
  python app.py            -> http://127.0.0.1:8050

Deploy Vercel: Vercel tự nhận biến `app` (FastAPI) trong app.py.
  - Trên Vercel chỉ ghi được vào /tmp nên file tải lên / báo cáo được lưu tại /tmp/vtvl.
  - API phân tích theo đường dẫn chỉ cho phép file nằm trong thư mục tải lên,
    trừ khi đặt biến môi trường ALLOW_LOCAL_PATHS=1 (chỉ dùng khi chạy trên máy cá nhân).
"""

import json
import os
import zlib
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

from core.audit_pipeline import run_full_audit
from exporters.excel_report_builder import build_excel_audit_report

BASE_DIR = Path(__file__).resolve().parent
IS_VERCEL = bool(os.environ.get("VERCEL"))

# Thư mục ghi được: /tmp trên Vercel, thư mục dự án khi chạy local (có thể ghi đè bằng VTVL_DATA_DIR)
DATA_DIR = Path(os.environ.get("VTVL_DATA_DIR") or ("/tmp/vtvl" if IS_VERCEL else BASE_DIR))
UPLOAD_DIR = DATA_DIR / "uploads"
EXPORT_DIR = DATA_DIR / "ket_qua_ra_soat"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# Cho phép đọc file theo đường dẫn bất kỳ trên máy (chỉ khi chạy local, không bật trên Vercel)
ALLOW_LOCAL_PATHS = os.environ.get("ALLOW_LOCAL_PATHS", "0" if IS_VERCEL else "1") == "1"

app = FastAPI(title="VTVL Workload & Headcount Auditor")


class AuditPathRequest(BaseModel):
    file_path: str


def _resolve_allowed_path(file_path: str) -> Path:
    """Chặn đọc file ngoài thư mục tải lên khi không bật ALLOW_LOCAL_PATHS."""
    p = Path(file_path).expanduser()
    if not p.is_absolute():
        # Tên file tương đối luôn hiểu là file trong thư mục tải lên
        return (UPLOAD_DIR / p.name).resolve()
    if ALLOW_LOCAL_PATHS:
        return p
    resolved = p.resolve()
    if UPLOAD_DIR.resolve() not in resolved.parents:
        raise HTTPException(
            status_code=403,
            detail="Chỉ phân tích được file đã tải lên qua nút 'Chọn file (.xlsx)'.",
        )
    return resolved


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = BASE_DIR / "templates" / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.post("/api/audit-path")
async def audit_by_path(req: AuditPathRequest):
    path = _resolve_allowed_path(req.file_path)
    try:
        result = run_full_audit(str(path))
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/audit-upload")
async def audit_upload(request: Request, filename: str = Query("uploaded_vtvl.xlsx")):
    try:
        body = await request.body()
        safe_name = Path(filename).name
        saved_path = UPLOAD_DIR / safe_name
        saved_path.write_bytes(body)
        result = run_full_audit(str(saved_path))
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


MAX_PAYLOAD_BYTES = 120 * 1024 * 1024  # giới hạn sau giải nén (chống "bom nén")


async def _read_sheets_payload(request: Request) -> Dict[str, Any]:
    """Đọc dữ liệu sheet do trình duyệt trích từ file Excel (JSON, có thể nén gzip)."""
    body = await request.body()
    if body[:2] == b"\x1f\x8b":
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        body = d.decompress(body, MAX_PAYLOAD_BYTES)
        if d.unconsumed_tail:
            raise HTTPException(status_code=413, detail="Dữ liệu sau giải nén vượt giới hạn cho phép.")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Dữ liệu gửi lên không phải JSON hợp lệ.")
    if not isinstance(payload, dict) or not isinstance(payload.get("sheets"), dict):
        raise HTTPException(status_code=400, detail="Dữ liệu gửi lên thiếu phần 'sheets'.")
    return payload


def _payload_file_name(payload: Dict[str, Any]) -> str:
    return Path(str(payload.get("file_name") or "bo_bieu_vtvl.xlsx")).name


@app.post("/api/audit-sheets")
async def audit_sheets(request: Request):
    """Phân tích từ dữ liệu sheet trích trên trình duyệt (không gửi cả file -> chạy được trên Vercel)."""
    payload = await _read_sheets_payload(request)
    try:
        result = run_full_audit(_payload_file_name(payload), payload)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/export-excel-sheets")
async def export_excel_sheets(request: Request):
    payload = await _read_sheets_payload(request)
    file_name = _payload_file_name(payload)
    try:
        result = run_full_audit(file_name, payload)
        out_file = EXPORT_DIR / f"Bao_cao_Ra_soat_Chuyen_mon_Gio_VTVL_{Path(file_name).stem}.xlsx"
        build_excel_audit_report(result, str(out_file))
        return FileResponse(
            path=str(out_file),
            filename=out_file.name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/export-excel")
async def export_excel(file_path: str = Query(...)):
    path = _resolve_allowed_path(file_path)
    try:
        result = run_full_audit(str(path))
        out_file = EXPORT_DIR / f"Bao_cao_Ra_soat_Chuyen_mon_Gio_VTVL_{path.stem}.xlsx"
        build_excel_audit_report(result, str(out_file))
        return FileResponse(
            path=str(out_file),
            filename=out_file.name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8050)
