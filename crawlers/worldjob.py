"""
crawlers/worldjob.py
worldjob.or.kr 크롤러 (글로벌 청년 취업 드림)

한국산업인력공단 운영 해외취업 지원 포털.
K-Move·해외 인턴십·국제기구 채용 연계 정보 수집.
requests + BeautifulSoup.
"""

import re
import urllib.request
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
from crawlers.base import BaseCrawler, Job


class WorldJobCrawler(BaseCrawler):

    BASE_URL   = "https://www.worldjob.or.kr"
    SEARCH_URL = "https://www.worldjob.or.kr/jobs/jobsList.do"

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
            "searchKeyword": keyword,
            "pageIndex": 1,
            "pageUnit": 30,
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

        rows = soup.select("table tbody tr, ul.list li, .job-item, .board-item")
        for row in rows:
            try:
                title_el = row.select_one("a, td.tit, .subject a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                href = title_el.get("href", "")
                url  = (self.BASE_URL + href) if href and not href.startswith("http") else (href or self.BASE_URL)

                job_id = re.search(r"[?&](?:seq|no|id)=(\d+)", href)
                job_id = job_id.group(1) if job_id else re.sub(r"\W+", "_", title)[:30]

                if job_id in seen_ids:
                    continue

                cells = row.select("td")
                org = cells[1].get_text(strip=True) if len(cells) > 1 else "Unknown"

                # 국가/지역
                loc_text = ""
                for cell in cells:
                    txt = cell.get_text(strip=True)
                    if any(c in txt for c in ["영국", "UK", "미국", "일본", "독일", "유럽"]):
                        loc_text = txt
                        break
                location = loc_text or "Overseas / Korea"

                # 날짜
                deadline_str = ""
                for cell in cells:
                    txt = cell.get_text(strip=True)
                    m = re.search(r"\d{4}[.\-]\d{2}[.\-]\d{2}", txt)
                    if m:
                        deadline_str = m.group(0)

                deadline_dt = self._parse_date(deadline_str)
                seen_ids.add(job_id)

                jobs.append(Job(
                    title=title,
                    organization=org,
                    location=location,
                    category="해외취업 / K-Move",
                    deadline=deadline_str,
                    url=url,
                    job_id=f"worldjob_{job_id}",
                    description=title,
                    source_site="글로벌청년취업드림",
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
