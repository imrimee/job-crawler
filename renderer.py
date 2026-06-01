"""
renderer.py
Jinja2 템플릿을 사용해 수집된 공고를 HTML 파일로 렌더링합니다.
"""

import os
import glob
from datetime import datetime, timezone, timedelta
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from crawlers.base import Job
from aggregator import group_by_category


KST = timezone(timedelta(hours=9))


def render_html(
    jobs: list[Job],
    conditions: dict,
    site_configs: list[dict],
    output_dir: str = "output",
    template_dir: str = "templates",
) -> str:
    """
    수집된 공고를 HTML로 렌더링하고 파일 경로를 반환합니다.
    """
    os.makedirs(output_dir, exist_ok=True)

    now = datetime.now(KST)
    run_date = now.strftime("%Y년 %m월 %d일")
    run_time = now.strftime("%H:%M KST")
    file_date = now.strftime("%Y-%m-%d")

    # 출력 파일명
    prefix   = conditions.get("output", {}).get("filename_prefix", "jobs")
    filename = f"{prefix}_{file_date}.html"
    filepath = os.path.join(output_dir, filename)

    # Job에 days_left 속성 추가
    today = now.replace(tzinfo=None)
    for job in jobs:
        if job.deadline_dt:
            delta = job.deadline_dt - today
            job.days_left = max(0, delta.days)
        else:
            job.days_left = None

    # 그룹화
    grouped = group_by_category(jobs)

    # 통계
    site_counts = {}
    for job in jobs:
        site_counts[job.source_site] = site_counts.get(job.source_site, 0) + 1

    category_counts = {k: len(v) for k, v in grouped.items()}

    # 아카이브 파일 목록 (최신순)
    all_files = sorted(
        glob.glob(os.path.join(output_dir, f"{prefix}_*.html")),
        reverse=True
    )
    archive_files = [os.path.basename(f) for f in all_files]

    # Jinja2 렌더링
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
    tmpl = env.get_template("jobs.html.j2")

    html = tmpl.render(
        run_date=run_date,
        run_time=run_time,
        total_count=len(jobs),
        sites=list(site_counts.keys()),
        site_counts=site_counts,
        category_counts=category_counts,
        grouped_jobs=grouped,
        keywords=conditions.get("keywords", []),
        locations=conditions.get("locations", []),
        site_configs=site_configs,
        archive_files=archive_files,
        current_file=filename,
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    return filepath


def cleanup_old_files(output_dir: str, prefix: str, keep_days: int):
    """오래된 HTML 파일을 삭제합니다."""
    if keep_days <= 0:
        return
    cutoff = datetime.now() - timedelta(days=keep_days)
    for fpath in glob.glob(os.path.join(output_dir, f"{prefix}_*.html")):
        fname = os.path.basename(fpath)
        date_str = fname.replace(f"{prefix}_", "").replace(".html", "")
        try:
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            if file_date < cutoff:
                os.remove(fpath)
                print(f"  🗑  오래된 파일 삭제: {fname}")
        except ValueError:
            pass
