from __future__ import annotations

from datetime import date
from pathlib import Path
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
        return "Temu納品書"
    if source in {"private", "私域"}:
        return "私域納品書"
    return "納品書"


def filename_for(order: Order) -> str:
    prefix = order.filename_prefix.strip() or prefix_for(order.source)
    return f"{prefix}_{safe_filename(order.order_no)}_{safe_filename(order.recipient)}.docx"


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
