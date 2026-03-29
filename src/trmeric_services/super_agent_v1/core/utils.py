



def slugify(text: str, fallback: str = "presentation") -> str:
    """Convert title/query to a safe snake_case filename."""
    import re as _re
    slug = _re.sub(r"[^\w\s-]", "", text.lower())
    slug = _re.sub(r"[\s-]+", "_", slug).strip("_")
    return (slug[:60] or fallback)

