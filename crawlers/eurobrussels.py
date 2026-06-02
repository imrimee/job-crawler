"""
crawlers/eurobrussels.py
eurobrussels.com 크롤러

브뤼셀 EU Affairs 특화 채용 플랫폼.
싱크탱크, NGO, EU 기관, 로비펌, 무역협회 공고.
"""

import re
import urllib.request
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
from crawlers.base import BaseCrawler, Job


class EuroBrusselsCrawler(BaseCrawler):

    BASE_URL = "https://www.eurobrussels.com"
    SEARCH_URL = "https://www.eurobrussels.com/jobs"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def fetch_jobs(self) -> list[Job]:
        keywords = self.conditions.get("keywords", [])
        all_jobs: list[Job] = []
        seen_ids: set[str] = set()

        self.log("크롤링 시작")

        for keyword in keywords:
            self.log(f"검색 중: '{keyword}'")
            jobs = self._search(keyword, seen_ids)
            self.log(f"  → {len(jobs)}개 신규 공고 수집")
            all_jobs.extend(jobs)

        self.log(f"크롤링 완료 — 총 {len(all_jobs)}개")
        return all_jobs

    def _search(self, keyword: str, seen_ids: set) -> list[Job]:
        params = urllib.parse.urlencode({"keywords": keyword})
        url = f"{self.SEARCH_URL}?{params}"

        jobs = []
        for page in range(1, 4):
            page_url = f"{url}&page={page}"
            try:
                req = urllib.request.Request(page_url, headers=self.HEADERS)
                with urllib.request.urlopen(req, timeout=20) as resp:
                    html = resp.read().decode("utf-8", errors="replace")
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

        cards = soup.select(
            "div.job-listing, div.job-item, article.job, "
            "li[class*='job'], div[class*='vacancy'], "
            "div[class*='JobItem'], tr.job-row"
        )

        for card in cards:
            try:
                title_el = card.select_one(
                    "h2 a, h3 a, h4 a, a.job-title, "
                    "a[class*='title'], td.job-title a"
                )
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                href  = title_el.get("href", "")
                url   = href if href.startswith("http") else self.BASE_URL + href

                job_id = re.search(r"/(\d+)(?:[/?]|$)", href)
                job_id = job_id.group(1) if job_id else re.sub(r"\W+", "_", title)[:30]
                if job_id in seen_ids:
                    continue

                org_el   = card.select_one("[class*='employer'], [class*='organization'], [class*='company']")
                org      = org_el.get_text(strip=True) if org_el else "Unknown"

                loc_el   = card.select_one("[class*='location'], [class*='city']")
                location = loc_el.get_text(strip=True) if loc_el else "Brussels"

                cat_el   = card.select_one("[class*='category'], [class*='sector'], [class*='type']")
                category = cat_el.get_text(strip=True) if cat_el else ""

                date_el      = card.select_one("[class*='deadline'], [class*='date'], [class*='closing']")
                deadline_str = date_el.get_text(strip=True) if date_el else ""
                deadline_dt  = self._parse_date(deadline_str)

                seen_ids.add(job_id)
                jobs.append(Job(
                    title=title,
                    organization=org,
                    location=location,
                    category=category,
                    deadline=deadline_str,
                    url=url,
                    job_id=job_id,
                    source_site="EuroBrussels",
                    deadline_dt=deadline_dt,
                    keywords_matched=[keyword],
                ))
            except Exception:
                continue

        return jobs

    def _parse_date(self, s: str) -> datetime | None:
        for fmt in ["%d %B %Y", "%d %b %Y", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"]:
            try:
                return datetime.strptime(s.strip(), fmt)
            except ValueError:
                continue
        return None
