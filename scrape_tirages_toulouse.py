#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Récupère tous les tirages des séances du club depuis :
https://dcdl-toulouse.over-blog.com/tag/seances%20du%20club/

Sorties :
- tirages_toulouse_chrono_desc.txt
- tirages_toulouse_chrono_desc.csv

Dépendances : pip install requests beautifulsoup4 lxml
"""

from __future__ import annotations

import csv
import re
import time
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://dcdl-toulouse.over-blog.com"
TAG_URL = f"{BASE}/tag/seances%20du%20club/"
OUT_TXT = Path("tirages_toulouse_chrono_desc.txt")
OUT_CSV = Path("tirages_toulouse_chrono_desc.csv")

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; DCDL-tirages-scraper/1.0)",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
})

DRAW_RE = re.compile(
    r"^\s*(?P<num>\d{1,3})\s*[).:-]\s*"
    r"(?P<draw>(?:[A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ]{8,12}|(?:\d{1,3}\s+){5}\d{1,3}\s*/\s*\d{2,4}))\s*$",
    re.I,
)
DATE_IN_TITLE_RE = re.compile(
    r"(?P<dow>lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche),?\s+"
    r"(?P<day>\d{1,2}|1er)\s+"
    r"(?P<month>[A-Za-zéûîôàèêùç]+)\s+"
    r"(?P<year>\d{4})",
    re.I,
)
MONTHS = {
    "janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "aout": 8, "août": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12, "décembre": 12,
}

@dataclass(frozen=True)
class Article:
    date: datetime
    title: str
    url: str

@dataclass(frozen=True)
class Tirage:
    date: datetime
    title: str
    url: str
    numero: int
    tirage: str


def fetch(url: str, retries: int = 4, sleep: float = 1.0) -> str:
    last = None
    for attempt in range(1, retries + 1):
        try:
            r = SESSION.get(url, timeout=30)
            r.raise_for_status()
            return r.text
        except requests.RequestException as exc:
            last = exc
            time.sleep(sleep * attempt)
    raise RuntimeError(f"Impossible de récupérer {url}: {last}")


def soup_text(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def parse_title_date(title: str) -> datetime | None:
    m = DATE_IN_TITLE_RE.search(title)
    if not m:
        return None
    day = 1 if m.group("day").lower() == "1er" else int(m.group("day"))
    month = MONTHS[m.group("month").lower()]
    year = int(m.group("year"))
    return datetime(year, month, day)


def parse_listing_date(raw: str) -> datetime | None:
    raw = re.sub(r"\s+", " ", raw).strip()
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if m:
        d, mo, y = map(int, m.groups())
        return datetime(y, mo, d)
    return None


def iter_listing_pages() -> Iterable[str]:
    page = 1
    seen = set()
    while True:
        url = TAG_URL if page == 1 else f"{TAG_URL}{page}"
        html = fetch(url)
        if url in seen:
            break
        seen.add(url)
        yield html

        soup = soup_text(html)
        page_links = []
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            full = urljoin(BASE, href)
            if full.startswith(TAG_URL):
                tail = full.rstrip("/").split("/")[-1]
                if tail.isdigit():
                    page_links.append(int(tail))
        if not page_links or page >= max(page_links):
            break
        page += 1


def extract_article_links_from_listing(html: str) -> list[Article]:
    soup = soup_text(html)
    out = []
    for h in soup.select("h2, h1"):
        a = h.find("a", href=True)
        if not a:
            continue
        title = a.get_text(" ", strip=True)
        if not ("Mercredi" in title or "Samedi" in title):
            continue
        url = urljoin(BASE, a["href"])
        # cherche la date proche dans le parent ou alentours
        raw_near = h.parent.get_text(" ", strip=True) if h.parent else ""
        dt = parse_listing_date(raw_near) or parse_title_date(title)
        if dt:
            out.append(Article(dt, title, url))
    return out


def clean_article_text(html: str) -> str:
    soup = soup_text(html)
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    article = soup.select_one("article") or soup.select_one(".ob-section") or soup
    # garder les séparations de lignes utiles
    return article.get_text("\n", strip=True)


def extract_draws(article: Article) -> list[Tirage]:
    html = fetch(article.url)
    text = clean_article_text(html)
    draws: list[Tirage] = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip().upper()
        m = DRAW_RE.match(line)
        if not m:
            continue
        draws.append(Tirage(article.date, article.title, article.url, int(m.group("num")), m.group("draw").replace(" / ", " / ")))
    return draws


def main() -> None:
    articles: dict[str, Article] = {}
    for html in iter_listing_pages():
        for article in extract_article_links_from_listing(html):
            articles[article.url] = article

    ordered_articles = sorted(articles.values(), key=lambda a: (a.date, a.url), reverse=True)
    print(f"Articles de séance trouvés : {len(ordered_articles)}")

    all_draws: list[Tirage] = []
    for i, article in enumerate(ordered_articles, 1):
        try:
            draws = extract_draws(article)
            all_draws.extend(draws)
            print(f"{i:>3}/{len(ordered_articles)} {article.date:%Y-%m-%d} : {len(draws):>3} tirages - {article.title}")
        except Exception as exc:
            print(f"ERREUR {article.url}: {exc}")

    all_draws.sort(key=lambda t: (t.date, t.url, t.numero), reverse=True)

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["date", "titre", "numero", "tirage", "url"])
        for t in all_draws:
            w.writerow([t.date.strftime("%Y-%m-%d"), t.title, t.numero, t.tirage, t.url])

    with OUT_TXT.open("w", encoding="utf-8") as f:
        current = None
        for t in all_draws:
            key = (t.date.strftime("%Y-%m-%d"), t.title, t.url)
            if key != current:
                if current is not None:
                    f.write("\n")
                f.write(f"{key[0]} - {key[1]}\n{key[2]}\n")
                current = key
            f.write(f"{t.numero}) {t.tirage}\n")

    print(f"\nTerminé : {len(all_draws)} tirages écrits dans {OUT_TXT} et {OUT_CSV}")


if __name__ == "__main__":
    main()
