"""
crawlers/impactpool.py
impactpool.org 크롤러

800개+ 국제기구·NGO 공고 통합 플랫폼.
Junior/Internship 특화, 유럽 기반 포지션 비중 높음.
"""

import urllib.request
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
from crawlers.base import BaseCrawler, Job


class ImpactpoolCrawler(BaseCrawler):

    BASE_URL = "https://www.impactpool.org"
    SEARCH_URL = "https://www.impactpool.org/jobs"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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
        params = urllib.parse.urlencode({"q": keyword})
        url = f"{self.SEARCH_URL}?{params}"

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

        for card in soup.select("div.job"):
            try:
                link_el = card.select_one("a[href]")
                if not link_el:
                    continue
                href   = link_el.get("href", "")
                url    = href if href.startswith("http") else self.BASE_URL + href

                # job_id: /jobs/1216839
                import re
                m = re.search(r"/jobs/(\d+)", href)
                job_id = m.group(1) if m else href.strip("/").split("/")[-1]
                if job_id in seen_ids:
                    continue

                # 제목: div[type="cardTitle"]
                title_el = card.select_one('div[type="cardTitle"]')
                title    = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    # img alt fallback
                    img = card.select_one("img[alt]")
                    title = img["alt"] if img and img.get("alt") else ""
                if not title:
                    continue

                # 조직: 첫 번째 bodyEmphasis
                org_els = card.select('div[type="bodyEmphasis"]')
                org     = org_els[0].get_text(strip=True) if org_els else "Unknown"

                # 위치: 두 번째 레이아웃 내 첫 번째 텍스트
                location = "Europe"
                if len(org_els) > 1:
                    location = org_els[1].get_text(strip=True)

                seen_ids.add(job_id)
                jobs.append(Job(
                    title=title,
                    organization=org,
                    location=location,
                    category="",
                    deadline="",
                    url=url,
                    job_id=job_id,
                    source_site="Impactpool",
                    deadline_dt=None,
                    keywords_matched=[keyword],
                ))
            except Exception:
                continue

        return jobs
