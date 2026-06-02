"""
crawlers/reliefweb_eu.py
ReliefWeb EU 크롤러

ReliefWeb API v1이 2026년에 종료(410 Gone)되어 HTML 스크래핑으로 전환.
EU는 국가 필터 없이 키워드 검색 (aggregator에서 키워드 재필터링).
"""

import urllib.request
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
from crawlers.base import BaseCrawler, Job


class ReliefWebEuCrawler(BaseCrawler):

    BASE_URL = "https://reliefweb.int"
    SEARCH_URL = "https://reliefweb.int/jobs"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    # 유럽 주요 국가명 (필터용)
    EU_COUNTRIES = {
        "Belgium", "France", "Germany", "Switzerland", "Austria",
        "Netherlands", "Sweden", "Norway", "Denmark", "Italy",
        "Spain", "Poland", "Finland", "Portugal", "Luxembourg",
        "Hungary", "Romania", "Czech Republic", "Slovakia", "Greece",
        "Ukraine", "Turkey", "UK", "United Kingdom",
    }

    def fetch_jobs(self) -> list[Job]:
        keywords = self.conditions.get("keywords", [])
        all_jobs: list[Job] = []
        seen_ids: set[str] = set()

        self.log("크롤링 시작 (HTML 스크래핑 — 유럽 필터)")

        for keyword in keywords:
            self.log(f"검색 중: '{keyword}'")
            jobs = self._search(keyword, seen_ids)
            self.log(f"  → {len(jobs)}개 신규 공고 수집")
            all_jobs.extend(jobs)

        self.log(f"크롤링 완료 — 총 {len(all_jobs)}개")
        return all_jobs

    def _search(self, keyword: str, seen_ids: set) -> list[Job]:
        jobs = []
        for page in range(0, 3):
            params = urllib.parse.urlencode({
                "search": keyword,
                "page": page,
            })
            url = f"{self.SEARCH_URL}?{params}"
            try:
                req = urllib.request.Request(url, headers=self.HEADERS)
                with urllib.request.urlopen(req, timeout=20) as r:
                    html = r.read().decode("utf-8", errors="replace")
            except Exception as e:
                self.log(f"  ⚠ 페이지 {page} 로드 실패: {e}")
                break

            page_jobs = self._parse(html, keyword, seen_ids)
            if not page_jobs:
                break
            jobs.extend(page_jobs)

        return jobs

    def _parse(self, html: str, keyword: str, seen_ids: set) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []

        for card in soup.select("article.rw-river-article--job"):
            try:
                job_id = card.get("data-id", "")
                if not job_id or job_id in seen_ids:
                    continue

                # 유럽 국가 필터
                country_el = card.select_one("p.rw-entity-country-slug a")
                country    = country_el.get_text(strip=True) if country_el else ""
                if country and country not in self.EU_COUNTRIES:
                    continue

                title_el = card.select_one("h3.rw-river-article__title a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                url   = title_el.get("href", self.SEARCH_URL)

                org_el = card.select_one("dd.rw-entity-meta__tag-value--source a")
                org    = org_el.get_text(strip=True) if org_el else "Unknown"

                posted_el   = card.select_one("dd.rw-entity-meta__tag-value--posted time")
                date_posted = posted_el.get("datetime", "")[:10] if posted_el else ""

                closing_el   = card.select_one("dd.rw-entity-meta__tag-value--closing-date time")
                deadline_str = closing_el.get("datetime", "")[:10] if closing_el else ""
                deadline_dt  = self._parse_date(deadline_str)

                seen_ids.add(job_id)
                jobs.append(Job(
                    title=title,
                    organization=org,
                    location=country,
                    category="",
                    deadline=deadline_str,
                    url=url,
                    job_id=job_id,
                    date_posted=date_posted,
                    source_site="ReliefWeb (EU)",
                    deadline_dt=deadline_dt,
                    keywords_matched=[keyword],
                ))
            except Exception:
                continue

        return jobs

    def _parse_date(self, s: str) -> datetime | None:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d")
        except Exception:
            return None
