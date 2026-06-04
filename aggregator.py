"""
aggregator.py
모든 크롤러의 결과를 병합하고 조건에 맞게 필터링합니다.
UK 사이트와 KR 사이트의 근무지/키워드 필터를 각각 적용합니다.
"""

from datetime import datetime, timedelta
from crawlers.base import Job


def filter_jobs(jobs: list[Job], conditions: dict) -> list[Job]:
    """지역(region)별로 적절한 키워드·근무지 필터를 적용합니다."""

    # ── 공통 설정 ──────────────────────────────────────────
    en_keywords  = [k.lower() for k in conditions.get("keywords",    [])]
    eu_keywords  = [k.lower() for k in conditions.get("keywords_eu", [])]
    kr_keywords  = [k.lower() for k in conditions.get("keywords_kr", [])]
    all_keywords = en_keywords + kr_keywords
    eu_all_keywords = en_keywords + eu_keywords
    exclude_kws  = [k.lower() for k in conditions.get("exclude_title_keywords", [])]

    uk_locations = [l.lower() for l in conditions.get("locations",    [])]
    kr_locations = [l.lower() for l in conditions.get("locations_kr", [])]

    categories   = [c.lower() for c in conditions.get("categories",   [])]
    max_days     = conditions.get("deadline_within_days", 0)

    # 사이트→지역 매핑 (site_config에서 region 읽기)
    site_region: dict[str, str] = {}
    for s in conditions.get("sites", []):
        site_region[s.get("name", "")] = s.get("region", "UK").upper()

    filtered = []
    for job in jobs:
        region = site_region.get(job.source_site, "UK").upper()

        # ── 0. 기술 직군 제외 필터 (제목 기준) ─────────────
        if exclude_kws:
            title_lower = job.title.lower()
            if any(ex in title_lower for ex in exclude_kws):
                continue

        # ── 1. 키워드 필터 ──────────────────────────────
        searchable = (job.title + " " + job.description).lower()
        if region == "KR":
            kw_pool = all_keywords      # KR: 영어+한국어
        elif region == "EU":
            kw_pool = eu_all_keywords   # EU: 영어+EU 추가키워드
        else:
            kw_pool = en_keywords       # UK: 영어만

        if kw_pool:
            matched = [kw for kw in kw_pool if kw in searchable]
            if not matched:
                continue
            job.keywords_matched = list(set(job.keywords_matched + matched))

        # ── 2. 근무지 필터 ─────────────────────────────
        if region == "KR":
            loc_pool = kr_locations
        elif region == "EU":
            loc_pool = []            # EU: 근무지 필터 없음 (전체 수집)
        else:
            loc_pool = uk_locations

        if loc_pool:
            job_loc = job.location.lower()
            if not any(loc in job_loc for loc in loc_pool):
                continue

        # ── 3. 카테고리 필터 ───────────────────────────
        if categories:
            if not any(cat in job.category.lower() for cat in categories):
                continue

        # ── 4. 마감일 필터 ─────────────────────────────
        if max_days and job.deadline_dt:
            cutoff = datetime.now() + timedelta(days=max_days)
            if job.deadline_dt < datetime.now():
                continue
            if job.deadline_dt > cutoff:
                continue

        filtered.append(job)

    return filtered


def deduplicate(jobs: list[Job]) -> list[Job]:
    seen = set()
    result = []
    for job in jobs:
        key = f"{job.source_site}:{job.job_id}"
        if key not in seen:
            seen.add(key)
            result.append(job)
    return result


def sort_jobs(jobs: list[Job]) -> list[Job]:
    return sorted(
        jobs,
        key=lambda j: (j.deadline_dt or datetime(9999, 12, 31), j.title)
    )


def group_by_region(jobs: list[Job], site_configs: list[dict]) -> dict[str, list[Job]]:
    """영국/한국별로 분류합니다. HTML 렌더링에 사용됩니다."""
    site_region = {s["name"]: s.get("region", "UK") for s in site_configs}
    groups: dict[str, list[Job]] = {"🇬🇧 영국 (UK)": [], "🇪🇺 유럽 (EU)": [], "🇰🇷 한국 (KR)": []}
    for job in jobs:
        region = site_region.get(job.source_site, "UK").upper()
        if region == "KR":
            groups["🇰🇷 한국 (KR)"].append(job)
        elif region == "EU":
            groups["🇪🇺 유럽 (EU)"].append(job)
        else:
            groups["🇬🇧 영국 (UK)"].append(job)
    return {k: v for k, v in groups.items() if v}


def group_by_category(jobs: list[Job]) -> dict[str, list[Job]]:
    groups: dict[str, list[Job]] = {
        "인턴십": [], "전문직 (P급)": [],
        "컨설턴트": [], "공공기관 / 정부": [],
        "NGO / 시민사회": [], "기타": [],
    }
    for job in jobs:
        cat = job.category.lower()
        if "intern" in cat or "인턴" in cat:
            groups["인턴십"].append(job)
        elif any(x in cat for x in ["p-1","p-2","p-3","p-4","p-5"]):
            groups["전문직 (P급)"].append(job)
        elif "consult" in cat or "con" == cat.strip():
            groups["컨설턴트"].append(job)
        elif any(x in cat for x in ["공공", "정부", "공무원", "civil", "government", "public"]):
            groups["공공기관 / 정부"].append(job)
        elif any(x in cat for x in ["ngo", "시민", "비영리", "nonprofit", "charity"]):
            groups["NGO / 시민사회"].append(job)
        else:
            groups["기타"].append(job)
    return {k: v for k, v in groups.items() if v}
