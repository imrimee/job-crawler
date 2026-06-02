"""
crawlers/oecd_careers.py
oecd.org/careers 크롤러

OECD(경제협력개발기구) 공식 채용 포털.
파리 본부 기반. 한국 회원국으로 한국인 지원 가능.
"""

import re
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from crawlers.base import BaseCrawler, Job


class OecdCareersCrawler(BaseCrawler):

    SEARCH_URL = "https://www.oecd.org/en/about/jobs.html"

    def fetch_jobs(self) -> list[Job]:
        keywords = self.conditions.get("keywords", [])
        all_jobs: list[Job] = []
        seen_ids: set[str] = set()

        self.log("크롤링 시작 (Playwright)")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()

            try:
                page.goto(self.SEARCH_URL, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)

                content = page.inner_text("main, body") or ""
                jobs = self._parse_text(content, keywords, seen_ids)
                all_jobs.extend(jobs)

                for keyword in keywords:
                    self.log(f"검색 중: '{keyword}'")
                    kw_jobs = self._search_keyword(page, keyword, seen_ids)
                    self.log(f"  → {len(kw_jobs)}개 신규 공고 수집")
                    all_jobs.extend(kw_jobs)

            except PlaywrightTimeout:
                self.log("⚠ 타임아웃 — 수집 부분 완료")
            except Exception as e:
                self.log(f"⚠ 오류: {e}")
            finally:
                browser.close()

        self.log(f"크롤링 완료 — 총 {len(all_jobs)}개")
        return all_jobs

    def _search_keyword(self, page, keyword: str, seen_ids: set) -> list[Job]:
        try:
            search_input = page.locator(
                "input[type='search'], input[placeholder*='search'], input[placeholder*='Search']"
            ).first
            if search_input.is_visible():
                search_input.fill(keyword)
                page.keyboard.press("Enter")
                page.wait_for_timeout(3000)

            content = page.inner_text("main, body") or ""
            return self._parse_text(content, [keyword], seen_ids)
        except Exception:
            return []

    def _parse_text(self, text: str, keywords: list[str], seen_ids: set) -> list[Job]:
        jobs = []
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        for i, line in enumerate(lines):
            if not any(kw.lower() in line.lower() for kw in keywords):
                continue
            if len(line) < 10 or len(line) > 200:
                continue

            job_id = re.sub(r"\W+", "_", line)[:40]
            if job_id in seen_ids:
                continue

            context_lines = lines[max(0, i-2):i+5]
            location = "Paris, France"
            deadline_str = ""
            for cl in context_lines:
                if re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}\s+\w+\s+\d{4}", cl):
                    deadline_str = cl
                    break
                if any(city in cl for city in ["Paris", "Berlin", "Brussels", "Geneva"]):
                    location = cl

            deadline_dt = self._parse_date(deadline_str)
            seen_ids.add(job_id)
            jobs.append(Job(
                title=line,
                organization="OECD",
                location=location,
                category="Policy",
                deadline=deadline_str,
                url="https://www.oecd.org/en/about/jobs.html",
                job_id=job_id,
                source_site="OECD Careers",
                deadline_dt=deadline_dt,
                keywords_matched=[kw for kw in keywords if kw.lower() in line.lower()],
            ))

        return jobs

    def _parse_date(self, s: str) -> datetime | None:
        for fmt in ["%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d, %Y"]:
            try:
                return datetime.strptime(s.strip(), fmt)
            except ValueError:
                continue
        return None
