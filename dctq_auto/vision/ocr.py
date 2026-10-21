"""Shared OCR helper with white-on-dark defaults."""
DEFAULT_OCR_CONFIG = {
    "method": "color_text",
    "text_color": "#FFFFFF",
    "background_color": "#202020",
    "border_color": None,
    "color_tolerance": 38,
    "psm": 11,
    "lang": "vie+eng",
}
