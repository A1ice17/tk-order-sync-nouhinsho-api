from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class Order:
    """Normalized order used by the DOCX writer.

    The program never alters order prefixes. For Temu, pass PO-100-... exactly
    as shown on the Temu page.
    """

    source: str
    order_no: str
    order_datetime: str
    recipient: str
    postal_code: str
    address: str
    phone: str
    product_name: str
    care: str = ""
    sku: str = ""
    quantity: int = 1
    filename_prefix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
