"""
crawlers/koica.py
recruit.koica.go.kr 크롤러

KOICA 공식 채용 포털. 정적 HTML 기반.
한국어+영어 키워드 모두 지원.
"""

import re
import urllib.request
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
from crawlers.base import BaseCrawler, Job


class KoicaCrawler(BaseCrawler):

    BASE_URL  = "https://recruit.koica.go.kr"
    LIST_URL  = "https://recruit.koica.go.kr/BoardRecruitment/list.do"

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

        all_jobs: list[Job] = []
        seen_ids: set[str] = set()

        self.log("크롤링 시작 (전체 공고 수집 후 키워드 필터)")

        raw = self._fetch_all_pages(seen_ids)
        self.log(f"  전체 수집: {raw}개 공고")

        # 키워드 필터링
        for job in self._job_pool:
            searchable = (job.title + " " + job.description).lower()
            matched = [kw for kw in combined if kw.lower() in searchable]
            if matched or not combined:
                job.keywords_matched = matched
                all_jobs.append(job)

        self.log(f"크롤링 완료 — 키워드 매칭 {len(all_jobs)}개")
        return all_jobs

    def _fetch_all_pages(self, seen_ids: set) -> int:
        self._job_pool: list[Job] = []
        for page in range(1, 5):
            params = urllib.parse.urlencode({
                "pageIndex": page,
                "searchCondition": "",
                "searchKeyword": "",
            })
            url = f"{self.LIST_URL}?{params}"
            try:
                req = urllib.request.Request(url, headers=self.HEADERS)
                with urllib.request.urlopen(req, timeout=20) as resp:
                    html = resp.read().decode("utf-8", errors="replace")
            except Exception as e:
                self.log(f"  ⚠ 페이지 {page} 실패: {e}")
                break

            jobs = self._parse_html(html, seen_ids)
            if not jobs:
                break
            self._job_pool.extend(jobs)

        return len(self._job_pool)

    def _parse_html(self, html: str, seen_ids: set) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []

        rows = soup.select("table tbody tr, ul.board-list li, div.board-item")
        for row in rows:
            try:
                title_el = row.select_one("a, td.title, .subject a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                href  = title_el.get("href", "")
                url   = (self.BASE_URL + href) if href and not href.startswith("http") else (href or self.BASE_URL)
                job_id = re.search(r"[?&](?:seq|no|id|idx)=(\d+)", href)
                job_id = job_id.group(1) if job_id else re.sub(r"\W+", "_", title)[:30]

                if job_id in seen_ids:
                    continue

                cells = row.select("td")
                deadline_str = ""
                for cell in cells:
                    txt = cell.get_text(strip=True)
                    m = re.search(r"\d{4}[.\-/]\d{2}[.\-/]\d{2}", txt)
                    if m:
                        deadline_str = m.group(0)

                deadline_dt = self._parse_date(deadline_str)
                seen_ids.add(job_id)

                jobs.append(Job(
                    title=title,
                    organization="KOICA 한국국제협력단",
                    location="Seoul, Korea",
                    category="ODA / 개발협력",
                    deadline=deadline_str,
                    url=url,
                    job_id=f"koica_{job_id}",
                    date_posted="",
                    description=title,
                    source_site="KOICA",
                    deadline_dt=deadline_dt,
                    keywords_matched=[],
                ))
            except Exception:
                continue
        return jobs

    def _parse_date(self, s: str) -> datetime | None:
        for fmt in ["%Y.%m.%d", "%Y-%m-%d", "%Y/%m/%d"]:
            try:
                return datetime.strptime(s.strip(), fmt)
            except ValueError:
                continue
        return None
