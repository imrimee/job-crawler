"""
crawlers/civil_service_jobs.py
civilservicejobs.service.gov.uk 크롤러

영국 정부 공식 채용 포털.
정적 HTML 기반 + 서버사이드 렌더링이라 requests + BeautifulSoup으로 처리합니다.
비자 제한 주의: 일부 포지션은 영국 국적/영주권 필요.
"""

import re
import urllib.request
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
from crawlers.base import BaseCrawler, Job


class CivilServiceJobsCrawler(BaseCrawler):

    BASE_URL = "https://www.civilservicejobs.service.gov.uk"
    SEARCH_URL = "https://www.civilservicejobs.service.gov.uk/csr/jobs.cgi"

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
            "jcode":     "",
            "own_orgcode": "",
            "keywords":  keyword,
            "grade1_selectpicker": "0",
            "action":    "search",
            "submit":    "Search",
        })
        url = f"{self.SEARCH_URL}?{params}"

        jobs = []
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

        cards = soup.select(
            "div.job-overview, li.search-results-job-box, "
            "div[class*='job-result'], article[class*='job']"
        )

        for card in cards:
            try:
                title_el = card.select_one(
                    "h3 a, h2 a, a.job-overview-title, "
                    "a[class*='job-title'], a[class*='title']"
                )
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                href  = title_el.get("href", "")
                url   = href if href.startswith("http") else self.BASE_URL + href

                # Civil Service Jobs ID는 URL 파라미터에 있음
                job_id_m = re.search(r"[?&](?:job_id|jobId|jcode)=(\d+)", href)
                job_id = job_id_m.group(1) if job_id_m else re.sub(r"\W+", "_", title)[:30]

                if job_id in seen_ids:
                    continue

                # 부서명
                dept_el  = card.select_one(
                    "[class*='department'], [class*='employer'], "
                    "[class*='organisation'], [class*='org']"
                )
                org = dept_el.get_text(strip=True) if dept_el else "UK Civil Service"

                # 근무지
                loc_el   = card.select_one("[class*='location'], [class*='place']")
                location = loc_el.get_text(strip=True) if loc_el else "United Kingdom"

                # 마감일
                deadline_str = ""
                for el in card.select("*"):
                    txt = el.get_text(strip=True)
                    if any(w in txt.lower() for w in ["closing date", "deadline", "apply by"]):
                        m = re.search(r"\d{1,2}\s+\w+\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}", txt)
                        if m:
                            deadline_str = m.group(0)
                            break

                # 급여/등급
                grade_el = card.select_one("[class*='grade'], [class*='salary'], [class*='pay']")
                category = grade_el.get_text(strip=True) if grade_el else "Civil Service"

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
                    source_site="Civil Service Jobs",
                    deadline_dt=deadline_dt,
                    keywords_matched=[keyword],
                ))
            except Exception:
                continue

        return jobs

    def _parse_date(self, s: str) -> datetime | None:
        for fmt in ["%d %B %Y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%Y", "%B %d, %Y"]:
            try:
                return datetime.strptime(s.strip(), fmt)
            except ValueError:
                continue
        return None
