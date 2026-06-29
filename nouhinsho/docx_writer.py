from __future__ import annotations

from copy import copy
from pathlib import Path
from typing import Iterable

from docx import Document
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

from .models import Order
from .rules import format_phone, format_postal_code, normalize_product_display, resolve_sku


class TemplateError(ValueError):
    pass


def _all_paragraphs(doc: Document) -> list[Paragraph]:
    return list(doc.paragraphs)


def _set_single_run(paragraph: Paragraph, text: str) -> None:
    """Replace visible text while retaining the original paragraph/run formatting.

    Never use paragraph.text or cell.text here: both reset runs and can alter
    layout in fixed-position Japanese delivery-note templates.
    """
    if paragraph.runs:
        first = paragraph.runs[0]
        first.text = text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(text)


def _set_multiline(paragraph: Paragraph, lines: list[str]) -> None:
    if paragraph.runs:
        first = paragraph.runs[0]
        first.text = ""
        for idx, line in enumerate(lines):
            if idx:
                first.add_break()
            first.add_text(line)
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        run = paragraph.add_run()
        for idx, line in enumerate(lines):
            if idx:
                run.add_break()
            run.add_text(line)


def _find_paragraph(paragraphs: list[Paragraph], *prefixes: str) -> Paragraph | None:
    for paragraph in paragraphs:
        stripped = paragraph.text.strip()
        if any(stripped.startswith(prefix) for prefix in prefixes):
            return paragraph
    return None


def _find_table(doc: Document) -> Table:
    for table in doc.tables:
        all_text = " ".join(cell.text for row in table.rows for cell in row.cells)
        if "注文日時" in all_text and "品名" in all_text:
            return table
    if not doc.tables:
        raise TemplateError("模板内没有找到表格。")
    return doc.tables[0]


def _find_data_row(table: Table):
    for index, row in enumerate(table.rows):
        row_text = " ".join(cell.text for cell in row.cells)
        if "注文日時" in row_text and "品名" in row_text and index + 1 < len(table.rows):
            return table.rows[index + 1]
    if len(table.rows) < 2:
        raise TemplateError("模板表格中没有可填写的数据行。")
    return table.rows[1]


def _first_nonempty_after(paragraphs: list[Paragraph], start: int, count: int) -> list[Paragraph]:
    result: list[Paragraph] = []
    for paragraph in paragraphs[start + 1 :]:
        if paragraph.text.strip():
            result.append(paragraph)
        if len(result) >= count:
            break
    return result


def _shipping_fields(paragraphs: list[Paragraph]) -> tuple[Paragraph, Paragraph, Paragraph, Paragraph] | None:
    for idx, paragraph in enumerate(paragraphs):
        if paragraph.text.strip().startswith("配送先"):
            candidates = _first_nonempty_after(paragraphs, idx, 4)
            if len(candidates) == 4:
                return candidates[0], candidates[1], candidates[2], candidates[3]
    return None


def _set_customer_name(paragraphs: list[Paragraph], recipient: str) -> None:
    # Fixed templates often contain a second, visually positioned customer name
    # outside the normal paragraph flow. Update every standalone recipient-like
    # paragraph, while leaving company and note text untouched.
    for paragraph in paragraphs:
        text = paragraph.text.strip()
        if (
            text.endswith("様")
            and "株式会社" not in text
            and "ください" not in text
            and "お客" not in text
            and len(text) <= 40
        ):
            _set_single_run(paragraph, f"{recipient}　様")


def _replace_table_row(row, order: Order, product_display: str, sku: str) -> None:
    if len(row.cells) < 4:
        raise TemplateError("模板明细表至少需要4列。")
    date_cell, product_cell, quantity_cell, total_cell = row.cells[:4]

    date_para = date_cell.paragraphs[0]
    _set_multiline(date_para, [order.order_datetime, f"（{order.order_no}）"])

    product_para = product_cell.paragraphs[0]
    _set_multiline(product_para, [product_display, f"商品管理番号:{sku}"])
    # Clear only already-existing secondary paragraphs; do not create new ones,
    # so cell dimensions and original paragraph formatting remain intact.
    for extra in product_cell.paragraphs[1:]:
        _set_single_run(extra, "")

    _set_single_run(quantity_cell.paragraphs[0], f"{order.quantity} X {order.quantity}")
    _set_single_run(total_cell.paragraphs[0], str(order.quantity))


def fill_template(template_path: str | Path, output_path: str | Path, order: Order, *, issue_date: str) -> dict:
    product_display = normalize_product_display(order.product_name, order.care, source=order.source)
    sku = resolve_sku(order.product_name, order.care, order.sku)
    if not sku:
        raise ValueError(f"订单 {order.order_no} 缺少SKU，脚本不会擅自猜测。")

    doc = Document(template_path)
    paragraphs = _all_paragraphs(doc)

    issue = _find_paragraph(paragraphs, "発行日")
    if issue is None:
        raise TemplateError("模板中未找到『発行日』字段。")
    _set_single_run(issue, f"発行日:{issue_date}")

    order_no = _find_paragraph(paragraphs, "注文番号")
    order_dt = _find_paragraph(paragraphs, "注文日時")
    if order_no is None or order_dt is None:
        raise TemplateError("模板中未找到『注文番号』或『注文日時』字段。")
    _set_single_run(order_no, f"注文番号: {order.order_no}")
    _set_single_run(order_dt, f"注文日時: {order.order_datetime}")

    fields = _shipping_fields(paragraphs)
    if fields is None:
        raise TemplateError("模板中未找到『配送先』后的邮编/地址/电话/姓名位置。")
    postal, address, phone, recipient = fields
    _set_single_run(postal, f"〒{format_postal_code(order.postal_code)}")
    _set_single_run(address, order.address)
    _set_single_run(phone, f"TEL : {format_phone(order.phone)}")
    _set_single_run(recipient, f"{order.recipient}　様")
    _set_customer_name(paragraphs, order.recipient)

    _replace_table_row(_find_data_row(_find_table(doc)), order, product_display, sku)
    doc.save(output_path)

    return {
        "order_no": order.order_no,
        "product": product_display,
        "sku": sku,
        "output": str(output_path),
    }
