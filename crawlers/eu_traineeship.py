"""
crawlers/eu_traineeship.py
traineeships.ec.europa.eu 크롤러

EU 집행위원회 공식 인턴십(Blue Book Traineeship).
5개월 유급(~€1,300/월), 연 2회 모집.
"""

import re
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from crawlers.base import BaseCrawler, Job


class EuTraineeshipCrawler(BaseCrawler):

    BASE_URL = "https://traineeships.ec.europa.eu"

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
                page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(4000)

                content = page.inner_text("main, body") or ""
                jobs = self._parse_content(content, keywords, seen_ids)
                all_jobs.extend(jobs)
                self.log(f"  → {len(jobs)}개 공고 수집")

                # 상세 공고 링크 탐색
                links = page.locator("a[href*='traineeship'], a[href*='stage'], a[href*='internship']").all()
                for link in links[:10]:
                    try:
                        href = link.get_attribute("href") or ""
                        if not href:
                            continue
                        url  = href if href.startswith("http") else self.BASE_URL + href
                        page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        page.wait_for_timeout(2000)
                        detail = page.inner_text("main, body") or ""
                        detail_jobs = self._parse_content(detail, keywords, seen_ids, url=url)
                        all_jobs.extend(detail_jobs)
                    except Exception:
                        continue

            except PlaywrightTimeout:
                self.log("⚠ 타임아웃 — 수집 부분 완료")
            except Exception as e:
                self.log(f"⚠ 오류: {e}")
            finally:
                browser.close()

        self.log(f"크롤링 완료 — 총 {len(all_jobs)}개")
        return all_jobs

    def _parse_content(self, text: str, keywords: list[str], seen_ids: set, url: str = "") -> list[Job]:
        jobs = []
        if not url:
            url = self.BASE_URL

        lines = [l.strip() for l in text.split("\n") if l.strip()]

        # 'traineeship' 또는 'stage' 또는 키워드가 포함된 라인을 공고 제목으로 추출
        for i, line in enumerate(lines):
            if len(line) < 10 or len(line) > 250:
                continue

            matched_kws = [kw for kw in keywords if kw.lower() in line.lower()]
            is_traineeship = any(
                w in line.lower()
                for w in ["traineeship", "stage", "intern", "trainee", "bluebook", "blue book"]
            )

            if not matched_kws and not is_traineeship:
                continue

            job_id = re.sub(r"\W+", "_", line)[:40]
            if job_id in seen_ids:
                continue

            context = lines[max(0, i-2):i+5]
            deadline_str = ""
            for cl in context:
                if re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}\s+\w+\s+\d{4}", cl):
                    deadline_str = cl
                    break

            seen_ids.add(job_id)
            jobs.append(Job(
                title=line,
                organization="European Commission",
                location="Brussels, Belgium / Luxembourg",
                category="Internship / Traineeship",
                deadline=deadline_str,
                url=url,
                job_id=job_id,
                source_site="EU Traineeship (Blue Book)",
                deadline_dt=self._parse_date(deadline_str),
                keywords_matched=matched_kws or ["traineeship"],
            ))

        return jobs

    def _parse_date(self, s: str) -> datetime | None:
        for fmt in ["%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d, %Y"]:
            try:
                return datetime.strptime(s.strip(), fmt)
            except ValueError:
                continue
        return None
