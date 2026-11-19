# -*- coding: utf-8 -*-
"""
ui/layout.py — KHUNG TRANG & GRID
=================================
Chịu trách nhiệm: cấu hình trang, nạp design system (tokens + CSS), page
header (kèm primary action), card header và các grid.

KHÔNG chứa business logic.
"""
from __future__ import annotations

import functools
from pathlib import Path
from typing import Callable, Optional, Tuple

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from styles import tokens
from ui.theme import is_dark
from utils.helpers import esc

STYLES_DIR = Path(__file__).resolve().parents[1] / "styles"
CSS_FILE = STYLES_DIR / "dashboard.css"


def setup_page() -> None:
    """Cấu hình trang — phải gọi TRƯỚC mọi lệnh st.* khác."""
    st.set_page_config(
        page_title="Quản lý mượn thiết bị",
        page_icon="📋",
        layout="wide",
        # "auto": mở sẵn trên máy tính (người dùng thấy ngay menu), tự gập trên
        # điện thoại để sidebar không che toàn bộ nội dung.
        initial_sidebar_state="auto",
    )


@functools.lru_cache(maxsize=4)
def _compiled_base_css(mtime_ns: int) -> str:
    css = CSS_FILE.read_text(encoding="utf-8")
    return f"@import url('{tokens.FONT_URL}');\n{tokens.css_variables()}\n{css}"


def inject_global_styles(extra_css: str = "") -> None:
    """
    Nạp font + design tokens + dashboard.css (+ CSS động tuỳ chọn).

    Thứ tự trong một thẻ <style>: @import (font) -> biến CSS -> component CSS.
    """
    try:
        mtime_ns = CSS_FILE.stat().st_mtime_ns
    except OSError:
        mtime_ns = 0
    base_css = _compiled_base_css(mtime_ns)
    # Chế độ tối: ghi đè biến màu SAU khối :root gốc; toàn bộ dashboard.css
    # dùng var(--...) nên tự đổi theo, không cần CSS riêng cho dark.
    dark_css = tokens.dark_css_variables() if is_dark() else ""
    st.markdown(
        f"<style>{base_css}\n{dark_css}\n{extra_css}</style>",
        unsafe_allow_html=True,
    )


def _page_header_html(title: str, subtitle: str, meta: str) -> None:
    meta_html = f'<div class="page-meta">{esc(meta)}</div>' if meta else ""
    st.markdown(
        f'<div class="page-header">'
        f'<h1 class="page-title">{esc(title)}</h1>'
        f'<p class="page-subtitle">{esc(subtitle)}</p>'
        f"{meta_html}</div>",
        unsafe_allow_html=True,
    )


def page_header(
    title: str,
    subtitle: str = "",
    meta: str = "",
    action_label: str = "",
    action_key: str = "",
    on_action: Optional[Callable[[], None]] = None,
    action_help: str = "",
) -> None:
    """
    Tiêu đề trang (28px/700) + mô tả + metadata + primary action tuỳ chọn.

    Primary action là st.button thật (keyboard/aria chuẩn) đặt ngay cạnh tiêu
    đề — không tách sang vùng khác của trang.
    """
    if not action_label:
        _page_header_html(title, subtitle, meta)
        return

    title_col, action_col = st.columns([3, 1], gap="medium", vertical_alignment="center")
    with title_col:
        _page_header_html(title, subtitle, meta)
    with action_col:
        st.button(
            action_label,
            key=action_key,
            on_click=on_action,
            type="primary",
            width="stretch",
            help=action_help or None,
        )


def card_header(title: str, subtitle: str = "", chip: str = "") -> None:
    """
    Header chuẩn của mọi card: tiêu đề (18px/700) + chip số liệu (tuỳ chọn)
    + phụ đề metadata (13px). Dùng chung cho chart card, table card, panel.
    """
    chip_html = f'<span class="card-count">{esc(chip)}</span>' if chip else ""
    subtitle_html = f'<div class="card-subtitle">{esc(subtitle)}</div>' if subtitle else ""
    st.markdown(
        f'<div class="card-title-row"><h3 class="card-title">{esc(title)}</h3>{chip_html}</div>'
        f"{subtitle_html}",
        unsafe_allow_html=True,
    )


def analytics_grid() -> Tuple[DeltaGenerator, DeltaGenerator]:
    """Grid analytics chính: cột lớn (8) cho biểu đồ chủ đạo, cột nhỏ (4) cho biểu đồ phụ."""
    return st.columns([8, 4], gap="medium")


def two_column_grid() -> Tuple[DeltaGenerator, DeltaGenerator]:
    """Grid hai cột bằng nhau (dùng cho các panel phụ như xếp hạng)."""
    return st.columns(2, gap="medium")


#: Script phím tắt: "/" focus ô tìm kiếm đầu tiên của trang, "Esc" thoát ô
#: đang gõ. Gắn listener MỘT lần (cờ window.__qlShortcuts) dù Streamlit rerun.
_SHORTCUT_JS = """
<script>
(function () {
  // Giao diện cố định SÁNG: nếu trình duyệt còn lưu lựa chọn theme Dark của
  // Streamlit (localStorage "stActiveTheme…") thì xoá và tải lại MỘT lần.
  try {
    var reset = false;
    for (var k = localStorage.length - 1; k >= 0; k--) {
      var key = localStorage.key(k);
      if (key && key.indexOf("stActiveTheme") === 0) {
        var value = localStorage.getItem(key) || "";
        if (value.toLowerCase().indexOf("dark") !== -1 || value.toLowerCase().indexOf("system") !== -1) {
          localStorage.removeItem(key);
          reset = true;
        }
      }
    }
    if (reset && !sessionStorage.getItem("qlThemeReset")) {
      sessionStorage.setItem("qlThemeReset", "1");
      window.location.reload();
      return;
    }
  } catch (err) { /* trình duyệt chặn storage: bỏ qua */ }
  if (window.__qlShortcuts) { return; }
  window.__qlShortcuts = true;
  function isTyping(el) {
    if (!el) { return false; }
    var tag = (el.tagName || "").toLowerCase();
    return tag === "input" || tag === "textarea" || tag === "select" || el.isContentEditable;
  }
  document.addEventListener("keydown", function (event) {
    if (event.key === "/" && !event.ctrlKey && !event.metaKey && !event.altKey) {
      if (isTyping(document.activeElement)) { return; }
      var inputs = document.querySelectorAll('[data-testid="stMain"] [data-testid="stTextInput"] input');
      for (var i = 0; i < inputs.length; i++) {
        if (inputs[i].offsetParent !== null && !inputs[i].disabled) {
          event.preventDefault();
          inputs[i].focus();
          inputs[i].select();
          return;
        }
      }
    } else if (event.key === "Escape" && isTyping(document.activeElement)) {
      document.activeElement.blur();
    }
  });
})();
</script>
"""


def inject_shortcuts() -> None:
    """Gắn phím tắt bàn phím toàn app ("/" tìm kiếm, "Esc" thoát ô nhập)."""
    st.html(_SHORTCUT_JS, unsafe_allow_javascript=True)
