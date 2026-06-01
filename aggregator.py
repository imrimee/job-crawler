"""
aggregator.py
모든 크롤러의 결과를 병합하고 search_conditions.yaml의 조건에 맞게 필터링합니다.
"""

from datetime import datetime, timedelta
from crawlers.base import Job


def filter_jobs(jobs: list[Job], conditions: dict) -> list[Job]:
    """수집된 전체 공고를 조건에 맞게 필터링합니다."""
    keywords   = [k.lower() for k in conditions.get("keywords", [])]
    locations  = [l.lower() for l in conditions.get("locations", [])]
    categories = [c.lower() for c in conditions.get("categories", [])]
    max_days   = conditions.get("deadline_within_days", 0)

    filtered = []
    for job in jobs:
        # ── 1. 키워드 필터 ──────────────────────────────────
        # 직위명 또는 설명에 키워드 중 하나 이상이 포함되어야 합니다.
        if keywords:
            searchable = (job.title + " " + job.description).lower()
            matched = [kw for kw in keywords if kw in searchable]
            if not matched:
                continue
            job.keywords_matched = list(set(job.keywords_matched + matched))

        # ── 2. 근무지 필터 ─────────────────────────────────
        # locations 목록이 비어 있으면 모든 근무지를 허용합니다.
        if locations:
            job_loc = job.location.lower()
            if not any(loc in job_loc for loc in locations):
                continue

        # ── 3. 카테고리 필터 ───────────────────────────────
        if categories:
            job_cat = job.category.lower()
            if not any(cat in job_cat for cat in categories):
                continue

        # ── 4. 마감일 필터 ─────────────────────────────────
        if max_days and job.deadline_dt:
            cutoff = datetime.now() + timedelta(days=max_days)
            if job.deadline_dt < datetime.now():
                continue   # 이미 마감된 공고 제외
            if job.deadline_dt > cutoff:
                continue   # 너무 먼 미래 공고 제외

        filtered.append(job)

    return filtered


def deduplicate(jobs: list[Job]) -> list[Job]:
    """여러 사이트에서 동일 공고가 수집된 경우 중복을 제거합니다."""
    seen = set()
    result = []
    for job in jobs:
        key = f"{job.source_site}:{job.job_id}"
        if key not in seen:
            seen.add(key)
            result.append(job)
    return result


def sort_jobs(jobs: list[Job]) -> list[Job]:
    """마감일 오름차순 정렬. 마감일 없는 공고는 맨 뒤로."""
    return sorted(
        jobs,
        key=lambda j: (j.deadline_dt or datetime(9999, 12, 31), j.title)
    )


def group_by_site(jobs: list[Job]) -> dict[str, list[Job]]:
    """사이트별로 공고를 묶습니다. HTML 렌더링에 사용됩니다."""
    groups: dict[str, list[Job]] = {}
    for job in jobs:
        groups.setdefault(job.source_site, []).append(job)
    return groups


def group_by_category(jobs: list[Job]) -> dict[str, list[Job]]:
    """카테고리별로 공고를 묶습니다."""
    # 카테고리를 3가지 버킷으로 단순화
    groups: dict[str, list[Job]] = {
        "인턴십": [],
        "전문직 (P급)": [],
        "컨설턴트": [],
        "기타": [],
    }
    for job in jobs:
        cat = job.category.lower()
        if "intern" in cat:
            groups["인턴십"].append(job)
        elif any(x in cat for x in ["p-1","p-2","p-3","p-4","p-5","p-6","p-7"]):
            groups["전문직 (P급)"].append(job)
        elif "consult" in cat or "con" == cat.strip():
            groups["컨설턴트"].append(job)
        else:
            groups["기타"].append(job)

    # 비어 있는 그룹 제거
    return {k: v for k, v in groups.items() if v}
