"""
crawlers/epso.py
eu-careers.europa.eu 크롤러 (EPSO)

EU 공식 인사선발처 채용 포털.
AD급 공무원, CAST 계약직, Blue Book 스테이지 포함.
"""

import re
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from crawlers.base import BaseCrawler, Job


class EpsoCrawler(BaseCrawler):

    BASE_URL = "https://eu-careers.europa.eu"
    SEARCH_URL = "https://eu-careers.europa.eu/en/search"

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

                base_jobs = self._collect_all_jobs(page, seen_ids)
                all_jobs.extend(base_jobs)
                self.log(f"  → 전체 공고 {len(base_jobs)}개 수집")

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

    def _collect_all_jobs(self, page, seen_ids: set) -> list[Job]:
        try:
            page.wait_for_selector(
                "[class*='job'], [class*='vacancy'], [class*='result'], article",
                timeout=10000,
            )
        except Exception:
            pass

        return self._parse_page(page, "general", seen_ids)

    def _search_keyword(self, page, keyword: str, seen_ids: set) -> list[Job]:
        try:
            search_el = page.locator(
                "input[type='search'], input[placeholder*='search'], input[placeholder*='keyword']"
            ).first
            if search_el.is_visible():
                search_el.fill(keyword)
                page.keyboard.press("Enter")
                page.wait_for_timeout(3000)
        except Exception:
            pass
        return self._parse_page(page, keyword, seen_ids)

    def _parse_page(self, page, keyword: str, seen_ids: set) -> list[Job]:
        jobs = []
        try:
            cards = page.locator(
                "[class*='job-item'], [class*='vacancy'], [class*='result-item'], "
                "article, li[class*='job'], div[class*='opening']"
            ).all()

            for card in cards:
                try:
                    job = self._parse_card(card, keyword)
                    if job and job.job_id not in seen_ids:
                        seen_ids.add(job.job_id)
                        jobs.append(job)
                except Exception:
                    continue

            if not jobs:
                text = page.inner_text("main, body") or ""
                jobs = self._parse_text(text, keyword, seen_ids)

        except Exception as e:
            self.log(f"  ⚠ 파싱 오류: {e}")

        return jobs

    def _parse_card(self, card, keyword: str) -> Job | None:
        text = card.inner_text()
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines:
            return None

        title = lines[0]
        job_id = re.sub(r"\W+", "_", title)[:40]

        try:
            link = card.locator("a").first
            href = link.get_attribute("href") or ""
            url  = href if href.startswith("http") else self.BASE_URL + href
        except Exception:
            url = self.SEARCH_URL

        location = "Brussels, Belgium"
        deadline_str = ""
        category = "EU Institution"

        for line in lines[1:]:
            if re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}\s+\w+\s+\d{4}", line):
                deadline_str = line
            if any(w in line.lower() for w in ["ad", "ast", "cast", "intern", "stage", "contract"]):
                category = line

        return Job(
            title=title,
            organization="EU Institutions (EPSO)",
            location=location,
            category=category,
            deadline=deadline_str,
            url=url,
            job_id=job_id,
            source_site="EPSO (EU Careers)",
            deadline_dt=self._parse_date(deadline_str),
            keywords_matched=[keyword],
        )

    def _parse_text(self, text: str, keyword: str, seen_ids: set) -> list[Job]:
        jobs = []
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines:
            if keyword.lower() not in line.lower():
                continue
            if len(line) < 10 or len(line) > 200:
                continue
            job_id = re.sub(r"\W+", "_", line)[:40]
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)
            jobs.append(Job(
                title=line,
                organization="EU Institutions (EPSO)",
                location="Brussels, Belgium",
                category="EU Institution",
                deadline="",
                url=self.SEARCH_URL,
                job_id=job_id,
                source_site="EPSO (EU Careers)",
                deadline_dt=None,
                keywords_matched=[keyword],
            ))
        return jobs

    def _parse_date(self, s: str) -> datetime | None:
        for fmt in ["%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d, %Y"]:
            try:
                return datetime.strptime(s.strip(), fmt)
            except ValueError:
                continue
        return None
