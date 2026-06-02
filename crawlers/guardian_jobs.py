"""
crawlers/guardian_jobs.py
jobs.theguardian.com 크롤러

Guardian Jobs는 정적 HTML 기반으로 BeautifulSoup으로 파싱합니다.
NGO, 싱크탱크, 공공정책 분야 공고가 풍부합니다.
"""

import re
import urllib.request
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
from crawlers.base import BaseCrawler, Job


class GuardianJobsCrawler(BaseCrawler):

    BASE_URL = "https://jobs.theguardian.com"
    SEARCH_URL = "https://jobs.theguardian.com/jobs"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-GB,en;q=0.9",
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
        params = urllib.parse.urlencode({
            "keywords": keyword,
            "location": "United Kingdom",
            "radius": "0",
        })
        url = f"{self.SEARCH_URL}?{params}"

        jobs = []
        for page_num in range(1, 4):  # 최대 3페이지
            page_url = f"{url}&page={page_num}"
            try:
                req = urllib.request.Request(page_url, headers=self.HEADERS)
                with urllib.request.urlopen(req, timeout=20) as resp:
                    html = resp.read().decode("utf-8", errors="replace")
            except Exception as e:
                self.log(f"  ⚠ 페이지 {page_num} 로드 실패: {e}")
                break

            page_jobs = self._parse_html(html, keyword, seen_ids)
            if not page_jobs:
                break
            jobs.extend(page_jobs)

        return jobs

    def _parse_html(self, html: str, keyword: str, seen_ids: set) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []

        # Guardian Jobs 공고 카드
        cards = soup.select(
            "li.lister__item, div.job-item, article.job-result, "
            "div[class*='JobItem'], li[class*='job']"
        )

        for card in cards:
            try:
                title_el = card.select_one(
                    "h2 a, h3 a, a[class*='title'], a[class*='JobTitle']"
                )
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                href  = title_el.get("href", "")
                url   = href if href.startswith("http") else self.BASE_URL + href

                job_id = re.search(r"/(\d+)/", href)
                job_id = job_id.group(1) if job_id else re.sub(r"\W+", "_", title)[:30]

                if job_id in seen_ids:
                    continue

                org_el   = card.select_one("[class*='employer'], [class*='company'], [class*='recruiter']")
                org      = org_el.get_text(strip=True) if org_el else "Unknown"

                loc_el   = card.select_one("[class*='location'], [class*='Location']")
                location = loc_el.get_text(strip=True) if loc_el else "United Kingdom"

                # 마감일
                deadline_str = ""
                for el in card.select("*"):
                    txt = el.get_text(strip=True)
                    if any(w in txt.lower() for w in ["closing", "deadline", "expires", "apply by"]):
                        m = re.search(r"\d{1,2}\s+\w+\s+\d{4}|\d{4}-\d{2}-\d{2}", txt)
                        if m:
                            deadline_str = m.group(0)
                            break

                # 섹터/카테고리
                sec_el   = card.select_one("[class*='sector'], [class*='category'], [class*='type']")
                category = sec_el.get_text(strip=True) if sec_el else ""

                date_el    = card.select_one("[class*='date'], [class*='posted']")
                date_posted = date_el.get_text(strip=True) if date_el else ""

                deadline_dt = self._parse_date(deadline_str)

                seen_ids.add(job_id)
                jobs.append(Job(
                    title=title,
                    organization=org,
                    location=location,
                    category=category,
                    deadline=deadline_str,
                    url=url,
                    job_id=job_id,
                    date_posted=date_posted,
                    source_site="Guardian Jobs",
                    deadline_dt=deadline_dt,
                    keywords_matched=[keyword],
                ))
            except Exception:
                continue

        return jobs

    def _parse_date(self, s: str) -> datetime | None:
        for fmt in ["%d %B %Y", "%d %b %Y", "%Y-%m-%d", "%B %d, %Y"]:
            try:
                return datetime.strptime(s.strip(), fmt)
            except ValueError:
                continue
        return None
