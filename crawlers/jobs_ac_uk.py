"""
crawlers/jobs_ac_uk.py
jobs.ac.uk 크롤러

영국 학술·연구기관 채용 1위 사이트.
정적 HTML 렌더링 방식이나 검색 결과는 JS로 일부 로딩됩니다.
Playwright로 렌더링 후 BeautifulSoup으로 파싱합니다.
"""

import re
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
from crawlers.base import BaseCrawler, Job


class JobsAcUkCrawler(BaseCrawler):

    BASE_URL = "https://www.jobs.ac.uk"

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
        # jobs.ac.uk 검색 URL: keywords + location UK
        encoded = keyword.replace(" ", "+")
        url = (
            f"{self.BASE_URL}/jobs/search/?keywords={encoded}"
            f"&location=United+Kingdom&radius=0"
            f"&job_type=&employer_type=&salary_min=&order=1"
        )

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)
        except PlaywrightTimeout:
            self.log(f"  ⚠ '{keyword}' 페이지 로드 타임아웃")
            return []
        except Exception as e:
            self.log(f"  ⚠ '{keyword}' 오류: {e}")
            return []

        jobs = []
        for _ in range(3):  # 최대 3페이지
            html = page.content()
            page_jobs = self._parse_html(html, keyword, seen_ids)
            jobs.extend(page_jobs)

            # 다음 페이지
            try:
                nxt = page.locator("a[aria-label='Next page'], a.next-page, li.next > a").first
                if nxt.is_visible():
                    nxt.click()
                    page.wait_for_timeout(2500)
                else:
                    break
            except Exception:
                break

        return jobs

    def _parse_html(self, html: str, keyword: str, seen_ids: set) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []

        # jobs.ac.uk의 공고 카드 선택자
        cards = soup.select("div.j-search-result__listing, article.job, div[class*='result']")

        for card in cards:
            try:
                # 제목
                title_el = card.select_one("h2 a, h3 a, a.j-search-result__title")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)

                # URL & ID
                href = title_el.get("href", "")
                url  = href if href.startswith("http") else self.BASE_URL + href
                job_id = re.search(r"/job/(\d+)", href)
                job_id = job_id.group(1) if job_id else re.sub(r"\W+", "_", title)[:30]

                if job_id in seen_ids:
                    continue

                # 기관명
                org_el = card.select_one(".j-search-result__employer, .employer, [class*='employer']")
                org = org_el.get_text(strip=True) if org_el else "Unknown"

                # 근무지
                loc_el = card.select_one(".j-search-result__location, .location, [class*='location']")
                location = loc_el.get_text(strip=True) if loc_el else "United Kingdom"

                # 마감일
                deadline_str = ""
                for el in card.select("li, span, div"):
                    txt = el.get_text(strip=True)
                    if "closing" in txt.lower() or "deadline" in txt.lower() or "expires" in txt.lower():
                        m = re.search(r"\d{1,2}\s+\w+\s+\d{4}|\d{4}-\d{2}-\d{2}", txt)
                        if m:
                            deadline_str = m.group(0)
                            break

                # 카테고리
                cat_el = card.select_one(".j-search-result__job-type, [class*='job-type'], [class*='category']")
                category = cat_el.get_text(strip=True) if cat_el else ""

                # 게시일
                date_el = card.select_one("[class*='posted'], [class*='date']")
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
                    source_site="Jobs.ac.uk",
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
