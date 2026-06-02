"""
crawlers/alio.py
alio.go.kr 크롤러 (알리오 공공기관 채용정보)

기획재정부 운영 공공기관 통합 채용 포털.
KOICA·KF·KIEP 등 외교·국제 관련 공공기관 공고 수집.
Playwright 사용 (동적 렌더링).
"""

import re
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
from crawlers.base import BaseCrawler, Job


class AlioCrawler(BaseCrawler):

    BASE_URL = "https://www.alio.go.kr"
    # 외교부·기재부 산하 공공기관 채용 목록 URL
    JOBS_URL = "https://www.alio.go.kr/recruitmentList.do"

    def fetch_jobs(self) -> list[Job]:
        all_keywords = self.conditions.get("keywords", [])
        kr_keywords  = self.conditions.get("keywords_kr", [])
        combined     = all_keywords + kr_keywords

        self.log("크롤링 시작")
        self._job_pool: list[Job] = []
        seen_ids: set[str] = set()

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ))
            try:
                page.goto(self.JOBS_URL, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)
                html = page.content()
                self._job_pool = self._parse_html(html, seen_ids)
            except PlaywrightTimeout:
                self.log("  ⚠ 페이지 로드 타임아웃")
            except Exception as e:
                self.log(f"  ⚠ 오류: {e}")
            finally:
                browser.close()

        self.log(f"  전체 수집: {len(self._job_pool)}개")

        # 키워드 필터링
        result = []
        for job in self._job_pool:
            searchable = (job.title + " " + job.description + " " + job.organization).lower()
            matched = [kw for kw in combined if kw.lower() in searchable]
            if matched or not combined:
                job.keywords_matched = matched
                result.append(job)

        self.log(f"크롤링 완료 — {len(result)}개")
        return result

    def _parse_html(self, html: str, seen_ids: set) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []

        rows = soup.select("table tbody tr, .recruit-list li, .list-item")
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

                job_id = re.search(r"[?&](?:seq|id|no|rcritSeq)=(\w+)", href)
                job_id = job_id.group(1) if job_id else re.sub(r"\W+", "_", title)[:30]

                if job_id in seen_ids:
                    continue

                # 기관명
                org_el = row.select_one(".org, .institution, td:nth-of-type(2)")
                org    = org_el.get_text(strip=True) if org_el else "공공기관"

                # 날짜
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
                    location="Korea",
                    category="공공기관",
                    deadline=deadline_str,
                    url=url,
                    job_id=f"alio_{job_id}",
                    description=f"{title} - {org}",
                    source_site="알리오(ALIO)",
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
