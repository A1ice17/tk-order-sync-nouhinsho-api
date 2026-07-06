"""Local invoice / delivery-note generator for fixed Japanese DOCX templates."""

__all__ = [
    "generate_zip",
    "generate_pdf_zip",
    "generate_documents",
    "GenerationError",
    "read_orders_from_excel",
    "normalize_product_display",
    "format_phone",
    "resolve_sku",
]


def __getattr__(name: str):
    if name in {"generate_zip", "generate_pdf_zip", "generate_documents", "GenerationError"}:
        from . import generator

        return getattr(generator, name)
    if name == "read_orders_from_excel":
        from .excel_reader import read_orders_from_excel

        return read_orders_from_excel
    if name in {"normalize_product_display", "format_phone", "resolve_sku"}:
        from . import rules

        return getattr(rules, name)
    raise AttributeError(name)
