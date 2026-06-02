"""
crawlers/osce_jobs.py
jobs.osce.org 크롤러

OSCE(유럽안보협력기구) 공식 채용 포털.
57개 회원국 대상, 한국 포함 비EU 국적 지원 가능.
"""

import re
import urllib.request
from datetime import datetime
from bs4 import BeautifulSoup
from crawlers.base import BaseCrawler, Job


class OsceJobsCrawler(BaseCrawler):

    LIST_URL = "https://jobs.osce.org/vacancies"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
    }

    def fetch_jobs(self) -> list[Job]:
        keywords = self.conditions.get("keywords", [])
        all_jobs: list[Job] = []
        seen_ids: set[str] = set()

        self.log("크롤링 시작")
        html = self._fetch(self.LIST_URL)
        if html:
            jobs = self._parse(html, keywords, seen_ids)
            all_jobs.extend(jobs)
            self.log(f"  → {len(jobs)}개 공고 수집")

        self.log(f"크롤링 완료 — 총 {len(all_jobs)}개")
        return all_jobs

    def _fetch(self, url: str) -> str | None:
        try:
            req = urllib.request.Request(url, headers=self.HEADERS)
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            self.log(f"  ⚠ 로드 실패: {e}")
            return None

    def _parse(self, html: str, keywords: list[str], seen_ids: set) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []

        for card in soup.select("div.job_list_row"):
            try:
                title_el = card.select_one("a.job_link")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                url   = title_el.get("href", "")

                # 키워드 매칭 확인
                matched = [kw for kw in keywords if kw.lower() in title.lower()]
                if not matched:
                    continue

                job_id_el = card.select_one("span.field_value")
                job_id    = job_id_el.get_text(strip=True) if job_id_el else re.sub(r"\W+", "_", title)[:30]
                if job_id in seen_ids:
                    continue

                loc_el   = card.select_one("a.location")
                location = loc_el.get_text(strip=True) if loc_el else "Europe"

                cat_el   = card.select_one("p.job_category span.jlr_value")
                category = cat_el.get_text(strip=True) if cat_el else ""

                desc_el     = card.select_one("p.jlr_description")
                description = desc_el.get_text(strip=True) if desc_el else ""

                seen_ids.add(job_id)
                jobs.append(Job(
                    title=title,
                    organization="OSCE",
                    location=location,
                    category=category,
                    deadline="",
                    url=url,
                    job_id=job_id,
                    description=description,
                    source_site="OSCE Jobs",
                    deadline_dt=None,
                    keywords_matched=matched,
                ))
            except Exception:
                continue

        return jobs
