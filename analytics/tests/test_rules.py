import pytest

from applify_analytics.features.rules import (
    Salary,
    degrees,
    get_agency_rules,
    get_role_rules,
    required_years,
    salary_in_text,
    seniority,
    yearly_eur,
)


@pytest.mark.parametrize(
    ("title", "family"),
    [
        ("Fullstack Entwickler (m/w/d)", "fullstack"),
        ("Full-Stack Webentwickler Java", "fullstack"),
        ("Senior Frontend Developer React", "frontend"),
        ("Backend-Developer - Telematikinfrastruktur (TI)", "backend"),
        ("Java Entwickler", "backend"),
        ("React Developer", "frontend"),
        ("Software Developer ABAP - remote DE", "sap"),
        ("Data Engineer", "data"),
        ("Agentic Software Engineer Smart Factory", "software"),
        ("Softwareentwickler Maschinensteuerungen", "embedded"),
        ("DevOps Engineer Kubernetes", "devops"),
        ("Software Development Engineer in Test (SDET)", "qa"),
        ("IT-Systemadministrator", "it_ops"),
        ("Product Owner E-Commerce", "management"),
        ("Senior UX Designer", "design"),
        ("iOS Developer", "mobile"),
        ("Softwareentwickler (m/w/d)", "software"),
        ("Enterprise Account Executive, Cloud", "other"),
        ("Sales Engineer", "other"),
        ("Solutions Architect, Public Sector", "consulting"),
        ("DevSecOps Engineer – full remote möglich", "devops"),
        ("Principal Engineer, Duo Agent Platform", "software"),
        ("Field Engineer Erdbeben-Stahlbau / Seismik", "other"),
    ],
)
def test_role_family_from_title(title: str, family: str) -> None:
    assert get_role_rules().classify(title) == family


def test_unknown_titles_have_no_family() -> None:
    assert get_role_rules().classify("Mitarbeiter (m/w/d) in Vollzeit") is None


@pytest.mark.parametrize(
    ("text", "years"),
    [
        ("- Mindestens 3 Jahre Erfahrung in der Backend-Entwicklung mit Java.", (3, None)),
        ("Mehrjährige praktische Erfahrung (mind. 5 Jahre) im Betrieb", (5, None)),
        ("- 3-5 years of experience in systems engineering", (3, 5)),
        ("- Technical Expertise: 3+ years building and shipping production", (3, None)),
        ("5+ years leading teams and 2+ years managing managers", (5, None)),
        ("Du bringst zwei Jahre Berufserfahrung mit", (2, None)),
        # Company age and time spans are no requirement.
        ("Bei uns herrscht auch nach über 10 Jahren eine Startup-Atmosphäre", (None, None)),
        ("Wir greifen auf mehr als 20 Jahre Kompetenz zurück", (None, None)),
        ("st du in 3 Monaten mehr als anderswo in 3 Jahren.", (None, None)),
    ],
)
def test_required_years(text: str, years: tuple[int | None, int | None]) -> None:
    assert required_years(text) == years


@pytest.mark.parametrize(
    ("title", "years", "level"),
    [
        ("Senior Backend Developer", 2, "senior"),
        ("Teamlead Software", None, "lead"),
        ("Junior Software Developer", 5, "junior"),
        ("Werkstudent Softwareentwicklung", None, "student"),
        ("Softwareentwickler", 1, "junior"),
        ("Softwareentwickler", 3, "mid"),
        ("Softwareentwickler", 5, "senior"),
        ("Softwareentwickler", None, None),
    ],
)
def test_seniority_title_before_years(title: str, years: int | None, level: str | None) -> None:
    assert seniority(title, years) == level


@pytest.mark.parametrize(
    ("text", "eur"),
    [
        (
            "- Die Vergütung liegt zwischen 71.000 € und 104.040 €. Die tatsächliche",
            (71000, 104040),
        ),
        ("• Annual Compensation Range (Gross) €65K – €105K • Offers Bonus", (65000, 105000)),
        ("Vergütung (ab 2.400 € – 3.400 € pro Monat, nach oben offen)", (28800, 40800)),
        ("## NUR VOLLZEIT · 30.000 bis 45.000 € brutto im Jahr, Gehalt fix", (30000, 45000)),
        ("- Gehaltsspektrum: 60000 Euro pro Jahr", (60000, None)),
        ("Die Gehaltsorientierung beträgt 74.750 EUR brutto pro Jahr bei Vollzeit.", (74750, None)),
        ("- je nach Qualifikation 48.000 bis 60.000 Euro Bruttojahresgehalt", (48000, 60000)),
        # A monthly lower bound below any plausible salary is dropped.
        ("Einkommensspanne: ca. 530 € bis 3.750 € monatlich", (None, 45000)),
    ],
)
def test_salary_in_text(text: str, eur: tuple[int | None, int | None]) -> None:
    salary = salary_in_text(text)
    assert salary is not None and yearly_eur(salary) == eur


@pytest.mark.parametrize(
    "text",
    [
        "Nach der Probezeit gibt's 600 € Zuschuss zur Altersvorsorge per Gehaltsumwandlung",
        "- Monatlicher 50€ hrmony Gutschein für Fitness-Center",
        "we support this with a yearly flex work allowance of €1560",
        "Rillet has raised more than $200M, is valued at $1B",
        "Wir bieten ein attraktives Gehalt und 30 Tage Urlaub.",
    ],
)
def test_benefits_and_funding_are_no_salary(text: str) -> None:
    assert salary_in_text(text) is None


def test_foreign_currency_is_kept_but_not_in_eur() -> None:
    text = (
        "United States Salary Range $140,000 - $185,000\nGermany Salary Range: €90,000 - €120,000"
    )
    assert salary_in_text(text) == Salary("EUR", "year", 90000, 120000)
    usd = salary_in_text("Compensation: $240K – $280K • Offers Equity")
    assert usd == Salary("USD", "year", 240000, 280000)
    assert yearly_eur(usd) == (None, None)


def test_degrees() -> None:
    text = (
        "- Du hast ein abgeschlossenes Studium der Informatik oder eine abgeschlossene "
        "Ausbildung als Fachinformatiker\n"
        "- Erfahrung als Scrum Master vorausgesetzt\n"
        "Wir unterstützen dein Studium mit flexiblen Arbeitszeiten."
    )
    assert degrees(text) == ["university", "vocational"]
    assert degrees("- Du bringst diplomatisches Geschick mit") == []


@pytest.mark.parametrize(
    ("company", "text"),
    [
        ("Hays AG", ""),
        ("FERCHAU GmbH Niederlassung Dresden", ""),
        ("Jenpersonal GmbH", ""),
        ("S&B Personalservice GmbH", ""),
        ("Die Tech Recruiter GmbH", ""),
        ("IT VISTA Personalberatung GmbH", ""),
        ("Acme", "Im Auftrag unseres Kunden suchen wir einen Java-Entwickler."),
        ("Acme", "Für unseren Kunden in Leipzig suchen wir"),
        ("Acme", "Die Stelle ist im Rahmen der Arbeitnehmerüberlassung zu besetzen."),
        ("Acme", "Our client is a fast-growing fintech."),
    ],
)
def test_staffing_agencies(company: str, text: str) -> None:
    assert get_agency_rules().is_agency(company, text)


@pytest.mark.parametrize(
    ("company", "text"),
    [
        ("GitLab", "We help our clients ship software faster."),
        ("Celonis", "Join our client success team."),
        ("Personio GmbH", "Unsere Kunden lieben unser HR-Produkt."),
        ("codecentric AG", "Du berätst unsere Kunden vor Ort."),
        ("CHECK24 Services Personal GmbH", ""),
        ("Vonovia Recruiting DE", ""),
    ],
)
def test_direct_employers(company: str, text: str) -> None:
    assert not get_agency_rules().is_agency(company, text)
