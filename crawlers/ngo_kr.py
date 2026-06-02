"""
crawlers/ngo_kr.py
ngo.or.kr 크롤러 (한국NGO협의회)

국내 NGO·시민사회 특화 채용 포털.
WordPress 기반 정적 HTML. requests + BeautifulSoup.
"""

import re
import urllib.request
from datetime import datetime
from bs4 import BeautifulSoup
from crawlers.base import BaseCrawler, Job


class NgoKrCrawler(BaseCrawler):

    BASE_URL = "https://www.ngo.or.kr"
    JOBS_URL = "https://www.ngo.or.kr/category/jobs/"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    }

    def fetch_jobs(self) -> list[Job]:
        all_keywords = self.conditions.get("keywords", [])
        kr_keywords  = self.conditions.get("keywords_kr", [])
        combined     = all_keywords + kr_keywords

        self.log("크롤링 시작 (전체 수집 후 키워드 필터)")
        raw_jobs: list[Job] = []
        seen_ids: set[str] = set()

        for page_num in range(1, 4):
            url = f"{self.JOBS_URL}page/{page_num}/" if page_num > 1 else self.JOBS_URL
            try:
                req = urllib.request.Request(url, headers=self.HEADERS)
                with urllib.request.urlopen(req, timeout=20) as resp:
                    html = resp.read().decode("utf-8", errors="replace")
            except Exception as e:
                self.log(f"  ⚠ 페이지 {page_num} 실패: {e}")
                break

            page_jobs = self._parse_html(html, seen_ids)
            if not page_jobs:
                break
            raw_jobs.extend(page_jobs)

        self.log(f"  전체 수집: {len(raw_jobs)}개")

        # 키워드 필터링
        result = []
        for job in raw_jobs:
            searchable = (job.title + " " + job.description).lower()
            matched = [kw for kw in combined if kw.lower() in searchable]
            if matched or not combined:
                job.keywords_matched = matched
                result.append(job)

        self.log(f"크롤링 완료 — {len(result)}개")
        return result

    def _parse_html(self, html: str, seen_ids: set) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []

        articles = soup.select("article, div.post, li.post")
        for article in articles:
            try:
                title_el = article.select_one("h1 a, h2 a, h3 a, .entry-title a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                href = title_el.get("href", "")
                url  = href if href.startswith("http") else (self.BASE_URL + href)

                # WordPress post ID
                post_id = re.search(r"/(\d+)/", href)
                job_id  = post_id.group(1) if post_id else re.sub(r"\W+", "_", title)[:30]

                if job_id in seen_ids:
                    continue

                # 본문 요약
                content_el  = article.select_one(".entry-content p, .post-excerpt, .excerpt")
                description = content_el.get_text(strip=True)[:200] if content_el else ""

                # 날짜
                date_el     = article.select_one("time[datetime], .entry-date, .published")
                date_posted = ""
                if date_el:
                    date_posted = date_el.get("datetime", date_el.get_text(strip=True))[:10]

                # 마감일
                deadline_str = ""
                full_text = article.get_text()
                for line in full_text.split("\n"):
                    if any(w in line for w in ["마감", "접수", "지원기간", "모집기간"]):
                        m = re.search(r"\d{4}[.\-]\d{2}[.\-]\d{2}", line)
                        if m:
                            deadline_str = m.group(0)
                            break

                deadline_dt = self._parse_date(deadline_str)
                seen_ids.add(job_id)

                jobs.append(Job(
                    title=title,
                    organization="한국 NGO / 시민사회단체",
                    location="Korea",
                    category="NGO / 시민사회",
                    deadline=deadline_str,
                    url=url,
                    job_id=f"ngo_kr_{job_id}",
                    date_posted=date_posted,
                    description=description,
                    source_site="NGO잡스(한국NGO협의회)",
                    deadline_dt=deadline_dt,
                    keywords_matched=[],
                ))
            except Exception:
                continue
        return jobs

    def _parse_date(self, s: str) -> datetime | None:
        for fmt in ["%Y.%m.%d", "%Y-%m-%d"]:
            try:
                return datetime.strptime(s.strip(), fmt)
            except ValueError:
                continue
        return None
