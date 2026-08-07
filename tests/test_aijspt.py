from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

import gduf_web_api as api
from gduf_web_api import GdufClient, NetworkError, UnsupportedSourceError


def test_competition_list_parses_all_snapshot_items(client: GdufClient) -> None:
    result = client.get_competitions()

    assert result.total_items == 14
    assert result.source_url == "https://ai-data-competitions.cn/api/competitions"
    first = result.items[0]
    assert first.title == "全国大学生机器人大赛-①RoboMaster"
    assert first.registration_start_at is None
    assert first.official_url == "https://www.robomaster.com/zh-CN"

    upcoming = result.items[1]
    assert upcoming.registration_start_at == datetime(2026, 11, 3, 21, 49, tzinfo=timezone.utc)
    assert upcoming.to_dict()["registration_start_at"] == "2026-11-03T21:49:00+00:00"
    assert upcoming.registration_mode == "team"
    assert upcoming.max_team_size == 5


def test_competition_filters_are_combined_and_keep_order(client: GdufClient) -> None:
    all_items = client.get_competitions().items
    filtered = client.get_competitions(
        year=2026,
        status="registration_open",
        category="软件设计类",
        department="大数据与人工智能学院",
        keyword="创新人才",
    )

    assert [item.id for item in filtered.items] == [all_items[2].id]
    assert filtered.total_items == 1

    with pytest.raises(ValueError, match="positive integer"):
        client.get_competitions(year=True)
    with pytest.raises(ValueError, match="cannot be empty"):
        client.get_competitions(keyword="  ")
    with pytest.raises(UnsupportedSourceError):
        client.get_competitions(source="missing")


def test_competition_detail_accepts_all_supported_identifiers(client: GdufClient) -> None:
    competition = client.get_competitions(keyword="软件杯").items[0]
    identifiers = (
        competition,
        competition.id,
        f"/competitions/{competition.id}",
        competition.url,
    )

    for identifier in identifiers:
        detail = client.get_competition_detail(identifier)
        assert detail.id == competition.id
        assert detail.title == competition.title
        assert detail.location == "广州校区"
        assert detail.highlights == ("产教融合", "企业命题")
        assert detail.sub_tracks == ("A 组",)
        assert detail.timeline[1].label == "报名截止"
        assert detail.faqs[0].answer == "需要至少一位指导老师。"
        assert detail.attachments[0].url == "https://ai-data-competitions.cn/files/rules.pdf"
        assert detail.related_questions[0].title == "报名问题"
        assert detail.experience_articles[0].url == "https://example.edu/article"
        assert "script" not in detail.description_html
        assert "style=" not in detail.description_html
        assert "onmouseover" not in detail.description_html
        assert "onerror" not in detail.description_html
        assert "https://ai-data-competitions.cn/images/cup.png" in detail.description_html
        assert "https://ai-data-competitions.cn/rules" in detail.description_html


def test_competition_detail_rejects_invalid_or_unavailable_resources(
    client: GdufClient,
) -> None:
    for invalid in (
        "",
        "not-a-uuid",
        "https://example.com/competitions/3c3f766f-684f-46cb-b265-a686a9f3738b",
        "/competitions/3c3f766f-684f-46cb-b265-a686a9f3738b/apply",
    ):
        with pytest.raises(ValueError):
            client.get_competition_detail(invalid)

    with pytest.raises(NetworkError):
        client.get_competition_detail("e9cd546f-2e1f-4756-8f5b-5d3a5f5d7800")


def test_notices_and_limit_validation(client: GdufClient, request_log: list[httpx.Request]) -> None:
    result = client.get_notices(7)

    assert result.total_items == 1
    assert request_log[-1].url.params["limit"] == "7"
    notice = result.items[0]
    assert notice.competition_id is None
    assert notice.delivery_scope == "global"
    assert notice.published_at.tzinfo == timezone.utc
    assert notice.to_dict()["published_at"] == "2026-07-20T03:27:49.461000+00:00"

    for invalid in (0, -1, True):
        with pytest.raises(ValueError, match="positive integer"):
            client.get_notices(invalid)


def test_club_list_parses_five_public_cards(client: GdufClient) -> None:
    result = client.get_clubs()

    assert result.total_items == 5
    assert [club.slug for club in result.items] == [
        "quant-investment",
        "java-tribe",
        "ai-studio",
        "bricks-team",
        "acm-team",
    ]
    assert result.items[0].direction == "量化投资"
    assert result.items[-1].url == "https://ai-data-competitions.cn/clubs/acm-team"


def test_aijspt_public_helpers_reuse_client(client: GdufClient) -> None:
    competitions = api.get_aijspt_bslb(status="registration_open", client=client)
    assert competitions.items
    assert api.get_aijspt_bsxq(competitions.items[0], client=client).timeline
    assert api.get_aijspt_tzgg(limit=1, client=client).items
    assert api.get_aijspt_stlb(client=client).items
