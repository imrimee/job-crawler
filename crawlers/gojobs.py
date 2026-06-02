"""
crawlers/gojobs.py
gojobs.go.kr 크롤러 (나라일터)

인사혁신처 운영 공무원 채용 통합 포털.
외교부·통일부·국제전문가 특채 공고 중심 수집.
requests + BeautifulSoup.
"""

import re
import urllib.request
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
from crawlers.base import BaseCrawler, Job


class GojobsCrawler(BaseCrawler):

    BASE_URL   = "https://www.gojobs.go.kr"
    SEARCH_URL = "https://www.gojobs.go.kr/jobsList.do"

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

        self.log("크롤링 시작")

        for keyword in combined:
            self.log(f"검색 중: '{keyword}'")
            jobs = self._search(keyword, seen_ids)
            self.log(f"  → {len(jobs)}개 수집")
            all_jobs.extend(jobs)

        self.log(f"크롤링 완료 — 총 {len(all_jobs)}개")
        return all_jobs

    def _search(self, keyword: str, seen_ids: set) -> list[Job]:
        params = urllib.parse.urlencode({
            "searchTxt": keyword,
            "pageIndex": 1,
        })
        url = f"{self.SEARCH_URL}?{params}"
        try:
            req = urllib.request.Request(url, headers=self.HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            self.log(f"  ⚠ 검색 실패: {e}")
            return []
        return self._parse_html(html, keyword, seen_ids)

    def _parse_html(self, html: str, keyword: str, seen_ids: set) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []

        rows = soup.select("table tbody tr, ul.list li, .job-item")
        for row in rows:
            try:
                title_el = row.select_one("a, td.title, .tit a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                href = title_el.get("href", "")
                url  = (self.BASE_URL + href) if href and not href.startswith("http") else (href or self.BASE_URL)
                job_id = re.search(r"[?&](?:recrutPblntSn|seq|no)=(\w+)", href)
                job_id = job_id.group(1) if job_id else re.sub(r"\W+", "_", title)[:30]

                if job_id in seen_ids:
                    continue

                # 부처명
                dept_el = row.select_one(".dept, td:nth-of-type(2), .organ")
                org = dept_el.get_text(strip=True) if dept_el else "대한민국 정부"

                # 마감일
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
                    organization=org,
                    location="Seoul, Korea",
                    category="공무원 / 공직",
                    deadline=deadline_str,
                    url=url,
                    job_id=f"gojobs_{job_id}",
                    description=title,
                    source_site="나라일터",
                    deadline_dt=deadline_dt,
                    keywords_matched=[keyword],
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
