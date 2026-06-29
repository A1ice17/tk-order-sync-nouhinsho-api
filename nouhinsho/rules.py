from __future__ import annotations

import re
import unicodedata
from typing import Optional


SKU_DEFAULTS: dict[tuple[str, str], str] = {
    ("pocket3_standard", "なし"): "D231025010-1",
    ("pocket3_creator", "なし"): "D231025020-1",
    ("pocket4_standard", "なし"): "D260416010-1",
    ("pocket4_standard", "1年版"): "D260416010-2",
    ("pocket4_creator", "なし"): "D260416020-1",
    ("pocket4_creator", "1年版"): "D260416020-2",
    ("mobile8p_standard", "なし"): "D260507010-1",
}


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    return re.sub(r"\s+", " ", text)


def _phone_digits(value: object) -> str:
    """Return normalized digits while surviving Excel numeric cells."""
    text = unicodedata.normalize("NFKC", clean_text(value))
    if not text:
        return ""
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".", 1)[0]
    return "".join(ch for ch in text if ch.isdigit())


def normalize_care(value: object | None) -> str:
    text = clean_text(value)
    if not text:
        return ""
    text = text.replace("DJI Care Refresh", "").replace("：", ":")
    text = text.replace("/", " ").strip(" :-")
    if "2年" in text:
        return "2年版"
    if "1年" in text:
        return "1年版"
    if "なし" in text or text.lower() in {"none", "no", "default", "デフォルト"}:
        return "なし"
    return text


def detect_model_key(product_name: object) -> Optional[str]:
    name = clean_text(product_name).replace("　", " ")
    compact = name.replace(" ", "")
    if "OsmoPocket4" in compact:
        return "pocket4_creator" if "クリエイター" in name else "pocket4_standard"
    if "OsmoPocket3" in compact:
        return "pocket3_creator" if "クリエイター" in name else "pocket3_standard"
    if "OsmoMobile8P" in compact:
        return "mobile8p_standard"
    return None


def canonical_base_name(product_name: object, *, source: str = "") -> str:
    """Short product title for the delivery note.

    Marketing copy and platform title prefixes are intentionally discarded.
    """
    raw = clean_text(product_name)
    compact = raw.replace(" ", "").replace("　", "")
    source = clean_text(source).lower()

    if "OsmoPocket4" in compact:
        if "クリエイター" in raw:
            return "DJI Osmo Pocket 4 クリエイター コンボ"
        # The private-store flow historically uses no space in スタンダードコンボ.
        return "DJI Osmo Pocket 4 スタンダードコンボ" if source in {"private", "私域"} else "DJI Osmo Pocket 4 スタンダード コンボ"
    if "OsmoPocket3" in compact:
        return "DJI Osmo Pocket 3 クリエイター コンボ" if "クリエイター" in raw else "DJI Osmo Pocket 3"
    if "OsmoMobile8P" in compact:
        return "DJI Osmo Mobile 8P スタンダードコンボ"
    if "Osmo360" in compact:
        return "DJI Osmo 360 アドベンチャーコンボ"
    if "MicMini2" in compact:
        return "DJI Mic Mini 2（2 TX + 1 RX + 充電ケース）"
    return raw


def normalize_product_display(product_name: object, care: object | None = None, *, source: str = "") -> str:
    raw = clean_text(product_name)
    care_value = normalize_care(care)
    if not care_value:
        # Product input may already include Care Refresh after a slash.
        care_match = re.search(r"DJI\s*Care\s*Refresh\s*[：:]?\s*([^/]+)", raw, flags=re.I)
        if care_match:
            care_value = normalize_care(care_match.group(1))
        elif "なし" in raw:
            care_value = "なし"
    base = canonical_base_name(raw, source=source)

    # Keep non-camera accessories concise and do not invent a Care field.
    key = detect_model_key(raw)
    if key in {"pocket3_standard", "pocket3_creator", "pocket4_standard", "pocket4_creator", "mobile8p_standard"}:
        if not care_value:
            care_value = "なし"
        return f"{base}/DJI Care Refresh：{care_value}"
    return base


def resolve_sku(product_name: object, care: object | None, explicit_sku: object | None = None) -> str:
    """Use explicit SKU first; known defaults are only fallback values.

    Unknown products intentionally return an empty string so the caller can stop
    rather than silently generating an incorrect delivery note.
    """
    sku = clean_text(explicit_sku)
    if sku:
        return sku
    key = detect_model_key(product_name)
    care_value = normalize_care(care) or "なし"
    return SKU_DEFAULTS.get((key or "", care_value), "")


def format_postal_code(value: object) -> str:
    text = clean_text(value).replace("〒", "").replace("-", "")
    if text.isdigit() and len(text) == 7:
        return f"{text[:3]}-{text[3:]}"
    return clean_text(value).replace("〒", "")


def format_phone(value: object) -> str:
    """Format Japanese phone numbers as 000-0000-0000 when possible.

    This preserves the number; it does not replace it with literal zeroes.
    """
    raw = clean_text(value)
    digits = _phone_digits(value)
    if digits.startswith("0081"):
        digits = "0" + digits[4:]
    if digits.startswith("81"):
        digits = "0" + digits[2:]
    # Excel sometimes stores 08012345678 as the number 8012345678.
    if len(digits) == 10 and not digits.startswith("0") and digits[0] in {"7", "8", "9"}:
        digits = "0" + digits
    if len(digits) == 11:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return raw


def safe_filename(text: object) -> str:
    value = clean_text(text)
    return re.sub(r'[\\/:*?"<>|]', "_", value).replace(" ", "")
