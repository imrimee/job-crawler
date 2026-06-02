"""
crawlers/reliefweb_eu.py
ReliefWeb EU 크롤러 — 유럽 소재 포지션 특화

기존 ReliefWeb API를 활용하되, 유럽 주요국으로 필터링합니다.
"""

import json
import urllib.request
from datetime import datetime
from crawlers.base import BaseCrawler, Job


EU_COUNTRIES = [
    "Belgium", "France", "Germany", "Switzerland", "Austria",
    "Netherlands", "Sweden", "Norway", "Denmark", "Italy",
    "Spain", "Poland", "Czech Republic", "Finland", "Portugal",
    "Hungary", "Romania", "Slovakia", "Luxembourg",
]


class ReliefWebEuCrawler(BaseCrawler):

    API_URL = "https://api.reliefweb.int/v1/jobs"

    def fetch_jobs(self) -> list[Job]:
        keywords = self.conditions.get("keywords", [])
        all_jobs: list[Job] = []
        seen_ids: set[str] = set()

        self.log("크롤링 시작 (공개 API — 유럽 필터)")

        for keyword in keywords:
            self.log(f"검색 중: '{keyword}'")
            jobs = self._fetch_by_keyword(keyword, seen_ids)
            self.log(f"  → {len(jobs)}개 신규 공고 수집")
            all_jobs.extend(jobs)

        self.log(f"크롤링 완료 — 총 {len(all_jobs)}개")
        return all_jobs

    def _fetch_by_keyword(self, keyword: str, seen_ids: set) -> list[Job]:
        payload = {
            "appname": "job-crawler",
            "query": {
                "value": keyword,
                "fields": ["title", "body"],
            },
            "filter": {
                "operator": "AND",
                "conditions": [
                    {
                        "field": "country.name",
                        "value": EU_COUNTRIES,
                        "operator": "OR",
                    }
                ],
            },
            "fields": {
                "include": [
                    "id", "title", "source.name", "city", "country",
                    "date.created", "date.closing", "url_alias",
                    "career_categories.name",
                ]
            },
            "sort": ["date.created:desc"],
            "limit": 50,
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.API_URL,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            self.log(f"  ⚠ API 호출 실패: {e}")
            return []

        jobs = []
        for item in result.get("data", []):
            fields  = item.get("fields", {})
            job_id  = str(item.get("id", ""))
            if job_id in seen_ids:
                continue

            title        = fields.get("title", "")
            org          = fields.get("source", [{}])
            org_name     = org[0].get("name", "Unknown") if org else "Unknown"
            city         = fields.get("city", [{}])
            city_name    = city[0].get("name", "") if city else ""
            country      = fields.get("country", [{}])
            country_name = country[0].get("name", "") if country else ""
            location     = f"{city_name}, {country_name}".strip(", ")
            categories   = fields.get("career_categories", [{}])
            category     = categories[0].get("name", "") if categories else ""
            closing      = fields.get("date", {}).get("closing", "")
            created      = fields.get("date", {}).get("created", "")
            url_alias    = fields.get("url_alias", "")
            url          = f"https://reliefweb.int{url_alias}" if url_alias else "https://reliefweb.int/jobs"

            deadline_str = closing[:10] if closing else ""
            deadline_dt  = self._parse_date(deadline_str)
            date_posted  = created[:10] if created else ""

            seen_ids.add(job_id)
            jobs.append(Job(
                title=title,
                organization=org_name,
                location=location,
                category=category,
                deadline=deadline_str,
                url=url,
                job_id=job_id,
                date_posted=date_posted,
                source_site="ReliefWeb (EU)",
                deadline_dt=deadline_dt,
                keywords_matched=[keyword],
            ))

        return jobs

    def _parse_date(self, s: str) -> datetime | None:
        try:
            return datetime.strptime(s, "%Y-%m-%d")
        except Exception:
            return None
