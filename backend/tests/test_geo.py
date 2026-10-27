import pytest

from applify.services.geo import distance_km, get_gazetteer


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Leipzig", "Leipzig"),
        ("04109 Leipzig", "Leipzig"),
        ("Münster, Westfalen", "Münster"),
        ("Berlin-Mitte", "Berlin"),
        # English main names in GeoNames; the German alternate name is indexed too.
        ("München", "München"),
        ("Nürnberg", "Nürnberg"),
        # Ambiguous names resolve to the largest place.
        ("Frankfurt", "Frankfurt am Main"),
        ("Frankfurt (Oder)", "Frankfurt (Oder)"),
        ("Leipzig/Halle", "Leipzig"),
    ],
)
def test_locate(text: str, expected: str) -> None:
    place = get_gazetteer().locate(text)
    assert place is not None
    assert place.name == expected


def test_halle_is_halle_saale() -> None:
    place = get_gazetteer().locate("Halle")
    assert place is not None
    assert place.population > 200_000


def test_unknown_place() -> None:
    assert get_gazetteer().locate("Remote") is None


def test_distance() -> None:
    gazetteer = get_gazetteer()
    leipzig, dresden = gazetteer.locate("Leipzig"), gazetteer.locate("Dresden")
    assert leipzig and dresden
    assert distance_km(leipzig.lat, leipzig.lon, dresden.lat, dresden.lon) == pytest.approx(
        100, abs=3
    )


@pytest.mark.parametrize(
    ("text", "city"),
    [
        ("Zentrum, Leipzig", "Leipzig"),
        ("Chemnitz, Sachsen", "Chemnitz"),
        ("04109 Leipzig", "Leipzig"),
        ("Ammerbach, Jena", "Jena"),
    ],
)
def test_city_of_district_or_state_suffix(text: str, city: str) -> None:
    assert get_gazetteer().city(text) == city
