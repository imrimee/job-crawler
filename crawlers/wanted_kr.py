"""
crawlers/wanted_kr.py
wanted.co.kr 크롤러 (원티드)

스타트업·글로벌 기업 특화 채용 플랫폼.
공개 API(v4) 사용 — Playwright 불필요.
"""

import json
import urllib.request
import urllib.parse
from datetime import datetime
from crawlers.base import BaseCrawler, Job


class WantedKrCrawler(BaseCrawler):

    BASE_URL = "https://www.wanted.co.kr"
    API_URL  = "https://www.wanted.co.kr/api/v4/jobs"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (compatible; JobCrawler/1.0)",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.wanted.co.kr/",
        "wanted-user-country": "KR",
        "wanted-user-language": "ko",
    }

    def fetch_jobs(self) -> list[Job]:
        all_keywords = self.conditions.get("keywords", [])
        kr_keywords  = self.conditions.get("keywords_kr", [])
        combined     = all_keywords + kr_keywords

        all_jobs: list[Job] = []
        seen_ids: set[str] = set()

        self.log("크롤링 시작 (API 방식)")

        for keyword in combined:
            self.log(f"검색 중: '{keyword}'")
            jobs = self._search(keyword, seen_ids)
            self.log(f"  → {len(jobs)}개 수집")
            all_jobs.extend(jobs)

        self.log(f"크롤링 완료 — 총 {len(all_jobs)}개")
        return all_jobs

    def _search(self, keyword: str, seen_ids: set) -> list[Job]:
        params = urllib.parse.urlencode({
            "query":  keyword,
            "limit":  100,
            "offset": 0,
            "country": "kr",
        })
        url = f"{self.API_URL}?{params}"
        try:
            req = urllib.request.Request(url, headers=self.HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read())
        except Exception as e:
            self.log(f"  ⚠ API 실패: {e}")
            return []

        jobs = []
        for item in data.get("data", []):
            try:
                job_id = str(item.get("id", ""))
                if not job_id or job_id in seen_ids:
                    continue

                title   = item.get("position", "")
                org     = item.get("company", {}).get("name", "Unknown")
                # 지역
                address = item.get("address", {})
                city    = address.get("city", "")
                country = address.get("country", "Korea")
                location = f"{city}, {country}".strip(", ") or "Korea"

                tags    = [t.get("tag_string", "") for t in item.get("tags", [])]
                category = ", ".join(tags[:3]) if tags else "일반"

                deadline_str = item.get("due_time", "")
                if deadline_str:
                    deadline_str = deadline_str[:10]

                url = f"{self.BASE_URL}/wd/{job_id}"
                deadline_dt = self._parse_date(deadline_str)
                seen_ids.add(job_id)

                jobs.append(Job(
                    title=title,
                    organization=org,
                    location=location,
                    category=category,
                    deadline=deadline_str,
                    url=url,
                    job_id=f"wanted_{job_id}",
                    description=title,
                    source_site="원티드",
                    deadline_dt=deadline_dt,
                    keywords_matched=[keyword],
                ))
            except Exception:
                continue
        return jobs

    def _parse_date(self, s: str) -> datetime | None:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d")
        except Exception:
            return None
