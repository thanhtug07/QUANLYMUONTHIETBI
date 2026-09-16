# -*- coding: utf-8 -*-
"""
styles/tokens.py — DESIGN TOKENS
================================
Nguồn duy nhất (single source of truth) cho mọi giá trị trực quan:
màu sắc, typography, spacing, radius, shadow.

- Python (Altair / pandas) import trực tiếp các hằng số màu ở đây.
- CSS (`styles/dashboard.css`) KHÔNG hardcode giá trị trực quan: mọi rule
  dùng biến CSS được sinh bởi `css_variables()`.

Bảng màu bám đúng palette của project (7 màu). Các biến "tint" bên dưới
KHÔNG phải màu mới: chúng là chính màu palette với alpha thấp, dùng cho nền
icon chip, trạng thái active/hover — không tạo màu ngoài hệ thống.
"""
from __future__ import annotations

from typing import Dict, Final

# ----------------------------------------------------------------------
# MÀU SẮC — palette duy nhất được phép sử dụng
# ----------------------------------------------------------------------
COLORS: Final[Dict[str, str]] = {
    "bg": "#F0F2F6",           # nền trang
    "surface": "#FFFFFF",      # card / bề mặt chính
    "surface-alt": "#FAFAFA",  # sidebar, nền phụ
    "text": "#31333F",         # chữ chính
    "primary": "#0054A3",      # xanh chính
    "accent": "#3D9DF3",       # xanh nhấn
    "border": "#C9DDF0",       # viền / đường kẻ
}

COLOR_BG: Final[str] = COLORS["bg"]
COLOR_SURFACE: Final[str] = COLORS["surface"]
COLOR_SURFACE_ALT: Final[str] = COLORS["surface-alt"]
COLOR_TEXT: Final[str] = COLORS["text"]
COLOR_PRIMARY: Final[str] = COLORS["primary"]
COLOR_ACCENT: Final[str] = COLORS["accent"]
COLOR_BORDER: Final[str] = COLORS["border"]

#: Chữ phụ = màu text với alpha (không thêm màu mới).
TEXT_MUTED: Final[str] = "rgba(49, 51, 63, 0.62)"
TEXT_SOFT: Final[str] = "rgba(49, 51, 63, 0.78)"

#: Nền nhấn = primary / accent với alpha thấp.
PRIMARY_TINT: Final[str] = "rgba(0, 84, 163, 0.08)"
ACCENT_TINT: Final[str] = "rgba(61, 157, 243, 0.14)"
ACCENT_TINT_BORDER: Final[str] = "rgba(61, 157, 243, 0.38)"

# ----------------------------------------------------------------------
# TYPOGRAPHY
# ----------------------------------------------------------------------
#: Tên font dùng cho cả HTML/CSS và Vega-Lite (Altair).
FONT_NAME: Final[str] = "Source Sans 3"
FONT_FAMILY: Final[str] = f"'{FONT_NAME}', 'Segoe UI', sans-serif"
#: URL Google Fonts cho các weight đang dùng (400 / 600 / 700).
FONT_URL: Final[str] = (
    "https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap"
)

#: Thang cỡ chữ của design system (px) — page title dùng text-3xl, metric
#: text-3xl, section text-2xl, body text-base, metadata text-sm/xs.
FONT_SIZE: Final[Dict[str, str]] = {
    "xs": "12px",
    "sm": "14px",
    "base": "16px",
    "lg": "20px",
    "xl": "22px",
    "2xl": "24px",
    "3xl": "28px",
}

# ----------------------------------------------------------------------
# RADIUS / SPACING / SHADOW
# ----------------------------------------------------------------------
RADIUS: Final[Dict[str, str]] = {
    "sm": "5px",
    "md": "8px",
    "lg": "10px",
    "pill": "50px",
}

SPACING: Final[Dict[str, str]] = {
    "xs": "4px",
    "sm": "8px",
    "md": "12px",
    "lg": "16px",
    "xl": "20px",
    "2xl": "24px",
    "3xl": "32px",
}

SHADOW_SUBTLE: Final[str] = "0 1px 2px rgba(49, 51, 63, 0.05)"
SHADOW_MENU: Final[str] = "0 4px 12px rgba(49, 51, 63, 0.10)"

# ----------------------------------------------------------------------
# MOTION
# ----------------------------------------------------------------------
#: Thời lượng chuyển động — 120ms cho hover/focus, 180ms cho notice, 240ms
#: cho page transition. Đủ "alive" mà không gây cảm giác trang trí thừa.
MOTION: Final[Dict[str, str]] = {
    "fast": "120ms",
    "base": "180ms",
    "slow": "240ms",
}

#: Đường cong chuyển động dùng chung cho mọi transition.
EASING_STANDARD: Final[str] = "cubic-bezier(0.2, 0, 0.2, 1)"
#: Đường cong cho phần tử trượt vào (bulk bar, page transition).
EASING_OUT: Final[str] = "cubic-bezier(0, 0, 0.2, 1)"


def css_variables() -> str:
    """
    Sinh khối `:root { --token: value; }` để dashboard.css dùng lại.

    Nhờ vậy giá trị trực quan chỉ được định nghĩa MỘT lần trong Python và
    không bị hardcode rải rác trong CSS.
    """
    tokens: Dict[str, str] = {
        "--color-bg": COLOR_BG,
        "--color-surface": COLOR_SURFACE,
        "--color-surface-alt": COLOR_SURFACE_ALT,
        "--color-text": COLOR_TEXT,
        "--color-primary": COLOR_PRIMARY,
        "--color-accent": COLOR_ACCENT,
        "--color-border": COLOR_BORDER,
        "--color-text-muted": TEXT_MUTED,
        "--color-text-soft": TEXT_SOFT,
        "--color-primary-tint": PRIMARY_TINT,
        "--color-accent-tint": ACCENT_TINT,
        "--color-accent-tint-border": ACCENT_TINT_BORDER,
        "--font-family": FONT_FAMILY,
        "--shadow-subtle": SHADOW_SUBTLE,
        "--shadow-menu": SHADOW_MENU,
        "--easing-standard": EASING_STANDARD,
        "--easing-out": EASING_OUT,
    }
    tokens.update({f"--motion-{name}": value for name, value in MOTION.items()})
    tokens.update({f"--text-{name}": value for name, value in FONT_SIZE.items()})
    tokens.update({f"--radius-{name}": value for name, value in RADIUS.items()})
    tokens.update({f"--spacing-{name}": value for name, value in SPACING.items()})

    lines = "\n".join(f"  {name}: {value};" for name, value in tokens.items())
    return f":root {{\n{lines}\n}}"
