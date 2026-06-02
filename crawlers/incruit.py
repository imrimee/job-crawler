"""
crawlers/incruit.py
incruit.com 크롤러 (인크루트)

외국계 기업·공공기관 인턴 특화 포털.
requests + BeautifulSoup.
"""

import re
import urllib.request
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
from crawlers.base import BaseCrawler, Job


class IncruitCrawler(BaseCrawler):

    BASE_URL   = "https://www.incruit.com"
    SEARCH_URL = "https://search.incruit.com/list/search.asp"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        "Referer": "https://www.incruit.com/",
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
            jobs = self._search(keyword, seen_ids)
            self.log(f"  → {len(jobs)}개 수집")
            all_jobs.extend(jobs)

        self.log(f"크롤링 완료 — 총 {len(all_jobs)}개")
        return all_jobs

    def _search(self, keyword: str, seen_ids: set) -> list[Job]:
        params = urllib.parse.urlencode({
            "col": "job",
            "q":   keyword,
            "careerType": 0,   # 0 = 전체 (신입+경력)
        })
        url = f"{self.SEARCH_URL}?{params}"
        try:
            req = urllib.request.Request(url, headers=self.HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            self.log(f"  ⚠ 검색 실패: {e}")
            return []
        return self._parse_html(html, keyword, seen_ids)

    def _parse_html(self, html: str, keyword: str, seen_ids: set) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []

        cards = soup.select(
            "li.cell_item, div.list_item, "
            "div[class*='recruit'], li[class*='job']"
        )

        for card in cards:
            try:
                title_el = card.select_one("a.title, a.tit, h2 a, h3 a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                href = title_el.get("href", "")
                url  = href if href.startswith("http") else (self.BASE_URL + href)

                job_id = re.search(r"jobno=(\d+)|/(\d+)", href)
                job_id = (job_id.group(1) or job_id.group(2)) if job_id else re.sub(r"\W+", "_", title)[:30]

                if job_id in seen_ids:
                    continue

                org_el   = card.select_one(".company, .corp, .name")
                org      = org_el.get_text(strip=True) if org_el else "Unknown"

                loc_el   = card.select_one(".loc, .location, .place")
                location = loc_el.get_text(strip=True) if loc_el else "Korea"

                deadline_str = ""
                for el in card.select("*"):
                    txt = el.get_text(strip=True)
                    m = re.search(r"\d{4}[.\-]\d{2}[.\-]\d{2}|\d{2}[./]\d{2}[./]\d{2}", txt)
                    if m:
                        deadline_str = m.group(0)
                        break

                cat_el   = card.select_one(".tag, .category, .duty")
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
                    job_id=f"incruit_{job_id}",
                    description=title,
                    source_site="인크루트",
                    deadline_dt=deadline_dt,
                    keywords_matched=[keyword],
                ))
            except Exception:
                continue
        return jobs

    def _parse_date(self, s: str) -> datetime | None:
        for fmt in ["%Y.%m.%d", "%Y-%m-%d", "%y.%m.%d", "%y/%m/%d"]:
            try:
                return datetime.strptime(s.strip(), fmt)
            except ValueError:
                continue
        return None
