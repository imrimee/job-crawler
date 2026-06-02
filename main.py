"""
main.py — Job Crawler 진입점 (UK + KR 통합)

사용법:
  python main.py               # 정상 실행
  python main.py --dry-run     # 더미 데이터로 HTML만 생성 (테스트)
  python main.py --no-notify   # 알림 없이 실행
  python main.py --region UK   # 영국 사이트만 실행
  python main.py --region KR   # 한국 사이트만 실행
  python main.py --kw-test     # 한국어 키워드 결과 수 테스트 출력
"""

import sys
import argparse
from datetime import datetime
from crawlers.base import Job
from crawlers import CRAWLER_REGISTRY
from aggregator import filter_jobs, deduplicate, sort_jobs
from renderer import render_html, cleanup_old_files
from notifier import get_new_jobs, mark_as_seen, notify

import yaml


def load_config(path: str = "config/search_conditions.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run(dry_run=False, no_notify=False, region_filter=None, kw_test=False):
    print("=" * 60)
    print(f"  🌐 Job Crawler 시작  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if region_filter:
        print(f"  🔍 지역 필터: {region_filter}")
    print("=" * 60)

    config     = load_config()
    conditions = config
    sites      = config.get("sites", [])
    output_cfg = config.get("output", {})

    all_jobs: list[Job] = []

    # ── 1. 크롤링 ────────────────────────────────────────────
    if dry_run:
        print("\n[DRY-RUN] 더미 데이터를 사용합니다.")
        all_jobs = _dummy_jobs()
    else:
        for site in sites:
            if not site.get("enabled", True):
                print(f"\n⏭  {site['name']} — 비활성화됨, 건너뜀")
                continue

            # 지역 필터 적용
            site_region = site.get("region", "UK").upper()
            if region_filter and site_region != region_filter.upper():
                continue

            crawler_key = site.get("crawler")
            crawler_cls = CRAWLER_REGISTRY.get(crawler_key)
            if not crawler_cls:
                print(f"\n⚠  {site['name']} — 크롤러 '{crawler_key}' 없음, 건너뜀")
                continue

            print(f"\n📡 [{site_region}] [{site['name']}] 크롤링 시작...")
            try:
                crawler  = crawler_cls(site, conditions)
                jobs     = crawler.fetch_jobs()
                all_jobs.extend(jobs)
                print(f"   ✅ {len(jobs)}개 수집")
            except Exception as e:
                print(f"   ❌ 크롤링 실패: {e}")

    # ── 2. 한국어 키워드 테스트 모드 ─────────────────────────
    if kw_test:
        _keyword_test_report(all_jobs, conditions)
        return None

    # ── 3. 필터링 + 중복 제거 + 정렬 ────────────────────────
    print(f"\n🔍 필터링 전: {len(all_jobs)}개")
    filtered = filter_jobs(all_jobs, conditions)
    filtered = deduplicate(filtered)
    filtered = sort_jobs(filtered)
    print(f"   필터링 후: {len(filtered)}개")

    # ── 4. HTML 렌더링 ───────────────────────────────────────
    print("\n📄 HTML 렌더링 중...")
    active_sites = [s for s in sites if s.get("enabled", True)]
    if region_filter:
        active_sites = [s for s in active_sites if s.get("region","UK").upper() == region_filter.upper()]

    output_dir = "docs"
    html_path  = render_html(
        jobs=filtered,
        conditions=conditions,
        site_configs=active_sites,
        output_dir=output_dir,
    )
    print(f"   ✅ 저장 완료: {html_path}")

    keep_days = output_cfg.get("keep_last_days", 30)
    prefix    = output_cfg.get("filename_prefix", "jobs")
    cleanup_old_files(output_dir, prefix, keep_days)

    # ── 5. 알림 발송 ─────────────────────────────────────────
    if not no_notify and not dry_run:
        new_jobs = get_new_jobs(filtered)
        if new_jobs:
            print(f"\n🔔 신규 공고 {len(new_jobs)}개 발견 — 알림 발송 중...")
        notify(filtered, new_jobs, conditions, html_path)
        mark_as_seen(filtered)

    print("\n" + "=" * 60)
    print(f"  ✅ 완료 — {len(filtered)}개 공고, {html_path}")
    print("=" * 60)
    return html_path


def _keyword_test_report(jobs: list[Job], conditions: dict):
    """
    한국어 키워드(B안) vs 영어만(A안) 결과 수 비교 리포트 출력.
    사용자가 질문3 최종 답변을 결정하는 데 사용됩니다.
    """
    en_keywords = [k.lower() for k in conditions.get("keywords",    [])]
    kr_keywords = [k.lower() for k in conditions.get("keywords_kr", [])]

    kr_sites = [
        j for j in jobs
        if j.source_site in {
            "KOICA","국제기구채용정보센터(MOFA)","나라일터","알리오(ALIO)",
            "잡코리아","사람인","원티드","글로벌청년취업드림","인크루트","NGO잡스(한국NGO협의회)"
        }
    ]

    def count_matched(pool, kw_list):
        result = set()
        for job in pool:
            s = (job.title + " " + job.description).lower()
            if any(kw in s for kw in kw_list):
                result.add(f"{job.source_site}:{job.job_id}")
        return len(result)

    en_count  = count_matched(kr_sites, en_keywords)
    kr_count  = count_matched(kr_sites, kr_keywords)
    both_count = count_matched(kr_sites, en_keywords + kr_keywords)

    print("\n" + "=" * 60)
    print("  📊 한국어 키워드 테스트 결과 (KR 사이트 기준)")
    print("=" * 60)
    print(f"  총 수집 공고 수  : {len(kr_sites)}개")
    print(f"  A안 (영어만)    : {en_count}개 매칭")
    print(f"  B안 (영어+한국어): {both_count}개 매칭")
    print(f"  한국어 키워드만  : {kr_count}개 매칭")
    print(f"  B안 증가분      : +{both_count - en_count}개 ({both_count - en_count}개가 한국어 키워드에만 매칭)")
    print("=" * 60)
    print("\n  사이트별 B안 매칭 현황:")
    site_counts: dict[str, int] = {}
    for job in kr_sites:
        s = (job.title + " " + job.description).lower()
        if any(kw in s for kw in en_keywords + kr_keywords):
            site_counts[job.source_site] = site_counts.get(job.source_site, 0) + 1
    for site, cnt in sorted(site_counts.items(), key=lambda x: -x[1]):
        print(f"    {site}: {cnt}개")


def _dummy_jobs() -> list[Job]:
    from datetime import timedelta
    return [
        Job(
            title="Political Affairs Officer, P-3",
            organization="Department of Peace Operations",
            location="London, United Kingdom",
            category="Professional, P-3",
            deadline=(datetime.now() + timedelta(days=30)).strftime("%b %d, %Y"),
            url="https://careers.un.org/99999",
            job_id="99999", source_site="UN Careers",
            deadline_dt=datetime.now() + timedelta(days=30),
            keywords_matched=["political affairs"],
        ),
        Job(
            title="국제협력 인턴",
            organization="KOICA 한국국제협력단",
            location="Seoul, Korea",
            category="인턴십",
            deadline=(datetime.now() + timedelta(days=20)).strftime("%Y.%m.%d"),
            url="https://recruit.koica.go.kr/88888",
            job_id="88888", source_site="KOICA",
            deadline_dt=datetime.now() + timedelta(days=20),
            keywords_matched=["국제협력"],
        ),
        Job(
            title="Research Officer - Governance",
            organization="Guardian NGO Trust",
            location="London, UK",
            category="Research",
            deadline=(datetime.now() + timedelta(days=14)).strftime("%b %d, %Y"),
            url="https://jobs.theguardian.com/77777",
            job_id="77777", source_site="Guardian Jobs",
            deadline_dt=datetime.now() + timedelta(days=14),
            keywords_matched=["governance", "research officer"],
        ),
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job Crawler (UK + KR)")
    parser.add_argument("--dry-run",   action="store_true", help="더미 데이터로 HTML만 생성")
    parser.add_argument("--no-notify", action="store_true", help="알림 없이 실행")
    parser.add_argument("--region",    type=str, default=None, help="UK 또는 KR만 실행")
    parser.add_argument("--kw-test",   action="store_true", help="한국어 키워드 테스트 리포트 출력")
    args = parser.parse_args()
    run(dry_run=args.dry_run, no_notify=args.no_notify,
        region_filter=args.region, kw_test=args.kw_test)
