import pytest

from applify_analytics.features.regions import get_states, state_at


@pytest.mark.parametrize(
    ("lat", "lon", "state"),
    [
        (51.34, 12.37, "DE-SN"),  # Leipzig
        (52.52, 13.40, "DE-BE"),  # Berlin, inside Brandenburg's outline
        (52.39, 13.06, "DE-BB"),  # Potsdam
        (53.55, 8.58, "DE-HB"),  # Bremerhaven, an exclave of Bremen
        (53.55, 9.99, "DE-HH"),  # Hamburg
        (54.90, 8.31, "DE-SH"),  # Sylt
        (47.66, 9.17, "DE-BW"),  # Konstanz at the lake
    ],
)
def test_state_from_coordinates(lat: float, lon: float, state: str) -> None:
    assert state_at(lon, lat) == state


def test_places_abroad_have_no_state() -> None:
    assert state_at(2.35, 48.85) is None  # Paris


def test_all_states_with_population() -> None:
    states = get_states()
    assert len(states) == 16
    assert 80_000_000 < sum(s.population for s in states) < 90_000_000
