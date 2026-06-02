"""
crawlers/mofa_unrecruit.py
unrecruit.mofa.go.kr 크롤러

외교부 국제기구 채용정보센터.
UN·전문기구 채용 공고를 한국어로 요약 제공하는 외교부 포털.
requests + BeautifulSoup으로 처리.
"""

import re
import urllib.request
from datetime import datetime
from bs4 import BeautifulSoup
from crawlers.base import BaseCrawler, Job


class MofaUnrecruitCrawler(BaseCrawler):

    BASE_URL = "https://www.unrecruit.mofa.go.kr"
    LIST_URL = "https://www.unrecruit.mofa.go.kr/board/list.do?menuNo=301"

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

        self.log("크롤링 시작")
        self._job_pool: list[Job] = []
        seen_ids: set[str] = set()

        for page in range(1, 5):
            url = f"{self.LIST_URL}&pageIndex={page}"
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

        self.log(f"  전체 수집: {len(self._job_pool)}개")

        # 키워드 필터
        result = []
        for job in self._job_pool:
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

        rows = soup.select("table tbody tr, .board-list li, .list-item")
        for row in rows:
            try:
                title_el = row.select_one("a, .title a, td.subject a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                href = title_el.get("href", "")
                url  = (self.BASE_URL + href) if href and not href.startswith("http") else (href or self.BASE_URL)

                job_id = re.search(r"[?&](?:seq|no|id|bbsSeq)=(\d+)", href)
                job_id = job_id.group(1) if job_id else re.sub(r"\W+", "_", title)[:30]

                if job_id in seen_ids:
                    continue

                # 날짜 추출
                deadline_str = ""
                for cell in row.select("td"):
                    txt = cell.get_text(strip=True)
                    m = re.search(r"\d{4}[.\-]\d{2}[.\-]\d{2}", txt)
                    if m:
                        deadline_str = m.group(0)

                deadline_dt = self._parse_date(deadline_str)
                seen_ids.add(job_id)

                jobs.append(Job(
                    title=title,
                    organization="국제기구 (외교부 채용정보센터)",
                    location="Korea / International",
                    category="국제기구",
                    deadline=deadline_str,
                    url=url,
                    job_id=f"mofa_un_{job_id}",
                    description=title,
                    source_site="국제기구채용정보센터(MOFA)",
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
