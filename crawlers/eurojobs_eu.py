"""
crawlers/eurojobs_eu.py
eurojobs.com 크롤러

유럽 전역 영어권 취업 공고 전문 플랫폼.
검색 URL: https://www.eurojobs.com/jobs?q=KEYWORD
"""

import re
import urllib.request
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
from crawlers.base import BaseCrawler, Job


class EuroJobsEuCrawler(BaseCrawler):

    BASE_URL = "https://www.eurojobs.com"
    SEARCH_URL = "https://www.eurojobs.com/jobs"

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
        params = urllib.parse.urlencode({"q": keyword})
        url = f"{self.SEARCH_URL}?{params}"
        jobs = []

        try:
            req = urllib.request.Request(url, headers=self.HEADERS)
            with urllib.request.urlopen(req, timeout=20) as r:
                html = r.read().decode("utf-8", errors="replace")
        except Exception as e:
            self.log(f"  ⚠ 로드 실패: {e}")
            return []

        return self._parse(html, keyword, seen_ids)

    def _parse(self, html: str, keyword: str, seen_ids: set) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []

        for card in soup.select("article.ej-job-result"):
            try:
                title_el = card.select_one("a.ej-job-result__title")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                url   = title_el.get("href", "")

                m = re.search(r"/jobs/(\d+)/", url)
                job_id = m.group(1) if m else re.sub(r"\W+", "_", title)[:30]
                if job_id in seen_ids:
                    continue

                # meta: Location / Company / Posted
                meta_el  = card.select_one("div.ej-job-result__meta")
                location = ""
                org      = ""
                date_posted = ""

                if meta_el:
                    spans = meta_el.find_all("span")
                    for span in spans:
                        strong = span.find("strong")
                        if not strong:
                            continue
                        label = strong.get_text(strip=True).rstrip(":")
                        value = span.get_text(strip=True).replace(strong.get_text(strip=True), "").strip().lstrip(":")
                        if label == "Location":
                            location = value
                        elif label == "Company":
                            org = value
                        elif label == "Posted":
                            date_posted = value

                seen_ids.add(job_id)
                jobs.append(Job(
                    title=title,
                    organization=org or "Unknown",
                    location=location or "Europe",
                    category="",
                    deadline="",
                    url=url if url.startswith("http") else self.BASE_URL + url,
                    job_id=job_id,
                    date_posted=date_posted,
                    source_site="EuroJobs",
                    deadline_dt=None,
                    keywords_matched=[keyword],
                ))
            except Exception:
                continue

        return jobs
