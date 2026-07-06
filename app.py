from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from nouhinsho.generator import GenerationError, generate_pdf_zip, generate_zip
from nouhinsho.models import Order


allowed_origins = [
    item.strip()
    for item in os.getenv("ALLOWED_ORIGINS", "*").split(",")
    if item.strip()
]

app = FastAPI(title="Nouhinsho Generator API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("NOUHINSHO_API_KEY", "").strip()
MAX_ORDERS = int(os.getenv("NOUHINSHO_MAX_ORDERS", "300"))


def verify_api_key(value: str | None) -> None:
    if API_KEY and value != API_KEY:
        raise HTTPException(status_code=401, detail="API 密钥不正确。")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "nouhinsho-generator", "status": "ok"}


@app.get("/api/nouhinsho/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/nouhinsho/generate")
async def generate_nouhinsho(
    template: UploadFile = File(...),
    orders: str = Form(...),
    issue_date: str | None = Form(None),
    x_api_key: str | None = Header(None),
) -> Response:
    verify_api_key(x_api_key)

    try:
        payload = json.loads(orders)
        items = payload.get("orders", payload if isinstance(payload, list) else [])
        parsed_orders = [Order(**item) for item in items]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"订单数据读取失败：{exc}") from exc

    if not parsed_orders:
        raise HTTPException(status_code=400, detail="没有可生成的订单。")
    if len(parsed_orders) > MAX_ORDERS:
        raise HTTPException(status_code=400, detail=f"单次最多生成 {MAX_ORDERS} 条订单。")

    with tempfile.TemporaryDirectory(prefix="nouhinsho_vercel_") as workdir:
        temp_path = Path(workdir)
        template_path = temp_path / "template.docx"
        zip_path = temp_path / "納品書_一括出力.zip"
        template_path.write_bytes(await template.read())

        try:
            generate_zip(template_path, parsed_orders, zip_path, issue_date=issue_date)
        except (GenerationError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"生成失败：{exc}") from exc

        data = zip_path.read_bytes()

    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="nouhinsho.zip"'},
    )


@app.post("/api/nouhinsho/generate-pdf")
async def generate_nouhinsho_pdf(
    template: UploadFile = File(...),
    orders: str = Form(...),
    issue_date: str | None = Form(None),
    x_api_key: str | None = Header(None),
) -> Response:
    verify_api_key(x_api_key)

    try:
        payload = json.loads(orders)
        items = payload.get("orders", payload if isinstance(payload, list) else [])
        parsed_orders = [Order(**item) for item in items]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"订单数据读取失败：{exc}") from exc

    if not parsed_orders:
        raise HTTPException(status_code=400, detail="没有可生成的订单。")
    if len(parsed_orders) > MAX_ORDERS:
        raise HTTPException(status_code=400, detail=f"单次最多生成 {MAX_ORDERS} 条订单。")

    with tempfile.TemporaryDirectory(prefix="nouhinsho_pdf_vercel_") as workdir:
        temp_path = Path(workdir)
        template_path = temp_path / "template.docx"
        zip_path = temp_path / "納品書_PDF_一括出力.zip"
        template_path.write_bytes(await template.read())

        try:
            generate_pdf_zip(template_path, parsed_orders, zip_path, issue_date=issue_date)
        except (GenerationError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"PDF 生成失败：{exc}") from exc

        data = zip_path.read_bytes()

    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="nouhinsho_pdf.zip"'},
    )
