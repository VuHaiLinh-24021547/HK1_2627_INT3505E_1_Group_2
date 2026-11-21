import httpx
import pytest
import respx

from app.services import ddragon_service


def test_parse_latest_version():
    assert ddragon_service.parse_latest_version(["16.23.1", "16.22.1"]) == "16.23.1"
    with pytest.raises(ddragon_service.DDragonError):
        ddragon_service.parse_latest_version([])


def test_build_maps_from_fixture(sample_ddragon):
    ver = sample_ddragon["versions"][0]
    champs = ddragon_service.build_champion_map(sample_ddragon["champion"]["data"], ver)
    assert champs["157"]["name"] == "Yasuo"
    assert champs["157"]["imageUrl"].endswith(f"/cdn/{ver}/img/champion/Yasuo.png")
    assert champs["266"]["alias"] == "Aatrox"

    items = ddragon_service.build_item_map(sample_ddragon["item"]["data"], ver)
    assert items["3153"]["name"] == "Gươm Của Vua Vô Danh"
    assert items["3153"]["gold"] == 3200
    assert items["3153"]["imageUrl"].endswith(f"/cdn/{ver}/img/item/3153.png")

    runes = ddragon_service.build_rune_map(sample_ddragon["runes"])
    assert runes["8000"]["type"] == "style"
    assert runes["8008"]["type"] == "keystone"
    assert runes["9111"]["type"] == "rune"
    assert "/cdn/img/" in runes["8008"]["imageUrl"]

    spells = ddragon_service.build_spell_map(sample_ddragon["summoner"]["data"], ver)
    assert spells["4"]["name"] == "Tốc Biến"
    assert spells["14"]["imageUrl"].endswith(f"/cdn/{ver}/img/spell/SummonerDot.png")


def test_sync_patch_stores_and_caches_catalog(app, sample_ddragon):
    base = "https://ddragon.leagueoflegends.com"
    ver = "16.23.1"
    with respx.mock:
        respx.get(f"{base}/api/versions.json").mock(return_value=httpx.Response(200, json=sample_ddragon["versions"]))
        for lang in ("vi_VN", "en_US"):
            respx.get(f"{base}/cdn/{ver}/data/{lang}/champion.json").mock(
                return_value=httpx.Response(200, json=sample_ddragon["champion"])
            )
            respx.get(f"{base}/cdn/{ver}/data/{lang}/item.json").mock(
                return_value=httpx.Response(200, json=sample_ddragon["item"])
            )
            respx.get(f"{base}/cdn/{ver}/data/{lang}/runesReforged.json").mock(
                return_value=httpx.Response(200, json=sample_ddragon["runes"])
            )
            respx.get(f"{base}/cdn/{ver}/data/{lang}/summoner.json").mock(
                return_value=httpx.Response(200, json=sample_ddragon["summoner"])
            )

        with app.app_context():
            synced = ddragon_service.sync_patch()
            assert synced == ver
            catalog = ddragon_service.get_catalog("latest", "vi_VN")
            assert catalog["patch"] == ver
            assert "157" in catalog["champions"]
            # Prefix lookup (e.g. 16.23 -> 16.23.1)
            by_short = ddragon_service.get_catalog("16.23", "vi_VN")
            assert by_short["patch"] == ver
            assert ddragon_service.get_catalog("99.99", "vi_VN") is None
