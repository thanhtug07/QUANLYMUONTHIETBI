# -*- coding: utf-8 -*-
"""
tests/test_ui_polish.py — KIỂM TRA DESIGN SYSTEM POLISH
=======================================================
Chỉ kiểm tra tầng UI thuần (tokens, badge, màu chart, CSS vars) — không chạm
business logic, không đọc/ghi CSV thật.
"""
from __future__ import annotations

from pathlib import Path

from styles import tokens
from ui import badges
from ui import charts

CSS_FILE = Path(__file__).resolve().parent.parent / "styles" / "dashboard.css"


def test_status_tokens_have_all_variants():
    assert set(tokens.STATUS) == {"success", "warning", "danger", "info", "neutral"}
    for variant, props in tokens.STATUS.items():
        assert set(props) == {"text", "bg", "border", "dot", "base"}, variant


def test_css_variables_emit_status_and_shadow():
    variables = tokens.css_variables()
    for variant in ("success", "warning", "danger", "info", "neutral"):
        for prop in ("text", "bg", "border", "dot", "base"):
            assert f"--st-{variant}-{prop}:" in variables
    assert "--shadow-card:" in variables
    assert "--motion-fast:" in variables


def test_status_badge_variants_and_dot():
    assert 'st-warning' in badges.status_badge("Quá hạn")
    assert 'st-danger' in badges.status_badge("Thất thoát")
    assert 'st-info' in badges.status_badge("Đang mượn")
    assert 'st-success' in badges.status_badge("Đã trả")
    assert 'st-success' in badges.status_badge("Sẵn sàng")
    assert 'st-warning' in badges.status_badge("Bảo trì")
    assert 'st-neutral' in badges.status_badge("Nhãn lạ nào đó")
    html = badges.status_badge("Quá hạn")
    assert 'class="status-dot"' in html and "Quá hạn" in html


def test_status_badge_escapes_html():
    html = badges.status_badge("<script>alert(1)</script>")
    assert "<script>" not in html
    assert "st-neutral" in html


def test_severity_badges_follow_semantic():
    assert "st-danger" in badges.severity_badge("Cao")
    assert "st-warning" in badges.severity_badge("Trung bình")
    assert badges.severity_label("Dữ liệu lỗi") == "Cao"
    assert badges.severity_label("Sẵn sàng") == "Trung bình"


def test_chart_status_colors_match_tokens():
    for label, color in charts.STATUS_CHART_COLORS.items():
        assert color in {props["base"] for props in tokens.STATUS.values()}, label
    assert charts.STATUS_CHART_COLORS["Quá hạn"] == tokens.STATUS["warning"]["base"]
    assert charts.STATUS_CHART_COLORS["Đang mượn"] == tokens.STATUS["info"]["base"]
    assert charts.STATUS_CHART_COLORS["Sẵn sàng"] == tokens.STATUS["success"]["base"]
    assert charts.STATUS_CHART_COLORS["Bảo trì"] == tokens.STATUS["warning"]["base"]
    ordered = ["Sẵn sàng", "Đang mượn", "Bảo trì", "Thất thoát"]
    assert charts._status_colors(ordered) == [charts.STATUS_CHART_COLORS[label] for label in ordered]


def test_dashboard_css_uses_tokens_not_hardcoded_status():
    css = CSS_FILE.read_text(encoding="utf-8")
    for variant in ("success", "warning", "danger", "info", "neutral"):
        assert f"--st-{variant}-bg" in css, variant
    assert ".status-dot" in css
    assert ".st-key-dlg_confirm" in css  # nút confirm destructive tách khỏi primary
    assert "filter: brightness" in css  # hover primary không thêm màu mới
    assert "prefers-reduced-motion" in css
