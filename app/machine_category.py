"""Machine category helpers for DOSE pro."""

MACHINE_CATEGORIES = (
    ("ct_linac", "CT Linac"),
    ("mr_linac", "MR Linac"),
    ("brachy", "Brachytherapy"),
)

CATEGORY_LABELS = dict(MACHINE_CATEGORIES)


def normalize_category(value: str | None) -> str:
    if value in CATEGORY_LABELS:
        return value
    return "ct_linac"


def is_brachy(category: str | None) -> bool:
    return normalize_category(category) == "brachy"


def is_linac(category: str | None) -> bool:
    return normalize_category(category) in ("ct_linac", "mr_linac")
