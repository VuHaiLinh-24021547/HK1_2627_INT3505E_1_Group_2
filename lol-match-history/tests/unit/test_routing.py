import pytest

from app.services import routing


def test_vn2_routes_account_to_asia_and_match_to_sea():
    r = routing.resolve("vn2")
    assert r.platform_host == "vn2.api.riotgames.com"
    assert r.account_host == "asia.api.riotgames.com"
    assert r.match_host == "sea.api.riotgames.com"


@pytest.mark.parametrize(
    ("region", "account_cluster", "match_cluster"),
    [
        ("VN2", "asia", "sea"),
        ("sg2", "asia", "sea"),
        ("kr", "asia", "asia"),
        ("jp1", "asia", "asia"),
        ("euw1", "europe", "europe"),
        ("na1", "americas", "americas"),
    ],
)
def test_supported_regions(region, account_cluster, match_cluster):
    r = routing.resolve(region)
    assert r.platform_host == f"{region.lower()}.api.riotgames.com"
    assert r.account_host == f"{account_cluster}.api.riotgames.com"
    assert r.match_host == f"{match_cluster}.api.riotgames.com"


@pytest.mark.parametrize("bad", ["", "mars1", "sea", "asia", None])
def test_invalid_region_raises_value_error(bad):
    with pytest.raises(ValueError):
        routing.resolve(bad)


def test_region_from_match_id():
    assert routing.region_from_match_id("VN2_492817261") == "vn2"
    assert routing.region_from_match_id("KR_123456") == "kr"
    with pytest.raises(ValueError):
        routing.region_from_match_id("INVALID")
