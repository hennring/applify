"""Rule-based feature extraction from job postings (§5.8, D22).

Pure functions on title and text; deterministic and unit-tested. What the rules cannot
decide stays None and may be filled by the LLM fallback later.
"""

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal

import yaml

ROLES_FILE = Path(__file__).resolve().parents[2] / "resources" / "roles.yaml"

Seniority = Literal["student", "junior", "mid", "senior", "lead"]
Period = Literal["year", "month", "hour"]

# --- role family ------------------------------------------------------------------------


@dataclass(frozen=True)
class RoleFamily:
    key: str
    label: str


@dataclass(frozen=True)
class RoleRules:
    families: tuple[RoleFamily, ...]
    rules: tuple[tuple[str, re.Pattern[str]], ...]

    def classify(self, title: str) -> str | None:
        """Family of the first matching rule, or None if no rule matches."""
        for family, pattern in self.rules:
            if pattern.search(title):
                return family
        return None


def _word_pattern(pattern: str) -> str:
    """Whole words where the pattern starts or ends with a letter (not '\\w*' etc.)."""
    start = r"(?<![\w])" if pattern[:1].isalnum() else ""
    end = r"(?![\w])" if pattern[-1:].isalnum() or pattern.endswith(")") else ""
    return f"{start}(?:{pattern}){end}"


@cache
def get_role_rules(path: Path = ROLES_FILE) -> RoleRules:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    families = tuple(RoleFamily(f["key"], f["label"]) for f in data["families"])
    keys = {f.key for f in families}
    rules = []
    for rule in data["rules"]:
        if rule["family"] not in keys:
            raise ValueError(f"roles.yaml: unknown family {rule['family']!r}")
        pattern = "|".join(_word_pattern(p) for p in rule["patterns"])
        rules.append((rule["family"], re.compile(pattern, re.IGNORECASE)))
    return RoleRules(families, tuple(rules))


# --- seniority and years of experience -----------------------------------------------------

STUDENT_TITLE = re.compile(
    r"\b(werkstudent\w*|working student|praktik\w*|intern(ship)?|azubi|auszubildende\w*|"
    r"ausbildung\w*|abschlussarbeit|bachelorarbeit|masterarbeit|thesis|duales studium|"
    r"dualer student\w*)\b",
    re.IGNORECASE,
)
LEAD_TITLE = re.compile(
    r"\b(lead|principal|head of|leiter\w*|leitung|team\s?lead\w*|teamleiter\w*|"
    r"director|vp|chief|cto)\b",
    re.IGNORECASE,
)
SENIOR_TITLE = re.compile(r"\b(senior|sr\.?|staff|expert\w*|architekt\w*|architect)\b", re.I)
MID_TITLE = re.compile(r"\b(mid[\s-]?level|midlevel|mid|professional)\b", re.IGNORECASE)
JUNIOR_TITLE = re.compile(
    r"\b(junior|jr\.?|einsteiger\w*|berufseinsteiger\w*|trainee|graduate|absolvent\w*|"
    r"young professional|entry[\s-]?level)\b",
    re.IGNORECASE,
)
# Below 2 years junior, 2–4 mid, from 5 senior (PLAN §5.8).
MID_FROM_YEARS = 2
SENIOR_FROM_YEARS = 5
MAX_YEARS = 15

NUMBER_WORDS = {
    "ein": 1, "einem": 1, "einen": 1, "eins": 1, "one": 1,
    "zwei": 2, "two": 2, "drei": 3, "three": 3, "vier": 4, "four": 4,
    "fünf": 5, "five": 5, "sechs": 6, "six": 6, "sieben": 7, "seven": 7,
    "acht": 8, "eight": 8, "neun": 9, "nine": 9, "zehn": 10, "ten": 10,
}  # fmt: skip
_NUM = r"(\d{1,2}|" + "|".join(NUMBER_WORDS) + r")"
YEARS = re.compile(
    rf"\b{_NUM}\s*(\+|plus)?\s*(?:(?:-|–|bis|to)\s*{_NUM}\s*)?"
    r"(?:\+\s*)?(?:jahre?n?|years?|yrs?)\b",
    re.IGNORECASE,
)
EXPERIENCE = re.compile(r"erfahrung|experience|berufspraxis|praxis", re.IGNORECASE)
AT_LEAST = re.compile(
    r"(mindestens|mind\.|min\.|wenigstens|at least|minimum( of)?)\s*$", re.IGNORECASE
)


def _number(text: str) -> int:
    return int(text) if text.isdigit() else NUMBER_WORDS[text.lower()]


def required_years(text: str) -> tuple[int | None, int | None]:
    """Years of experience a posting asks for: (minimum, maximum of a range).

    A number of years counts only as a requirement if it says so: "3+", "mindestens 3",
    or "experience" close by; "seit über 10 Jahren" (company age) does not.
    With several requirements the highest minimum wins.
    """
    best: tuple[int, int | None] | None = None
    for m in YEARS.finditer(text):
        low = _number(m.group(1))
        high = _number(m.group(3)) if m.group(3) else None
        plus = bool(m.group(2)) or "+" in m.group(0)
        before = text[max(0, m.start() - 60) : m.start()]
        after = text[m.end() : m.end() + 60]
        line_before = before.rsplit("\n", 1)[-1]
        explicit = plus or bool(AT_LEAST.search(line_before))
        if not (explicit or EXPERIENCE.search(line_before) or EXPERIENCE.search(after)):
            continue
        if low > MAX_YEARS or (high is not None and (high > MAX_YEARS or high < low)):
            continue
        if best is None or low > best[0]:
            best = (low, high)
    return best if best is not None else (None, None)


def seniority(title: str, years_min: int | None) -> Seniority | None:
    """The title decides if it says so; otherwise the required years."""
    if STUDENT_TITLE.search(title):
        return "student"
    if LEAD_TITLE.search(title):
        return "lead"
    if SENIOR_TITLE.search(title):
        return "senior"
    if JUNIOR_TITLE.search(title):
        return "junior"
    if MID_TITLE.search(title):
        return "mid"
    if years_min is None:
        return None
    if years_min >= SENIOR_FROM_YEARS:
        return "senior"
    return "mid" if years_min >= MID_FROM_YEARS else "junior"


# --- salary -------------------------------------------------------------------------------

CURRENCIES = {"€": "EUR", "eur": "EUR", "euro": "EUR", "$": "USD", "usd": "USD",
              "£": "GBP", "gbp": "GBP", "chf": "CHF"}  # fmt: skip
_CUR = r"(€|eur\b|euro\b|\$|usd\b|£|gbp\b|chf\b)"
_AMOUNT = r"(\d{1,3}(?:[.,\s]\d{3})+|\d+(?:[.,]\d{1,2})?)\s*(k|tsd\.?|t€)?"
MONEY = re.compile(rf"{_CUR}\s*{_AMOUNT}(?![\d.,])|(?<![\w.,]){_AMOUNT}\s*{_CUR}", re.IGNORECASE)
SALARY_WORDS = re.compile(
    r"gehalt|vergütung|salary|compensation|pay[\s-]?range|base pay|einkommen|verdienst|"
    r"jahresbrutto|bruttojahres|tarif",
    re.IGNORECASE,
)
# Money that is not the salary: benefits, funding, budgets.
NOT_SALARY = re.compile(
    r"zuschuss|gutschein|umwandlung|allowance|budget|stipend|sachbezug|raised|valuation|"
    r"revenue|umsatz|spend|funding|finanzierung|investment|investition",
    re.IGNORECASE,
)
MONTH = re.compile(r"monat\w*|month\w*|mtl\.?|/\s*mon", re.IGNORECASE)
HOUR = re.compile(r"stunde\w*|stündlich|hour\w*|/\s*h\b|std\.", re.IGNORECASE)
PER_PERIOD = {"year": 1, "month": 12, "hour": 2080}
# Plausible yearly gross salary in EUR (PLAN §5.8).
SALARY_RANGE = (15_000, 300_000)


@dataclass(frozen=True)
class Salary:
    currency: str
    period: Period
    low: float
    high: float | None


def _amount(number: str, thousands: str | None) -> float:
    digits = number.replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", digits):
        value = float(re.sub(r"[.,]", "", digits))
    else:
        value = float(digits.replace(",", "."))
    return value * 1000 if thousands else value


def _period(line: str, values: list[float]) -> Period:
    if HOUR.search(line):
        return "hour"
    if MONTH.search(line) and not re.search(r"jahr|year|annual|p\.\s?a\.", line, re.I):
        return "month"
    if max(values) < 200:
        return "hour"
    return "month" if max(values) < 10_000 else "year"


# A bare first amount of a range whose currency follows the second: "30.000 bis 45.000 €".
RANGE_START = re.compile(
    r"(\d{1,3}(?:[.,\s]\d{3})+|\d+(?:[.,]\d{1,2})?)\s*(k|tsd\.?)?\s*(?:-|–|—|bis|to)\s*$",
    re.IGNORECASE,
)


def _line_salary(line: str) -> Salary | None:
    found: list[tuple[str, float]] = []
    for m in MONEY.finditer(line):
        if m.group(1):
            currency, number, thousands = m.group(1), m.group(2), m.group(3)
        else:
            number, thousands, currency = m.group(4), m.group(5), m.group(6)
        code = CURRENCIES[currency.lower()]
        value = _amount(number, thousands)
        if not found and (start := RANGE_START.search(line[: m.start()])):
            first = _amount(start.group(1), start.group(2))
            # "65-80k €": the first number shares the second's thousands.
            found.append((code, first * 1000 if thousands and first < 1000 else first))
        found.append((code, value))
    if not found:
        return None
    currency = found[0][0]
    values = [value for cur, value in found if cur == currency][:2]
    low, high = min(values), max(values)
    return Salary(currency, _period(line, values), low, high if high != low else None)


def salary_in_text(text: str) -> Salary | None:
    """The salary named in the text: range or single value, as written.

    Only lines that speak of salary count, without benefit words. Postings listing
    several countries are read for the EUR line first.
    """
    candidates = [
        salary
        for line in text.splitlines()
        if SALARY_WORDS.search(line) and not NOT_SALARY.search(line)
        if (salary := _line_salary(line)) is not None
    ]
    eur = [c for c in candidates if c.currency == "EUR"]
    preferred = eur or candidates
    return preferred[0] if preferred else None


def yearly_eur(salary: Salary) -> tuple[int | None, int | None]:
    """Gross per year in EUR; values outside the plausible range are dropped."""
    if salary.currency != "EUR":
        return None, None
    factor = PER_PERIOD[salary.period]

    def plausible(value: float | None) -> int | None:
        if value is None:
            return None
        yearly = round(value * factor)
        return yearly if SALARY_RANGE[0] <= yearly <= SALARY_RANGE[1] else None

    return plausible(salary.low), plausible(salary.high)


# --- degree -------------------------------------------------------------------------------

DEGREES = {
    "phd": re.compile(r"\b(promotion|promoviert\w*|ph\.?\s?d|doktor\w*)\b", re.I),
    "university": re.compile(
        r"(studium|studiengang|hochschul\w*|universität\w*|university|bachelor|"
        r"(?<!scrum )\bmaster\b|\bdiplom(?!at)\w*|degree in|\bfh\b|\btu\b)",
        re.IGNORECASE,
    ),
    "vocational": re.compile(
        r"(ausbildung als|abgeschlossene\w* (berufs)?ausbildung|berufsausbildung|"
        r"fachinformatiker\w*|it-ausbildung|technische\w* ausbildung|kaufmännische\w* ausbildung)",
        re.IGNORECASE,
    ),
}
# Mentions in the company or benefits part ("wir unterstützen dein Studium") are not
# requirements; only lines that read like one count.
REQUIREMENT_LINE = re.compile(
    r"abgeschlossen\w*|erfolgreich\w*|vorausgesetzt|voraussetzung|hast|bringst|verfügst|"
    r"you have|you hold|required|requirement|qualifikation|degree|oder vergleichbar\w*|"
    r"or (equivalent|similar)",
    re.IGNORECASE,
)


def degrees(text: str) -> list[str]:
    """Degrees a posting asks for (any of them suffices), e.g. ['university', 'vocational']."""
    found: set[str] = set()
    for line in text.splitlines():
        if not REQUIREMENT_LINE.search(line):
            continue
        found.update(key for key, pattern in DEGREES.items() if pattern.search(line))
    return [key for key in DEGREES if key in found]
