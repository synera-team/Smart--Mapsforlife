"""Ward choices accepted from the business registration Google Form."""

import re

from db import q


# This Form choice is not yet present in the project's map boundary data.
EXTRA_WARDS = (("van-mieu-quoc-tu-giam", "Văn Miếu - Quốc Tử Giám"),)


def registration_wards():
    rows = [(row["slug"], row["name"].removeprefix("Phường ")) for row in
            q("SELECT slug,name FROM wards WHERE type='phuong' AND published=1")]
    return sorted(rows + list(EXTRA_WARDS), key=lambda item: item[1].casefold())


def normalize(value):
    value = re.sub(r"\s*[-–—]\s*", "-", str(value or "").strip()).casefold()
    return re.sub(r"\s+", " ", value)


def registration_ward_slug(value):
    value = normalize(value)
    for slug, name in registration_wards():
        if value in (normalize(slug), normalize(name), normalize(f"Phường {name}")):
            return slug
    return None


def valid_registration_scope(values):
    allowed = {slug for slug, _ in registration_wards()}
    return isinstance(values, list) and bool(values) and all(
        isinstance(value, str) and value in allowed for value in values
    ) and len(set(values)) == len(values)
