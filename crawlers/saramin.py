"""
crawlers/saramin.py
saramin.co.kr 크롤러 (사람인)

국내 2위 종합 취업 포털.
공개 검색 API(JSON)를 일부 지원하므로 requests 우선 시도.
"""

import re
import json
import urllib.request
import urllib.parse
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
from crawlers.base import BaseCrawler, Job


class SaraminCrawler(BaseCrawler):

    BASE_URL   = "https://www.saramin.co.kr"
    SEARCH_URL = "https://www.saramin.co.kr/zf_user/search/recruit"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        "Referer": "https://www.saramin.co.kr/",
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
            jobs = self._search_requests(keyword, seen_ids)
            if not jobs:
                jobs = self._search_playwright(keyword, seen_ids)
            self.log(f"  → {len(jobs)}개 수집")
            all_jobs.extend(jobs)

        self.log(f"크롤링 완료 — 총 {len(all_jobs)}개")
        return all_jobs

    def _search_requests(self, keyword: str, seen_ids: set) -> list[Job]:
        """requests로 HTML 직접 수집 시도"""
        params = urllib.parse.urlencode({
            "searchword": keyword,
            "recruitPage": 1,
            "recruitSort": "relation",
            "recruitPageCount": 40,
        })
        url = f"{self.SEARCH_URL}?{params}"
        try:
            req = urllib.request.Request(url, headers=self.HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            return self._parse_html(html, keyword, seen_ids)
        except Exception:
            return []

    def _search_playwright(self, keyword: str, seen_ids: set) -> list[Job]:
        """requests 실패 시 Playwright fallback"""
        jobs = []
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page(user_agent=self.HEADERS["User-Agent"])
                page.add_init_script(
                    "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
                )
                params = urllib.parse.urlencode({
                    "searchword": keyword,
                    "recruitPage": 1,
                })
                page.goto(
                    f"{self.SEARCH_URL}?{params}",
                    wait_until="domcontentloaded",
                    timeout=30000
                )
                page.wait_for_timeout(2500)
                html = page.content()
                browser.close()
                jobs = self._parse_html(html, keyword, seen_ids)
        except Exception as e:
            self.log(f"  ⚠ Playwright fallback 실패: {e}")
        return jobs

    def _parse_html(self, html: str, keyword: str, seen_ids: set) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []

        cards = soup.select(
            "div.item_recruit, li.item_, "
            "div[class*='recruit-item'], article.job"
        )

        for card in cards:
            try:
                title_el = card.select_one(
                    "a.str_tit, h2.job_tit a, h3 a, a.tit"
                )
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                href = title_el.get("href", "")
                url  = (self.BASE_URL + href) if href and not href.startswith("http") else (href or self.BASE_URL)

                job_id = re.search(r"rec_idx=(\d+)|/(\d+)", href)
                job_id = (job_id.group(1) or job_id.group(2)) if job_id else re.sub(r"\W+", "_", title)[:30]

                if job_id in seen_ids:
                    continue

                org_el   = card.select_one(".corp_name a, .company a, h3.corp_name")
                org      = org_el.get_text(strip=True) if org_el else "Unknown"

                loc_el   = card.select_one(".work_place, .loc")
                location = loc_el.get_text(strip=True) if loc_el else "Korea"

                # 마감일
                deadline_str = ""
                for el in card.select("*"):
                    txt = el.get_text(strip=True)
                    m = re.search(r"(\d{2}/\d{2})\(", txt)
                    if m:
                        year = str(datetime.now().year)
                        deadline_str = f"{year}/{m.group(1)}"
                        break
                    m2 = re.search(r"\d{4}[.\-]\d{2}[.\-]\d{2}", txt)
                    if m2:
                        deadline_str = m2.group(0)
                        break

                cat_el   = card.select_one(".job_sector, .duty, .sector")
                category = cat_el.get_text(strip=True) if cat_el else "일반"

                deadline_dt = self._parse_date(deadline_str)
                seen_ids.add(job_id)

                jobs.append(Job(
                    title=title,
                    organization=org,
                    location=location,
                    category=category,
                    deadline=deadline_str,
                    url=url,
                    job_id=f"saramin_{job_id}",
                    description=title,
                    source_site="사람인",
                    deadline_dt=deadline_dt,
                    keywords_matched=[keyword],
                ))
            except Exception:
                continue
        return jobs

    def _parse_date(self, s: str) -> datetime | None:
        for fmt in ["%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%d"]:
            try:
                return datetime.strptime(s.strip(), fmt)
            except ValueError:
                continue
        return None
