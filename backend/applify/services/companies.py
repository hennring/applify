"""Company watchlist (F7a): companies from postings, discovery and the user."""

import re
from dataclasses import replace
from datetime import datetime
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from applify.db.models import Company, Job, UserCompany
from applify.services.normalize import normalize_company
from applify.sources.ats import find_ats
from applify.sources.base import JobPosting

URL = re.compile(r"(?:https?://|\bwww\.)[^\s<>()\"'\]]+", re.IGNORECASE)
EMAIL_DOMAIN = re.compile(r"\b[\w.+-]+@((?:[\w-]+\.)+[a-z]{2,})\b", re.IGNORECASE)
# Domains in postings that are not the employer's: job boards, social media, mail providers.
FOREIGN_DOMAINS = frozenset(
    [
        "arbeitsagentur.de",
        "stepstone.de",
        "indeed.com",
        "indeed.de",
        "linkedin.com",
        "xing.com",
        "glassdoor.de",
        "monster.de",
        "get-in-it.de",
        "jobexport.de",
        "gute-jobs.de",
        "empfehlungsbund.de",
        "finest-jobs.com",
        "jobboerse-direkt.de",
        "persy.jobs",
        "compleet.com",
        "heyjobs.co",
        "stellenanzeigen.de",
        "online-stellenmarkt.net",
        "bewerbung.jobs",
        "arbeitnow.com",
        "adzuna.de",
        "kununu.com",
        "facebook.com",
        "instagram.com",
        "youtube.com",
        "twitter.com",
        "x.com",
        "tiktok.com",
        "google.com",
        "gmail.com",
        "gmx.de",
        "gmx.net",
        "web.de",
        "t-online.de",
        "outlook.com",
        "hotmail.com",
        "yahoo.com",
        "icloud.com",
        "service.bund.de",
        "interamt.de",
        "wa.me",
    ]
)
MAX_HINTS = 10


def registered_domain(host: str) -> str:
    """'karriere.example.co.uk' → 'example.co.uk', 'www.example.de' → 'example.de'."""
    parts = host.lower().strip(".").split(".")
    keep = 3 if len(parts) > 2 and parts[-2] in ("co", "com", "org") else 2
    return ".".join(parts[-keep:])


def same_company(a: str, b: str) -> bool:
    """Names equal after normalization, ignoring spaces, or one extends the other."""
    na, nb = normalize_company(a), normalize_company(b)
    if not na or not nb:
        return False
    if na.replace(" ", "") == nb.replace(" ", ""):
        return True
    return na.startswith(f"{nb} ") or nb.startswith(f"{na} ")


def domain_fits(domain: str, name: str) -> bool:
    """Whether a domain plausibly belongs to the company ("chrono24.com" ↔ "Chrono24 GmbH")."""
    label = domain.split(".")[0].replace("-", "")
    norm = normalize_company(name)
    joined = norm.replace(" ", "")
    if len(label) < 3 or not joined:
        return False
    if label in joined or joined in label:
        return True
    return any(len(token) >= 4 and token in label for token in norm.split())


def posting_hints(posting: JobPosting) -> tuple[list[str], str | None]:
    """URLs worth a look for the company's careers page, and a likely website."""
    text = f"{posting.description}\n{posting.raw.get('externeURL') or ''}"
    urls, website = [], None
    for raw in URL.findall(text):
        url = raw.rstrip(".,;:!?")
        url = url if url.lower().startswith("http") else f"https://{url}"
        host = urlsplit(url).netloc.lower()
        if not host or registered_domain(host) in FOREIGN_DOMAINS:
            continue
        if find_ats(url) or domain_fits(registered_domain(host), posting.company):
            urls.append(url)
    for domain in EMAIL_DOMAIN.findall(posting.description):
        domain = registered_domain(domain)
        if domain not in FOREIGN_DOMAINS and domain_fits(domain, posting.company):
            website = website or f"https://www.{domain}"
    for url in urls:
        host = registered_domain(urlsplit(url).netloc)
        if not find_ats(url) and domain_fits(host, posting.company):
            website = website or f"https://{urlsplit(url).netloc}"
    return list(dict.fromkeys(urls)), website


class CompanyRegistry:
    """Get-or-create companies within one session, cached by normalized name."""

    def __init__(self, session: Session, user_id: int) -> None:
        self.session = session
        self.user_id = user_id
        self._cache: dict[str, Company] = {}
        self._linked: set[int] = set()

    def get_or_create(
        self, name: str, discovered_from: str, *, website: str | None = None
    ) -> Company | None:
        norm = normalize_company(name)[:300]
        if not norm:
            return None
        company = self._cache.get(norm) or self.session.scalar(
            select(Company).where(Company.name_norm == norm)
        )
        if company is None:
            company = Company(
                name=name.strip()[:300],
                name_norm=norm,
                website=website,
                discovered_from=discovered_from,
                ats_type="unknown",
                detection_status="pending",
                hints={},
            )
            self.session.add(company)
            self.session.flush()
        elif website and not company.website:
            company.website = website
            if company.ats_type == "unknown":
                company.detection_status = "pending"  # new lead, try again
        self._cache[norm] = company
        self.link(company)
        return company

    def link(self, company: Company, status: str = "candidate") -> UserCompany:
        link = self.session.scalar(
            select(UserCompany).where(
                UserCompany.user_id == self.user_id, UserCompany.company_id == company.id
            )
        )
        if link is None:
            link = UserCompany(user_id=self.user_id, company_id=company.id, status=status)
            self.session.add(link)
            self.session.flush()
        self._linked.add(company.id)
        return link

    def attach(self, job: Job, posting: JobPosting) -> Company | None:
        """Company of a posting from a job source; collects leads for the detection."""
        # Known listings come as short search results; the stored job has the full text.
        if len(job.description) > len(posting.description):
            posting = replace(posting, description=job.description)
        urls, website = posting_hints(posting)
        company = self.session.get(Company, job.company_id) if job.company_id else None
        if company is None:
            company = self.get_or_create(posting.company, "jobs", website=website)
            if company is None:
                return None
            job.company_id = company.id
        else:
            if company.id not in self._linked:
                self.link(company)
            if website and not company.website:
                company.website = website
                if company.ats_type == "unknown":
                    company.detection_status = "pending"
        known = list((company.hints or {}).get("urls") or [])
        new = [u for u in urls if u not in known]
        if new:
            company.hints = {**(company.hints or {}), "urls": (known + new)[:MAX_HINTS]}
            if company.ats_type == "unknown" and any(find_ats(u) for u in new):
                company.detection_status = "pending"
        return company


def mark_checked(company: Company, now: datetime, error: str | None = None) -> None:
    company.last_checked_at = now
    company.last_error = error[:500] if error else None
