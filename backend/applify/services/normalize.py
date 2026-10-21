"""Normalization of job postings for deduplication (§5.2)."""

import hashlib
import re
import unicodedata

# Legal forms and their usual spellings, removed from company names.
LEGAL_FORMS = re.compile(
    r"\b(gmbh\s*&\s*co\.?\s*(kgaa|kg|ohg)|ggmbh|gmbh|mbh|ag|se|kgaa|kg|ohg|gbr|ug"
    r"(\s*\(haftungsbeschränkt\))?|e\.\s?v\.?|e\.\s?k\.?|ltd\.?|inc\.?|llc|plc|b\.?v\.?|"
    r"s\.?a\.?|co\.?|corp\.?|holding|group|gruppe|deutschland|germany)(?=\W|$)",
    re.IGNORECASE,
)
# "(m/w/d)", "(w/m/d)", "(all genders)", "(d/f/m)", "m/w/d", "(gn)" and similar.
GENDER_MARKERS = re.compile(
    r"[(\[]?\s*\b([mwfdx]\s*[/|,]\s*){1,3}[mwfdx]\b\s*[)\]]?|"
    r"[(\[]\s*(all\s+genders?|alle\s+geschlechter|gn|genderneutral|w/m/x/d)\s*[)\]]|"
    r"\ball\s+genders?\b",
    re.IGNORECASE,
)
# German gender suffixes: "Entwickler*in", "Entwickler:in", "EntwicklerIn", "Entwickler/-in".
GENDER_SUFFIX = re.compile(r"(?<=[a-zäöü])([*:_]in(nen)?|In(nen)?|\s?/\s?-?in(nen)?)\b")

REMOTE_WORDS = re.compile(
    r"\b(100\s?%\s*remote|full(y)?[\s-]remote|voll(ständig)?\s*remote|remote[\s-]first|"
    r"remote\s*only|nur\s*remote|deutschlandweit\s*remote|ortsunabhängig)\b",
    re.IGNORECASE,
)
HYBRID_WORDS = re.compile(
    r"\b(hybrid\w*|home[\s-]?office|mobiles?\s*arbeiten|remote|teilweise\s*remote|"
    r"mobile\s*work(ing)?|work\s*from\s*home)\b",
    re.IGNORECASE,
)

_NUMBER = r"(\d{1,3}(?:[.\s]\d{3})+|\d+(?:[,.]\d+)?)\s*(k|tsd\.?|tausend)?"
SALARY_RANGE = re.compile(
    rf"{_NUMBER}\s*(?:€|eur|euro)?\s*(?:-|–|bis)\s*{_NUMBER}\s*(?:€|eur|euro)", re.IGNORECASE
)
SALARY_SINGLE = re.compile(rf"(?:ab|mindestens|from)?\s*{_NUMBER}\s*(?:€|eur|euro)", re.IGNORECASE)
MONTHLY = re.compile(r"monat|month|/\s*m\b|p\.\s?m\.", re.IGNORECASE)


def _fold(text: str) -> str:
    """Lowercase, umlauts and accents folded, punctuation as spaces."""
    text = text.casefold().replace("ß", "ss")
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^\w#+]+", " ", text)).strip()


def normalize_company(name: str) -> str:
    return _fold(LEGAL_FORMS.sub(" ", name.replace("&", " ")))


def clean_title(title: str, company: str = "") -> str:
    """Display title without gender markers or a "Company: " prefix."""
    if company and ":" in title:
        prefix, rest = title.split(":", 1)
        if normalize_company(prefix) == normalize_company(company):
            title = rest
    title = GENDER_SUFFIX.sub("", GENDER_MARKERS.sub(" ", title))
    return re.sub(r"\s+", " ", title).strip(" -–|,")


def normalize_title(title: str, company: str = "") -> str:
    return _fold(clean_title(title, company))


def normalize_city(city: str) -> str:
    """'Münster, Westfalen' and 'Berlin-Mitte' → 'munster', 'berlin'."""
    return _fold(re.split(r"[,/(]|\s-\s|-(?=[A-ZÄÖÜ])", city)[0])


def detect_remote(text: str) -> str | None:
    """'remote' or 'hybrid' if the text says so; None means unknown or on site."""
    if REMOTE_WORDS.search(text):
        return "remote"
    if HYBRID_WORDS.search(text):
        return "hybrid"
    return None


def _amount(number: str, thousands: str | None) -> float:
    if re.fullmatch(r"\d{1,3}(?:[.\s]\d{3})+", number):
        value = float(re.sub(r"[.\s]", "", number))
    else:
        value = float(number.replace(",", "."))
    return value * 1000 if thousands else value


def parse_salary(text: str) -> tuple[int | None, int | None]:
    """Yearly gross salary range from free text; monthly values are multiplied by 12."""
    for match in SALARY_RANGE.finditer(text):
        low, high = _amount(match[1], match[2]), _amount(match[3], match[4] or match[2])
        if low > high or low < 500:
            continue
        context = text[match.end() : match.end() + 30]
        factor = 12 if MONTHLY.search(context) or high < 15000 else 1
        return int(low * factor), int(high * factor)
    for match in SALARY_SINGLE.finditer(text):
        value = _amount(match[1], match[2])
        if value < 500:
            continue
        context = text[match.end() : match.end() + 30]
        factor = 12 if MONTHLY.search(context) or value < 15000 else 1
        return int(value * factor), None
    return None, None


def fingerprint(company: str, title: str, city: str) -> str:
    """Exact-duplicate key: hash(company_norm + title_norm + city_norm)."""
    parts = (normalize_company(company), normalize_title(title, company), normalize_city(city))
    key = "|".join(parts)
    return hashlib.sha1(key.encode()).hexdigest()
