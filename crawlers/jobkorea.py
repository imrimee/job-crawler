"""
crawlers/jobkorea.py
jobkorea.co.kr 크롤러 (잡코리아)

국내 최대 민간 취업 포털.
영어+한국어 키워드 모두 지원.
Playwright 사용 (로그인 불필요 공개 검색 활용).
"""

import re
import urllib.parse
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
from crawlers.base import BaseCrawler, Job


class JobKoreaCrawler(BaseCrawler):

    BASE_URL   = "https://www.jobkorea.co.kr"
    SEARCH_URL = "https://www.jobkorea.co.kr/Search/"

    def fetch_jobs(self) -> list[Job]:
        all_keywords = self.conditions.get("keywords", [])
        kr_keywords  = self.conditions.get("keywords_kr", [])
        combined     = all_keywords + kr_keywords

        all_jobs: list[Job] = []
        seen_ids: set[str] = set()

        self.log("크롤링 시작")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ))
            page.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
            )

            for keyword in combined:
                self.log(f"검색 중: '{keyword}'")
                jobs = self._search(page, keyword, seen_ids)
                self.log(f"  → {len(jobs)}개 수집")
                all_jobs.extend(jobs)

            browser.close()

        self.log(f"크롤링 완료 — 총 {len(all_jobs)}개")
        return all_jobs

    def _search(self, page, keyword: str, seen_ids: set) -> list[Job]:
        params = urllib.parse.urlencode({"stext": keyword, "tabType": "recruit"})
        url = f"{self.SEARCH_URL}?{params}"
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)
            # 팝업 닫기
            for sel in ["button.btn-close", ".popup-close", "#popClose"]:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible():
                        btn.click()
                        page.wait_for_timeout(300)
                except Exception:
                    pass
        except PlaywrightTimeout:
            self.log(f"  ⚠ '{keyword}' 타임아웃")
            return []
        except Exception as e:
            self.log(f"  ⚠ '{keyword}' 오류: {e}")
            return []

        html = page.content()
        return self._parse_html(html, keyword, seen_ids)

    def _parse_html(self, html: str, keyword: str, seen_ids: set) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []

        cards = soup.select(
            "div.list-post, li.recruit-list-item, "
            "div[class*='list-item'], article.job"
        )

        for card in cards:
            try:
                title_el = card.select_one(
                    "a.title, a.str-title, h2 a, h3 a, .job-title a"
                )
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                href = title_el.get("href", "")
                url  = (self.BASE_URL + href) if href and not href.startswith("http") else (href or self.BASE_URL)

                job_id = re.search(r"/Recruit/(\d+)", href)
                job_id = job_id.group(1) if job_id else re.sub(r"\W+", "_", title)[:30]

                if job_id in seen_ids:
                    continue

                org_el   = card.select_one(".name, .company, .corp-name, .co_name")
                org      = org_el.get_text(strip=True) if org_el else "Unknown"

                loc_el   = card.select_one(".loc, .location, .work-place")
                location = loc_el.get_text(strip=True) if loc_el else "Korea"

                deadline_str = ""
                for el in card.select("*"):
                    txt = el.get_text(strip=True)
                    if any(w in txt for w in ["마감", "~", "까지"]):
                        m = re.search(r"\d{2,4}[./]\d{2}[./]\d{2}", txt)
                        if m:
                            deadline_str = m.group(0)
                            break

                cat_el   = card.select_one(".job-category, .sector, .duty")
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
                    job_id=f"jobkorea_{job_id}",
                    description=title,
                    source_site="잡코리아",
                    deadline_dt=deadline_dt,
                    keywords_matched=[keyword],
                ))
            except Exception:
                continue
        return jobs

    def _parse_date(self, s: str) -> datetime | None:
        for fmt in ["%y.%m.%d", "%Y.%m.%d", "%Y-%m-%d", "%y/%m/%d"]:
            try:
                return datetime.strptime(s.strip(), fmt)
            except ValueError:
                continue
        return None
