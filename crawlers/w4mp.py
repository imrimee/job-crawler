"""
crawlers/w4mp.py
w4mp.org 크롤러

영국 의회·Westminster 특화 채용 플랫폼.
정적 WordPress 기반이라 requests + BeautifulSoup으로 처리합니다.
"""

import re
import urllib.request
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
from crawlers.base import BaseCrawler, Job


class W4MPCrawler(BaseCrawler):

    BASE_URL = "https://www.w4mp.org"
    JOBS_URL = "https://www.w4mp.org/jobs"

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

        # W4MP는 전체 목록에서 키워드 필터링하는 방식
        # (검색 기능이 제한적이므로 전체 공고 수집 후 필터)
        raw_jobs = self._fetch_all(seen_ids)
        self.log(f"  전체 공고 수집: {len(raw_jobs)}개")

        # 키워드 필터링
        for job in raw_jobs:
            searchable = (job.title + " " + job.description).lower()
            matched = [kw for kw in keywords if kw.lower() in searchable]
            if matched or not keywords:  # 키워드가 없으면 전체 포함
                job.keywords_matched = matched
                all_jobs.append(job)

        self.log(f"크롤링 완료 — 총 {len(all_jobs)}개 (키워드 매칭)")
        return all_jobs

    def _fetch_all(self, seen_ids: set) -> list[Job]:
        jobs = []
        for page_num in range(1, 4):  # 최대 3페이지
            url = f"{self.JOBS_URL}/page/{page_num}/" if page_num > 1 else self.JOBS_URL
            try:
                req = urllib.request.Request(url, headers=self.HEADERS)
                with urllib.request.urlopen(req, timeout=20) as resp:
                    html = resp.read().decode("utf-8", errors="replace")
            except Exception as e:
                self.log(f"  ⚠ 페이지 {page_num} 로드 실패: {e}")
                break

            page_jobs = self._parse_html(html, seen_ids)
            if not page_jobs:
                break
            jobs.extend(page_jobs)

        return jobs

    def _parse_html(self, html: str, seen_ids: set) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []

        # W4MP는 WordPress 기반 — post 형태로 공고 표시
        cards = soup.select(
            "article.post, div.job-listing, li.job, "
            "div[class*='vacancy'], article[class*='job'], "
            "div.entry, article"
        )

        for card in cards:
            try:
                title_el = card.select_one("h1 a, h2 a, h3 a, .entry-title a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 5:
                    continue

                href = title_el.get("href", "")
                url  = href if href.startswith("http") else self.BASE_URL + href

                job_id = re.search(r"/(\d+)/", href)
                job_id = (
                    job_id.group(1) if job_id
                    else re.sub(r"\W+", "_", title)[:30]
                )

                if job_id in seen_ids:
                    continue

                # 내용 요약 (description으로 사용)
                content_el = card.select_one(".entry-content, .post-content, p")
                description = content_el.get_text(strip=True)[:300] if content_el else ""

                # 마감일
                deadline_str = ""
                full_text = card.get_text()
                for line in full_text.split("\n"):
                    if any(w in line.lower() for w in ["deadline", "closing", "apply by"]):
                        m = re.search(r"\d{1,2}\s+\w+\s+\d{4}|\d{4}-\d{2}-\d{2}", line)
                        if m:
                            deadline_str = m.group(0)
                            break

                # 게시일
                date_el    = card.select_one("time, .date, .posted-on, [class*='date']")
                date_posted = ""
                if date_el:
                    date_posted = date_el.get("datetime", date_el.get_text(strip=True))[:10]

                deadline_dt = self._parse_date(deadline_str)
                seen_ids.add(job_id)

                jobs.append(Job(
                    title=title,
                    organization="Westminster / UK Parliament",
                    location="London, United Kingdom",
                    category="Parliamentary / Public Affairs",
                    deadline=deadline_str,
                    url=url,
                    job_id=job_id,
                    date_posted=date_posted,
                    description=description,
                    source_site="W4MP",
                    deadline_dt=deadline_dt,
                    keywords_matched=[],
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
