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


@pytest.mark.parametrize(
    ("text", "low", "high"),
    [
        # Districts count as their city.
        ("Zentrum, Leipzig", 500_000, 600_000),
        ("Berlin-Mitte", 3_000_000, 4_000_000),
        ("88074 Meckenbeuren", 10_000, 20_000),
        ("Wiesenbach", 1_000, 5_000),
        ("Geiersthal, Regen (Kreis)", 1_000, 5_000),
        ("Berlin; Chemnitz, Sachsen; Dresden, Sachsen", 3_000_000, 4_000_000),
    ],
)
def test_population(text: str, low: int, high: int) -> None:
    population = get_gazetteer().population(text)
    assert population is not None
    assert low <= population <= high


def test_population_of_same_named_town_near_the_job() -> None:
    # Without coordinates the largest Neustadt; next to Coburg it is Neustadt bei Coburg.
    gazetteer = get_gazetteer()
    assert (gazetteer.population("Neustadt") or 0) > 50_000
    assert (gazetteer.population("Neustadt", 50.33, 11.12) or 0) < 20_000


def test_population_unknown() -> None:
    assert get_gazetteer().population("Remote") is None
