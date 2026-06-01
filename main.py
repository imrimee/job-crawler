"""
main.py
Job Crawler 진입점.
직접 실행하거나 GitHub Actions에서 호출됩니다.

사용법:
  python main.py                     # 정상 실행
  python main.py --dry-run           # 크롤링 없이 더미 데이터로 HTML만 생성 (테스트용)
  python main.py --no-notify         # 알림 발송 없이 실행
"""

import sys
import argparse
import importlib
import yaml
from datetime import datetime
from crawlers.base import Job
from crawlers import CRAWLER_REGISTRY
from aggregator import filter_jobs, deduplicate, sort_jobs
from renderer import render_html, cleanup_old_files
from notifier import get_new_jobs, mark_as_seen, notify


def load_config(path: str = "config/search_conditions.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run(dry_run: bool = False, no_notify: bool = False):
    print("=" * 60)
    print(f"  🌐 Job Crawler 시작  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    config = load_config()
    conditions = config          # 전체 config를 conditions로 사용
    sites = config.get("sites", [])
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

            crawler_key = site.get("crawler")
            crawler_cls = CRAWLER_REGISTRY.get(crawler_key)

            if not crawler_cls:
                print(f"\n⚠  {site['name']} — 크롤러 '{crawler_key}' 없음, 건너뜀")
                continue

            print(f"\n📡 [{site['name']}] 크롤링 시작...")
            try:
                crawler = crawler_cls(site, conditions)
                jobs = crawler.fetch_jobs()
                all_jobs.extend(jobs)
                print(f"   ✅ {len(jobs)}개 수집")
            except Exception as e:
                print(f"   ❌ 크롤링 실패: {e}")

    # ── 2. 필터링 + 중복 제거 + 정렬 ────────────────────────
    print(f"\n🔍 필터링 전: {len(all_jobs)}개")
    filtered = filter_jobs(all_jobs, conditions)
    filtered = deduplicate(filtered)
    filtered = sort_jobs(filtered)
    print(f"   필터링 후: {len(filtered)}개")

    # ── 3. HTML 렌더링 ───────────────────────────────────────
    print("\n📄 HTML 렌더링 중...")
    output_dir = "docs"
    html_path = render_html(
        jobs=filtered,
        conditions=conditions,
        site_configs=[s for s in sites if s.get("enabled", True)],
        output_dir=output_dir,
    )
    print(f"   ✅ 저장 완료: {html_path}")

    # 오래된 파일 정리
    keep_days = output_cfg.get("keep_last_days", 30)
    prefix    = output_cfg.get("filename_prefix", "jobs")
    cleanup_old_files(output_dir, prefix, keep_days)

    # ── 4. 알림 발송 ─────────────────────────────────────────
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


def _dummy_jobs() -> list[Job]:
    """테스트용 더미 데이터"""
    from datetime import datetime, timedelta
    return [
        Job(
            title="Political Affairs Officer, P-3",
            organization="Department of Peace Operations",
            location="London, United Kingdom",
            category="Professional and Higher Categories, P-3",
            deadline=(datetime.now() + timedelta(days=30)).strftime("%b %d, %Y"),
            url="https://careers.un.org/jobSearchDescription/99999?language=EN",
            job_id="99999",
            date_posted=datetime.now().strftime("%b %d, %Y"),
            source_site="UN Careers",
            deadline_dt=datetime.now() + timedelta(days=30),
            keywords_matched=["political affairs"],
        ),
        Job(
            title="Public Administration Intern",
            organization="UNDP",
            location="United Kingdom",
            category="Internship, I-1",
            deadline=(datetime.now() + timedelta(days=10)).strftime("%b %d, %Y"),
            url="https://careers.un.org/jobSearchDescription/88888?language=EN",
            job_id="88888",
            date_posted=datetime.now().strftime("%b %d, %Y"),
            source_site="UN Careers",
            deadline_dt=datetime.now() + timedelta(days=10),
            keywords_matched=["public administration"],
        ),
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job Crawler")
    parser.add_argument("--dry-run",   action="store_true", help="더미 데이터로 HTML만 생성 (테스트)")
    parser.add_argument("--no-notify", action="store_true", help="알림 발송 없이 실행")
    args = parser.parse_args()

    run(dry_run=args.dry_run, no_notify=args.no_notify)
