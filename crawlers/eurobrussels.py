"""
crawlers/eurobrussels.py
eurobrussels.com 크롤러

브뤼셀 EU Affairs 특화 채용 플랫폼.
싱크탱크, NGO, EU 기관, 로비펌, 무역협회 공고.
"""

import re
import urllib.request
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
from crawlers.base import BaseCrawler, Job


class EuroBrusselsCrawler(BaseCrawler):

    BASE_URL = "https://www.eurobrussels.com"
    SEARCH_URL = "https://www.eurobrussels.com/jobs/"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def fetch_jobs(self) -> list[Job]:
        keywords = self.conditions.get("keywords", [])
        all_jobs: list[Job] = []
        seen_ids: set[str] = set()

        self.log("크롤링 시작")

        for keyword in keywords:
            self.log(f"검색 중: '{keyword}'")
            jobs = self._search(keyword, seen_ids)
            self.log(f"  → {len(jobs)}개 신규 공고 수집")
            all_jobs.extend(jobs)

        self.log(f"크롤링 완료 — 총 {len(all_jobs)}개")
        return all_jobs

    def _search(self, keyword: str, seen_ids: set) -> list[Job]:
        params = urllib.parse.urlencode({"search": keyword})
        url = f"{self.SEARCH_URL}?{params}"
        jobs = []

        try:
            req = urllib.request.Request(url, headers=self.HEADERS)
            with urllib.request.urlopen(req, timeout=20) as r:
                html = r.read().decode("utf-8", errors="replace")
        except Exception as e:
            self.log(f"  ⚠ 로드 실패: {e}")
            return []

        return self._parse(html, keyword, seen_ids)

    def _parse(self, html: str, keyword: str, seen_ids: set) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []

        for card in soup.select("li.premiumJobContainer, li.jobContainer"):
            try:
                link_el = card.select_one("a[href*='/job_display/']")
                if not link_el:
                    continue
                href   = link_el.get("href", "")
                url    = href if href.startswith("http") else self.BASE_URL + href

                # job_id: /job_display/291820/...
                m = re.search(r"/job_display/(\d+)/", href)
                job_id = m.group(1) if m else re.sub(r"\W+", "_", href)[:30]
                if job_id in seen_ids:
                    continue

                # 제목: img alt 속성
                img = card.select_one("img[alt]")
                title = img["alt"] if img and img.get("alt") else ""
                if not title:
                    continue

                # 텍스트 라인에서 조직·위치 추출
                lines = [l.strip() for l in card.get_text("\n").split("\n") if l.strip()]
                org      = lines[1] if len(lines) > 1 else "Unknown"
                location = lines[2] if len(lines) > 2 else "Brussels"

                seen_ids.add(job_id)
                jobs.append(Job(
                    title=title,
                    organization=org,
                    location=location,
                    category="EU Affairs",
                    deadline="",
                    url=url,
                    job_id=job_id,
                    source_site="EuroBrussels",
                    deadline_dt=None,
                    keywords_matched=[keyword],
                ))
            except Exception:
                continue

        return jobs
