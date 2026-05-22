"""Phase 2: theme→novel + copyright novelty."""
import os
import pathlib
import sys

from src.compliance.copyright_novelty import novelty_check
from src.shell1_screenwriter.theme_to_novel import theme_to_novel


def test_theme_to_novel_mock_backend_returns_structured_text():
    body = theme_to_novel(
        "都市职场失意女青年遇见霸总", genre="modern", length_words=2000, backend="mock"
    )
    assert isinstance(body, str)
    assert len(body) > 200
    # Heuristic chapter markers exist
    assert "第" in body and ("章" in body or "幕" in body or "集" in body)


def test_novelty_check_safe_text_low_risk():
    report = novelty_check("完全原创的小说，关于一只可爱的小猫的日常冒险。")
    assert 0.0 <= report["risk_score"] <= 0.3


def test_novelty_check_flags_known_ip():
    report = novelty_check(
        "霍格沃茨的魁地奇赛季开始了，伏地魔却悄悄出现在对角巷。"
        "马尔福一家也加入了战斗。"
    )
    # Heuristic backend marks ≥ 3 signal hits as risk_score >= 1.0
    assert report["risk_score"] >= 0.8
    assert any("哈利波特" in s["ip"] for s in report["similar_ips"])
