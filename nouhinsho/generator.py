from __future__ import annotations

from datetime import date
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from typing import Iterable
import zipfile

from .docx_writer import fill_template
from .models import Order
from .rules import safe_filename


class GenerationError(RuntimeError):
    pass


def issue_date_text(value: str | None = None) -> str:
    if value:
        # Supports YYYY-MM-DD or already formatted Japanese dates.
        if "年" in value:
            return value
        y, m, d = value.split("-")
        return f"{int(y):04d}年{int(m):02d}月{int(d):02d}日"
    today = date.today()
    return f"{today.year:04d}年{today.month:02d}月{today.day:02d}日"


def prefix_for(source: str) -> str:
    source = source.lower().strip()
    if source in {"temu"}:
        return "Temu"
    if source in {"private", "私域"}:
        return "私域"
    if source in {"aliexpress"}:
        return "Aliexpress"
    return "TK"


def filename_for(order: Order) -> str:
    platform = safe_filename(order.filename_prefix.strip() or prefix_for(order.source))
    return f"納品書_{platform}_{safe_filename(order.order_no)}.docx"


def pdf_filename_for(order: Order) -> str:
    return Path(filename_for(order)).with_suffix(".pdf").name


def validate_orders(orders: Iterable[Order]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for order in orders:
        if not order.order_no:
            errors.append("发现没有订单号的记录。")
        elif order.order_no in seen:
            errors.append(f"订单号重复: {order.order_no}")
        seen.add(order.order_no)
        for name, value in [
            ("收件人", order.recipient),
            ("邮编", order.postal_code),
            ("地址", order.address),
            ("商品名", order.product_name),
        ]:
            if not str(value).strip():
                errors.append(f"订单 {order.order_no} 缺少{name}。")
        if not order.order_datetime:
            errors.append(f"订单 {order.order_no} 缺少注文日時。")
    return errors


def generate_documents(template_path: str | Path, orders: list[Order], output_dir: str | Path, *, issue_date: str | None = None) -> list[dict]:
    errors = validate_orders(orders)
    if errors:
        raise GenerationError("\n".join(errors))
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    issue = issue_date_text(issue_date)
    for order in orders:
        target = output / filename_for(order)
        try:
            result = fill_template(template_path, target, order, issue_date=issue)
        except Exception as exc:
            raise GenerationError(str(exc)) from exc
        results.append(result)
    return results


def generate_zip(template_path: str | Path, orders: list[Order], zip_path: str | Path, *, issue_date: str | None = None) -> list[dict]:
    zip_path = Path(zip_path)
    with TemporaryDirectory(prefix="nouhinsho_") as temp:
        results = generate_documents(template_path, orders, temp, issue_date=issue_date)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for result in results:
                source = Path(result["output"])
                archive.write(source, arcname=source.name)
    return results


def _soffice_path() -> str | None:
    candidates = [
        os.getenv("SOFFICE_BIN", "").strip(),
        "soffice",
        "libreoffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        resolved = candidate if Path(candidate).exists() else shutil.which(candidate)
        if resolved and Path(resolved).exists():
            return resolved
    return None


def convert_docx_to_pdf(docx_path: str | Path, pdf_dir: str | Path) -> Path:
    source = Path(docx_path)
    output = Path(pdf_dir)
    output.mkdir(parents=True, exist_ok=True)
    soffice = _soffice_path()
    if not soffice:
        raise GenerationError("PDF 转换工具 LibreOffice/soffice 未安装或不在 PATH 中。")
    cmd = [
        soffice,
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(output),
        str(source),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90)
    pdf_path = output / source.with_suffix(".pdf").name
    if proc.returncode != 0 or not pdf_path.exists():
        detail = (proc.stderr or proc.stdout or "unknown error").strip()
        raise GenerationError(f"PDF 转换失败：{detail}")
    return pdf_path


def generate_pdf_zip(template_path: str | Path, orders: list[Order], zip_path: str | Path, *, issue_date: str | None = None) -> list[dict]:
    zip_path = Path(zip_path)
    with TemporaryDirectory(prefix="nouhinsho_pdf_") as temp:
        temp_path = Path(temp)
        pdf_dir = temp_path / "pdf"
        results: list[dict]
        if _soffice_path():
            docx_dir = temp_path / "docx"
            results = generate_documents(template_path, orders, docx_dir, issue_date=issue_date)
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
                for index, result in enumerate(results):
                    source = Path(result["output"])
                    pdf_path = convert_docx_to_pdf(source, pdf_dir)
                    archive.write(pdf_path, arcname=pdf_filename_for(orders[index]))
                    result["pdf_output"] = str(pdf_path)
            return results

        from .pdf_writer import write_pdf

        errors = validate_orders(orders)
        if errors:
            raise GenerationError("\n".join(errors))
        pdf_dir.mkdir(parents=True, exist_ok=True)
        results = []
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for order in orders:
                pdf_path = pdf_dir / pdf_filename_for(order)
                result = write_pdf(pdf_path, order, issue_date=issue_date)
                archive.write(pdf_path, arcname=pdf_path.name)
                result["pdf_output"] = str(pdf_path)
                results.append(result)
    return results
