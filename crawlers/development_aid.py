"""
crawlers/development_aid.py
developmentaid.org/jobs 크롤러

국제개발·ODA 분야 전문 채용 플랫폼.
무료 공개 공고만 수집합니다 (로그인 불필요 범위 내).
Playwright로 렌더링 후 파싱합니다.
"""

import re
import urllib.parse
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
from crawlers.base import BaseCrawler, Job


class DevelopmentAidCrawler(BaseCrawler):

    BASE_URL = "https://www.developmentaid.org"

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

            for keyword in keywords:
                self.log(f"검색 중: '{keyword}'")
                jobs = self._search(page, keyword, seen_ids)
                self.log(f"  → {len(jobs)}개 신규 공고 수집")
                all_jobs.extend(jobs)

            browser.close()

        self.log(f"크롤링 완료 — 총 {len(all_jobs)}개")
        return all_jobs

    def _search(self, page, keyword: str, seen_ids: set) -> list[Job]:
        encoded = urllib.parse.quote_plus(keyword)
        url = (
            f"{self.BASE_URL}/jobs/#!/list?keywords={encoded}"
            f"&locations=United+Kingdom&categories=&sort=date"
        )

        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            # 쿠키 배너
            for sel in ["#onetrust-accept-btn-handler", "button[class*='accept']", "button[class*='cookie']"]:
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
            "div.job-item, div[class*='job-card'], article[class*='job'], "
            "li[class*='job'], div[class*='vacancy'], div[class*='listing']"
        )

        for card in cards:
            try:
                title_el = card.select_one("h2 a, h3 a, a[class*='title'], a[class*='name']")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                href  = title_el.get("href", "")
                url   = href if href.startswith("http") else self.BASE_URL + href

                job_id = re.search(r"/(\d+)", href)
                job_id = job_id.group(1) if job_id else re.sub(r"\W+", "_", title)[:30]

                if job_id in seen_ids:
                    continue

                org_el   = card.select_one("[class*='organization'], [class*='employer'], [class*='company']")
                org      = org_el.get_text(strip=True) if org_el else "Unknown"

                loc_el   = card.select_one("[class*='location'], [class*='country']")
                location = loc_el.get_text(strip=True) if loc_el else "United Kingdom"

                deadline_str = ""
                for el in card.select("*"):
                    txt = el.get_text(strip=True)
                    if any(w in txt.lower() for w in ["deadline", "closing", "apply by", "expires"]):
                        m = re.search(r"\d{1,2}\s+\w+\s+\d{4}|\d{4}-\d{2}-\d{2}|\w+\s+\d{1,2},?\s+\d{4}", txt)
                        if m:
                            deadline_str = m.group(0)
                            break

                cat_el   = card.select_one("[class*='category'], [class*='sector'], [class*='type']")
                category = cat_el.get_text(strip=True) if cat_el else "International Development"

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
                    source_site="DevelopmentAid",
                    deadline_dt=deadline_dt,
                    keywords_matched=[keyword],
                ))
            except Exception:
                continue

        return jobs

    def _parse_date(self, s: str) -> datetime | None:
        for fmt in ["%d %B %Y", "%d %b %Y", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"]:
            try:
                return datetime.strptime(s.strip(), fmt)
            except ValueError:
                continue
        return None
