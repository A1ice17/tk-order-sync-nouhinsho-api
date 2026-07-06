from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from .generator import issue_date_text
from .models import Order
from .rules import format_phone, format_postal_code, normalize_product_display, resolve_sku


JP_FONT = "HeiseiKakuGo-W5"
PAGE_W, PAGE_H = A4


def _ensure_fonts() -> None:
    if JP_FONT not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(JP_FONT))


def _draw_text(c: canvas.Canvas, x: float, y: float, text: str, size: float = 9, *, bold: bool = False) -> None:
    c.setFont(JP_FONT, size)
    c.drawString(x, y, text)


def _draw_wrapped(c: canvas.Canvas, x: float, y: float, text: str, width_chars: int, size: float = 8, leading: float = 10) -> float:
    lines: list[str] = []
    for part in str(text or "").splitlines() or [""]:
        lines.extend(wrap(part, width=width_chars, break_long_words=True) or [""])
    for line in lines:
        _draw_text(c, x, y, line, size)
        y -= leading
    return y


def write_pdf(output_path: str | Path, order: Order, *, issue_date: str | None = None) -> dict:
    _ensure_fonts()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    product = normalize_product_display(order.product_name, order.care, source=order.source)
    sku = resolve_sku(order.product_name, order.care, order.sku)
    if not sku:
        raise ValueError(f"订单 {order.order_no} 缺少SKU，脚本不会擅自猜测。")

    c = canvas.Canvas(str(output), pagesize=A4)
    c.setTitle(output.stem)
    c.setFillColor(colors.black)

    _draw_text(c, PAGE_W - 162, PAGE_H - 44, f"発行日:{issue_date_text(issue_date)}", 8)
    _draw_text(c, PAGE_W / 2 - 24, PAGE_H - 64, "納品書", 14)

    _draw_text(c, 82, PAGE_H - 112, f"{order.recipient}　様", 9)

    company_x = 338
    company_y = PAGE_H - 116
    for line in [
        "〒111-0053",
        "東京都台東区浅草橋５丁目４番５号",
        "ハシモトビル703号室",
        "株式会社ピー・エフ・シー",
    ]:
        _draw_text(c, company_x, company_y, line, 8)
        company_y -= 18

    _draw_text(c, 74, PAGE_H - 274, "この度はご注文いただきありがとうございます。下記の通り納品させていただきます。", 8)
    _draw_text(c, 74, PAGE_H - 314, f"注文番号: {order.order_no}", 7)
    _draw_text(c, 74, PAGE_H - 328, f"注文日時: {order.order_datetime}", 7)

    ship_x = 335
    ship_y = PAGE_H - 314
    for line in [
        "配送先：",
        f"〒{format_postal_code(order.postal_code)}",
        order.address,
        f"TEL : {format_phone(order.phone)}",
        f"{order.recipient}　様",
    ]:
        ship_y = _draw_wrapped(c, ship_x, ship_y, line, 32, 7, 10)

    _draw_text(c, PAGE_W - 92, PAGE_H - 410, "注文数", 7)

    table_x = 66
    table_y = PAGE_H - 454
    table_w = 464
    header_h = 32
    row_h = 50
    col_w = [116, 256, 58, 34]

    c.setFillColor(colors.black)
    c.rect(table_x, table_y, table_w, header_h, fill=1, stroke=1)
    c.setFillColor(colors.white)
    headers = ["注文日時\n(注文番号)", "品名", "入数X注文数", "合計数"]
    x = table_x
    for idx, title in enumerate(headers):
        for line_no, line in enumerate(title.split("\n")):
            _draw_text(c, x + 8, table_y + 19 - line_no * 10, line, 7)
        x += col_w[idx]

    c.setFillColor(colors.black)
    x = table_x
    for w in col_w:
        c.rect(x, table_y - row_h, w, row_h, fill=0, stroke=1)
        x += w

    _draw_wrapped(c, table_x + 10, table_y - 18, f"{order.order_datetime}\n({order.order_no})", 18, 6.5, 9)
    _draw_wrapped(c, table_x + col_w[0] + 6, table_y - 16, f"{product}\n商品管理番号:{sku}", 52, 6.2, 8.5)
    _draw_text(c, table_x + col_w[0] + col_w[1] + 12, table_y - 24, f"{order.quantity} X {order.quantity}", 6.5)
    _draw_text(c, table_x + col_w[0] + col_w[1] + col_w[2] + 18, table_y - 24, str(order.quantity), 6.5)

    notes_y = table_y - row_h - 18
    notes = [
        "【備考】",
        "・商品ならびに発送には細心の注意を払っておりますが、万が一、事故品、欠品などございましたらお知らせください。",
        "・保証について・",
        "・商品により保証内容が異なります。「https://sekido-rc.com/?mode=f94」よりご確認ください。こちらのURLに記載のない商品は、商品到着日より7日以内の商品に限り初期の不具合が確認された場合のみ商品の交換を承ります。",
        "・お客様の不適切な使用方法による故障•破損•紛失は、保証の対象外となっております。",
        "・全ての判断は株式会社セキドに帰属します。",
    ]
    for note in notes:
        notes_y = _draw_wrapped(c, 70, notes_y, note, 88, 6, 8)

    c.showPage()
    c.save()
    return {"order_no": order.order_no, "product": product, "sku": sku, "output": str(output)}
