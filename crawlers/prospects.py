"""
crawlers/prospects.py
prospects.ac.uk 크롤러

영국 대졸자 1위 취업 포털.
검색 결과가 JS로 렌더링되므로 Playwright를 사용합니다.
"""

import re
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
from crawlers.base import BaseCrawler, Job


class ProspectsCrawler(BaseCrawler):

    BASE_URL = "https://www.prospects.ac.uk"

    def fetch_jobs(self) -> list[Job]:
        keywords = self.conditions.get("keywords", [])
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
            # 쿠키/팝업 자동 처리
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            for keyword in keywords:
                self.log(f"검색 중: '{keyword}'")
                jobs = self._search(page, keyword, seen_ids)
                self.log(f"  → {len(jobs)}개 신규 공고 수집")
                all_jobs.extend(jobs)

            browser.close()

        self.log(f"크롤링 완료 — 총 {len(all_jobs)}개")
        return all_jobs

    def _search(self, page, keyword: str, seen_ids: set) -> list[Job]:
        encoded = keyword.replace(" ", "+")
        url = (
            f"{self.BASE_URL}/jobs-and-work-experience/job-sectors/job-search"
            f"#?searchTerm={encoded}&locationTerm=United+Kingdom"
        )

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3500)
            # 팝업/쿠키 배너 닫기 시도
            for sel in ["button[id*='accept']", "button[class*='cookie']", "#onetrust-accept-btn-handler"]:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible():
                        btn.click()
                        page.wait_for_timeout(500)
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
            "div[class*='job-listing'], li[class*='job'], "
            "article[class*='job'], div[class*='vacancy']"
        )

        for card in cards:
            try:
                title_el = card.select_one("h2 a, h3 a, a[class*='title']")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                href  = title_el.get("href", "")
                url   = href if href.startswith("http") else self.BASE_URL + href

                job_id = re.search(r"/(\d+)", href)
                job_id = job_id.group(1) if job_id else re.sub(r"\W+", "_", title)[:30]

                if job_id in seen_ids:
                    continue

                org_el   = card.select_one("[class*='employer'], [class*='company']")
                org      = org_el.get_text(strip=True) if org_el else "Unknown"

                loc_el   = card.select_one("[class*='location']")
                location = loc_el.get_text(strip=True) if loc_el else "United Kingdom"

                deadline_str = ""
                for el in card.select("*"):
                    txt = el.get_text(strip=True)
                    if any(w in txt.lower() for w in ["closing", "deadline", "apply by", "expires"]):
                        m = re.search(r"\d{1,2}\s+\w+\s+\d{4}|\d{4}-\d{2}-\d{2}", txt)
                        if m:
                            deadline_str = m.group(0)
                            break

                cat_el   = card.select_one("[class*='type'], [class*='sector'], [class*='category']")
                category = cat_el.get_text(strip=True) if cat_el else ""

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
                    source_site="Prospects.ac.uk",
                    deadline_dt=deadline_dt,
                    keywords_matched=[keyword],
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
