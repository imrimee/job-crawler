"""
crawlers/idealist.py
idealist.org 크롤러

NGO·비영리 인턴십 특화 플랫폼.
React SPA이므로 Playwright 사용. 검색 API endpoint를 직접 호출합니다.
"""

import re
import json
import urllib.request
import urllib.parse
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from crawlers.base import BaseCrawler, Job


class IdealistCrawler(BaseCrawler):

    BASE_URL = "https://www.idealist.org"

    def fetch_jobs(self) -> list[Job]:
        keywords = self.conditions.get("keywords", [])
        all_jobs: list[Job] = []
        seen_ids: set[str] = set()

        self.log("크롤링 시작")

        # 먼저 API 방식 시도, 실패 시 Playwright fallback
        api_success = self._try_api(keywords, all_jobs, seen_ids)
        if not api_success:
            self.log("  API 실패 → Playwright 방식으로 전환")
            self._try_playwright(keywords, all_jobs, seen_ids)

        self.log(f"크롤링 완료 — 총 {len(all_jobs)}개")
        return all_jobs

    def _try_api(self, keywords: list, all_jobs: list, seen_ids: set) -> bool:
        """Idealist 내부 검색 API 시도"""
        for keyword in keywords:
            self.log(f"검색 중 (API): '{keyword}'")
            try:
                params = urllib.parse.urlencode({
                    "q": keyword,
                    "type": "INTERNSHIP,JOB",
                    "country": "GB",
                    "page": 1,
                    "pageSize": 50,
                })
                url = f"https://www.idealist.org/api/v3/search?{params}"
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json",
                    "Referer": "https://www.idealist.org/",
                })
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read())

                for item in data.get("results", data.get("items", [])):
                    job = self._parse_api_item(item, keyword, seen_ids)
                    if job:
                        all_jobs.append(job)

            except Exception as e:
                self.log(f"  ⚠ API 오류: {e}")
                return False

        return True

    def _parse_api_item(self, item: dict, keyword: str, seen_ids: set) -> Job | None:
        try:
            job_id   = str(item.get("id", ""))
            if not job_id or job_id in seen_ids:
                return None

            title    = item.get("title", item.get("name", ""))
            org      = item.get("org", {}).get("name", item.get("orgName", "Unknown"))
            location = item.get("city", "") + ", " + item.get("country", "UK")
            location = location.strip(", ")
            category = item.get("type", "")
            deadline_str = item.get("applicationDeadline", item.get("deadline", ""))
            if deadline_str:
                deadline_str = deadline_str[:10]
            date_posted  = item.get("publishedAt", item.get("createdAt", ""))
            if date_posted:
                date_posted = date_posted[:10]
            slug = item.get("slug", item.get("url", ""))
            url  = f"{self.BASE_URL}/en/jobs/{slug}" if slug and not slug.startswith("http") else slug or self.BASE_URL

            deadline_dt = self._parse_date(deadline_str)
            seen_ids.add(job_id)

            return Job(
                title=title,
                organization=org,
                location=location,
                category=category,
                deadline=deadline_str,
                url=url,
                job_id=job_id,
                date_posted=date_posted,
                source_site="Idealist",
                deadline_dt=deadline_dt,
                keywords_matched=[keyword],
            )
        except Exception:
            return None

    def _try_playwright(self, keywords: list, all_jobs: list, seen_ids: set):
        """Playwright를 사용한 브라우저 렌더링 방식"""
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ))

            for keyword in keywords:
                self.log(f"검색 중 (Playwright): '{keyword}'")
                try:
                    params = urllib.parse.urlencode({
                        "q": keyword,
                        "type": "internships,jobs",
                        "country": "United Kingdom",
                    })
                    page.goto(
                        f"{self.BASE_URL}/en/search?{params}",
                        wait_until="networkidle",
                        timeout=30000
                    )
                    page.wait_for_timeout(3000)

                    # 쿠키 배너 닫기
                    for sel in ["button[data-test*='accept']", "button[id*='accept']", "#onetrust-accept-btn-handler"]:
                        try:
                            btn = page.locator(sel).first
                            if btn.is_visible():
                                btn.click()
                                page.wait_for_timeout(500)
                        except Exception:
                            pass

                    # 페이지 텍스트 파싱
                    text = page.inner_text("main") or page.inner_text("body")
                    jobs = self._parse_text(text, keyword, seen_ids)
                    all_jobs.extend(jobs)
                    self.log(f"  → {len(jobs)}개 수집")

                except PlaywrightTimeout:
                    self.log(f"  ⚠ '{keyword}' 타임아웃")
                except Exception as e:
                    self.log(f"  ⚠ '{keyword}' 오류: {e}")

            browser.close()

    def _parse_text(self, text: str, keyword: str, seen_ids: set) -> list[Job]:
        """텍스트 기반 파싱 (Playwright fallback용)"""
        jobs = []
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        # 간단한 휴리스틱: "Internship" 또는 "Job" 이 포함된 라인 주변을 공고로 간주
        for i, line in enumerate(lines):
            if any(k in line.lower() for k in ["internship", "coordinator", "officer", "analyst", "researcher"]):
                job_id = f"idealist_{abs(hash(line))}"
                if job_id in seen_ids:
                    continue
                context = " ".join(lines[max(0, i-1):i+3])
                seen_ids.add(job_id)
                jobs.append(Job(
                    title=line[:120],
                    organization="Unknown",
                    location="United Kingdom",
                    category="",
                    deadline="",
                    url=self.BASE_URL,
                    job_id=job_id,
                    source_site="Idealist",
                    deadline_dt=None,
                    keywords_matched=[keyword],
                ))
        return jobs[:20]  # 텍스트 파싱은 최대 20개로 제한

    def _parse_date(self, s: str) -> datetime | None:
        for fmt in ["%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d, %Y"]:
            try:
                return datetime.strptime(s.strip(), fmt)
            except ValueError:
                continue
        return None
