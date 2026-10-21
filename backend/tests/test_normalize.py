import pytest

from applify.services.normalize import (
    clean_title,
    detect_remote,
    fingerprint,
    normalize_city,
    normalize_company,
    parse_salary,
)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("mgm technology partners GmbH", "mgm technology partners"),
        ("Müller & Söhne GmbH & Co. KG", "muller sohne"),
        ("SAP SE", "sap"),
        ("Startup UG (haftungsbeschränkt)", "startup"),
        ("Pixelwerk Deutschland GmbH", "pixelwerk"),
    ],
)
def test_normalize_company(name: str, expected: str) -> None:
    assert normalize_company(name) == expected


@pytest.mark.parametrize(
    ("title", "company", "expected"),
    [
        ("Fullstack Entwickler (m/w/d)", "", "Fullstack Entwickler"),
        ("DevOps Engineer m/w/d", "", "DevOps Engineer"),
        ("Senior Developer (all genders)", "", "Senior Developer"),
        ("Softwareentwickler*in Java", "", "Softwareentwickler Java"),
        ("Entwickler:in Frontend (w/m/d)", "", "Entwickler Frontend"),
        ("Webentwickler/-in", "", "Webentwickler"),
        ("C# Developer (gn)", "", "C# Developer"),
        # A "Company: " prefix is dropped only if it is the company.
        (
            "mgm technology partners GmbH: Fullstack Entwickler",
            "mgm technology partners",
            "Fullstack Entwickler",
        ),
        ("Team Lead: Platform", "Pixelwerk", "Team Lead: Platform"),
    ],
)
def test_clean_title(title: str, company: str, expected: str) -> None:
    assert clean_title(title, company) == expected


def test_normalize_city() -> None:
    assert normalize_city("Münster, Westfalen") == "munster"
    assert normalize_city("Berlin-Mitte") == "berlin"
    assert normalize_city("Halle (Saale)") == "halle"
    assert normalize_city("Frankfurt am Main") == "frankfurt am main"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Wir bieten 100% Remote", "remote"),
        ("Full-Remote möglich", "remote"),
        ("Homeoffice nach Vereinbarung", "hybrid"),
        ("hybrides Arbeiten", "hybrid"),
        ("Arbeitsort: Leipzig", None),
    ],
)
def test_detect_remote(text: str, expected: str | None) -> None:
    assert detect_remote(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Gehalt: 50.000 - 60.000 € brutto", (50000, 60000)),
        ("55k-65k EUR", (55000, 65000)),
        ("45.000€ bis 55.000€", (45000, 55000)),
        ("Vergütung: 60 000 EUR", (60000, None)),
        ("ab 48.000 € im Jahr", (48000, None)),
        # Monthly values become yearly.
        ("4.500 € brutto monatlich", (54000, None)),
        ("3.800 – 4.200 € / Monat", (45600, 50400)),
        ("Wir sind 25 Leute in 2 Büros", (None, None)),
        ("Zuschuss von 50 € für das Deutschlandticket", (None, None)),
    ],
)
def test_parse_salary(text: str, expected: tuple[int | None, int | None]) -> None:
    assert parse_salary(text) == expected


def test_fingerprint_ignores_legal_form_gender_and_district() -> None:
    a = fingerprint("Pixelwerk GmbH", "Fullstack Entwickler (m/w/d)", "Leipzig")
    b = fingerprint("Pixelwerk", "Fullstack Entwickler*in", "Leipzig-Plagwitz")
    assert a == b
    assert a != fingerprint("Pixelwerk", "Fullstack Entwickler", "Dresden")
