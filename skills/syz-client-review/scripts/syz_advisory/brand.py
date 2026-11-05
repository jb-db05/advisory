"""The SYZ house style, in one place.

Presentation rules, applied everywhere: white background, Nunito (Bold for
titles, Light for labels), ink #202945, rules and axes in #202945 at 40%
opacity, and flat solid colour throughout -- no shadows, glows, reflections or
gradients.

Where a medium cannot do transparency reliably (HTML email), the 40% rule
colour is used pre-flattened against white by `flatten`, so the value on the
page is still a real, flat colour.
"""

from __future__ import annotations

INK = "#202945"          # Space Blue -- all type
WHITE = "#FFFFFF"
RULE = "#202945"         # drawn at RULE_ALPHA
RULE_ALPHA = 0.4

# Ordered as the house palette is quoted; index 0 is the default accent.
PALETTE: dict[str, str] = {
    "tiger_orange": "#FF6C0E",
    "mango_amber": "#FFA400",
    "gold_yellow": "#FFC545",
    "mint_green": "#3BAF90",
    "teal_green": "#9DD9D2",
    "sky_blue": "#79D6FF",
    "peach_pink": "#E6A4AD",
    "mulberry_pink": "#AC5D85",
    "blueberry_blue": "#4B5F80",
}

# Human labels, for pickers in the UI.
PALETTE_NAMES: dict[str, str] = {
    "tiger_orange": "Tiger Orange",
    "mango_amber": "Mango Amber",
    "gold_yellow": "Gold Yellow",
    "mint_green": "Mint Green",
    "teal_green": "Teal Green",
    "sky_blue": "Sky Blue",
    "peach_pink": "Peach Pink",
    "mulberry_pink": "Mulberry Pink",
    "blueberry_blue": "Blueberry Blue",
}

DEFAULT_ACCENT = "tiger_orange"

# Nunito first; the rest are fallbacks for mail clients, which can only use
# locally installed faces.
FONT_STACK = "'Nunito', 'Nunito Sans', Lato, Calibri, Arial, sans-serif"
BOLD, LIGHT = 700, 300


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    """'#FF6C0E' -> (255, 108, 14)."""
    text = value.lstrip("#")
    return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))


def flatten(colour: str, alpha: float, over: str = WHITE) -> str:
    """A partly transparent colour as the flat hex it would appear as.

    Keeps the "no effects, flat colour only" rule in media without alpha.
    """
    top, bottom = hex_to_rgb(colour), hex_to_rgb(over)
    mixed = tuple(round(b + (t - b) * alpha) for t, b in zip(top, bottom))
    return "#{:02X}{:02X}{:02X}".format(*mixed)


def accent(name: str) -> str:
    """Resolve a palette name, or a literal #rrggbb, to a hex colour."""
    if name.startswith("#"):
        return name.upper()
    return PALETTE.get(name, PALETTE[DEFAULT_ACCENT])


# The 40% rule colour, pre-flattened for HTML email.
RULE_FLAT = flatten(RULE, RULE_ALPHA)
