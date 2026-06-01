"""
crawlers/un_careers.py
careers.un.org 크롤러

UN Careers는 React SPA이므로 Playwright로 브라우저를 구동하여
실제 렌더링된 결과를 수집합니다.
각 검색 키워드마다 검색을 수행하고 결과를 병합합니다.
"""

import re
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from crawlers.base import BaseCrawler, Job


class UnCareersCrawler(BaseCrawler):

    BASE_URL = "https://careers.un.org"
    SEARCH_URL = "https://careers.un.org/home?language=en"

    def fetch_jobs(self) -> list[Job]:
        keywords = self.conditions.get("keywords", [])
        all_jobs: list[Job] = []
        seen_ids: set[str] = set()

        self.log(f"크롤링 시작 — 검색 키워드 {len(keywords)}개")

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

            for keyword in keywords:
                self.log(f"검색 중: '{keyword}'")
                jobs = self._search_keyword(page, keyword, seen_ids)
                self.log(f"  → {len(jobs)}개 신규 공고 수집")
                all_jobs.extend(jobs)

            browser.close()

        self.log(f"크롤링 완료 — 총 {len(all_jobs)}개 공고 수집")
        return all_jobs

    def _search_keyword(self, page, keyword: str, seen_ids: set) -> list[Job]:
        jobs = []

        try:
            # 홈페이지로 이동 후 검색
            page.goto(self.SEARCH_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            # 검색창 입력
            search_input = page.locator("input[placeholder*='keyword'], input[placeholder*='search'], input[type='search']").first
            search_input.click()
            search_input.fill("")
            search_input.type(keyword, delay=50)
            page.keyboard.press("Enter")

            # 결과 로딩 대기
            page.wait_for_timeout(4000)
            page.wait_for_load_state("networkidle", timeout=15000)

        except PlaywrightTimeout:
            self.log(f"  ⚠ '{keyword}' 검색 타임아웃, 건너뜀")
            return []
        except Exception as e:
            self.log(f"  ⚠ '{keyword}' 검색 오류: {e}")
            return []

        # 페이지 순회 (최대 5페이지)
        for page_num in range(1, 6):
            page_jobs = self._parse_current_page(page, keyword, seen_ids)
            jobs.extend(page_jobs)

            # 다음 페이지 버튼 확인
            if not self._go_next_page(page):
                break

        return jobs

    def _parse_current_page(self, page, keyword: str, seen_ids: set) -> list[Job]:
        jobs = []
        try:
            # 공고 카드 수집 (UN Careers의 실제 DOM 구조에 맞춤)
            job_elements = page.locator(".job-opening, [class*='job-item'], [class*='jobOpening']").all()

            if not job_elements:
                # 대안: 텍스트 기반으로 공고 블록 찾기
                content = page.inner_text("main, #main-content, .content") or ""
                jobs = self._parse_text_content(content, keyword, seen_ids)
                return jobs

            for el in job_elements:
                try:
                    job = self._parse_job_element(el, keyword)
                    if job and job.job_id not in seen_ids:
                        seen_ids.add(job.job_id)
                        jobs.append(job)
                except Exception:
                    continue

        except Exception as e:
            self.log(f"  ⚠ 페이지 파싱 오류: {e}")

        return jobs

    def _parse_job_element(self, el, keyword: str) -> Job | None:
        """DOM 엘리먼트에서 Job 객체 추출"""
        try:
            text = el.inner_text()
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            if not lines:
                return None

            title = lines[0] if lines else "Unknown"

            # Job ID 추출
            job_id = ""
            for line in lines:
                m = re.search(r"Job ID\s*[:\s]\s*(\d+)", line, re.IGNORECASE)
                if m:
                    job_id = m.group(1)
                    break
            if not job_id:
                job_id = re.sub(r"\W+", "_", title)[:30]

            # 각 필드 추출
            dept = self._extract_field(lines, ["Department", "Department/Office"])
            location = self._extract_field(lines, ["Duty Station", "Location"])
            category = self._extract_field(lines, ["Category", "Category and Level"])
            deadline_str = self._extract_field(lines, ["Deadline", "Closing Date"])
            date_posted = self._extract_field(lines, ["Date Posted"])

            # URL 추출
            try:
                link = el.locator("a").first
                href = link.get_attribute("href") or ""
                url = href if href.startswith("http") else self.BASE_URL + href
            except Exception:
                url = f"{self.BASE_URL}/jobSearchDescription/{job_id}?language=EN"

            # deadline datetime 파싱
            deadline_dt = self._parse_date(deadline_str)

            return Job(
                title=title,
                organization=dept or "United Nations",
                location=location or "Unknown",
                category=category or "",
                deadline=deadline_str or "",
                url=url,
                job_id=job_id,
                date_posted=date_posted or "",
                source_site="UN Careers",
                deadline_dt=deadline_dt,
                keywords_matched=[keyword],
            )
        except Exception:
            return None

    def _parse_text_content(self, text: str, keyword: str, seen_ids: set) -> list[Job]:
        """
        DOM 파싱 실패 시 페이지 텍스트를 직접 파싱하는 폴백 방법.
        UN Careers 텍스트 구조 기반으로 공고 블록을 분리합니다.
        """
        jobs = []
        # 공고 블록은 "Job ID : XXXXXX" 패턴으로 구분
        blocks = re.split(r"(?=Job ID\s*:\s*\d+)", text)

        for block in blocks:
            if "Job ID" not in block:
                continue
            try:
                lines = [l.strip() for l in block.split("\n") if l.strip()]

                title = lines[0] if lines else ""
                job_id_m = re.search(r"Job ID\s*:\s*(\d+)", block)
                job_id = job_id_m.group(1) if job_id_m else re.sub(r"\W+", "_", title)[:30]

                if job_id in seen_ids:
                    continue

                dept = self._extract_field(lines, ["Department/Office"])
                location = self._extract_field(lines, ["Duty Station"])
                category = self._extract_field(lines, ["Category and Level"])
                deadline_str = self._extract_field(lines, ["Deadline"])
                date_posted = self._extract_field(lines, ["Date Posted"])
                deadline_dt = self._parse_date(deadline_str)

                url = f"{self.BASE_URL}/jobSearchDescription/{job_id}?language=EN"

                seen_ids.add(job_id)
                jobs.append(Job(
                    title=title,
                    organization=dept or "United Nations",
                    location=location or "",
                    category=category or "",
                    deadline=deadline_str or "",
                    url=url,
                    job_id=job_id,
                    date_posted=date_posted or "",
                    source_site="UN Careers",
                    deadline_dt=deadline_dt,
                    keywords_matched=[keyword],
                ))
            except Exception:
                continue

        return jobs

    def _extract_field(self, lines: list[str], keys: list[str]) -> str:
        """'Key : Value' 형식에서 값을 추출"""
        for line in lines:
            for key in keys:
                if line.startswith(key):
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        return parts[1].strip()
        return ""

    def _parse_date(self, date_str: str) -> datetime | None:
        """다양한 날짜 형식을 datetime으로 파싱"""
        if not date_str:
            return None
        formats = ["%b %d, %Y", "%B %d, %Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None

    def _go_next_page(self, page) -> bool:
        """다음 페이지로 이동. 다음 페이지가 없으면 False 반환"""
        try:
            next_btn = page.locator("a[aria-label='Next page'], button:has-text('Next'), a:has-text('›'), a:has-text('»')").first
            if next_btn.is_visible() and next_btn.is_enabled():
                next_btn.click()
                page.wait_for_timeout(3000)
                page.wait_for_load_state("networkidle", timeout=10000)
                return True
        except Exception:
            pass
        return False
