"""
notifier.py
새로 발견된 공고를 Gmail 또는 Slack으로 알림 발송합니다.
GitHub Secrets에 환경변수를 등록해야 합니다.

Gmail  : GMAIL_USER, GMAIL_APP_PASSWORD
Slack  : SLACK_WEBHOOK_URL
"""

import os
import json
import smtplib
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from crawlers.base import Job


def load_seen_ids(cache_file: str = ".seen_jobs.json") -> set[str]:
    """이전에 알림을 보낸 공고 ID를 불러옵니다."""
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            return set(json.load(f))
    return set()


def save_seen_ids(ids: set[str], cache_file: str = ".seen_jobs.json"):
    """알림을 보낸 공고 ID를 저장합니다."""
    with open(cache_file, "w") as f:
        json.dump(list(ids), f)


def get_new_jobs(jobs: list[Job], cache_file: str = ".seen_jobs.json") -> list[Job]:
    """이전에 본 적 없는 새 공고만 필터링합니다."""
    seen = load_seen_ids(cache_file)
    new_jobs = [j for j in jobs if f"{j.source_site}:{j.job_id}" not in seen]
    return new_jobs


def mark_as_seen(jobs: list[Job], cache_file: str = ".seen_jobs.json"):
    """공고를 '이미 알림 발송됨'으로 표시합니다."""
    seen = load_seen_ids(cache_file)
    for job in jobs:
        seen.add(f"{job.source_site}:{job.job_id}")
    save_seen_ids(seen, cache_file)


def notify(jobs: list[Job], new_jobs: list[Job], conditions: dict, html_path: str):
    """설정에 따라 이메일 또는 Slack 알림을 발송합니다."""
    cfg = conditions.get("notifications", {})

    # ── Gmail ─────────────────────────────────────────
    email_cfg = cfg.get("email", {})
    if email_cfg.get("enabled") and new_jobs:
        try:
            send_email(new_jobs, email_cfg)
            print(f"  📧 이메일 알림 발송 완료 ({len(new_jobs)}개 신규 공고)")
        except Exception as e:
            print(f"  ⚠  이메일 발송 실패: {e}")

    # ── Slack ──────────────────────────────────────────
    slack_cfg = cfg.get("slack", {})
    if slack_cfg.get("enabled"):
        try:
            send_slack(jobs, new_jobs, slack_cfg, html_path)
            print(f"  💬 Slack 알림 발송 완료")
        except Exception as e:
            print(f"  ⚠  Slack 발송 실패: {e}")


def send_email(new_jobs: list[Job], cfg: dict):
    gmail_user = os.environ["GMAIL_USER"]
    gmail_pw   = os.environ["GMAIL_APP_PASSWORD"]
    to_addr    = cfg.get("to", gmail_user)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Job Crawler] 새 채용 공고 {len(new_jobs)}개 발견"
    msg["From"]    = gmail_user
    msg["To"]      = to_addr

    rows = "".join(
        f"<tr><td style='padding:8px;border-bottom:1px solid #eee'>"
        f"<a href='{j.url}'>{j.title}</a></td>"
        f"<td style='padding:8px;border-bottom:1px solid #eee;color:#666'>{j.source_site}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #eee;color:#666'>{j.location}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #eee;color:#c00'>{j.deadline}</td></tr>"
        for j in new_jobs
    )
    html_body = f"""
    <html><body style='font-family:sans-serif;max-width:700px;margin:auto'>
    <h2 style='color:#009edb'>🌐 Job Crawler — 새 채용 공고 {len(new_jobs)}개</h2>
    <table style='width:100%;border-collapse:collapse;font-size:13px'>
      <tr style='background:#f5f5f5'>
        <th style='padding:8px;text-align:left'>직위</th>
        <th style='padding:8px;text-align:left'>사이트</th>
        <th style='padding:8px;text-align:left'>근무지</th>
        <th style='padding:8px;text-align:left'>마감일</th>
      </tr>
      {rows}
    </table>
    </body></html>
    """
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(gmail_user, gmail_pw)
        s.sendmail(gmail_user, to_addr, msg.as_string())


def send_slack(jobs: list[Job], new_jobs: list[Job], cfg: dict, html_path: str):
    webhook = os.environ["SLACK_WEBHOOK_URL"]
    mention = "@channel " if cfg.get("mention_on_new") and new_jobs else ""

    lines = [f"*🌐 Job Crawler 일일 리포트* — 총 {len(jobs)}개 공고"]
    if new_jobs:
        lines.append(f"{mention}*✨ 신규 공고 {len(new_jobs)}개*")
        for j in new_jobs[:5]:
            lines.append(f"  • <{j.url}|{j.title}> — {j.source_site} | {j.location} | 마감: {j.deadline}")
        if len(new_jobs) > 5:
            lines.append(f"  … 외 {len(new_jobs)-5}개")
    else:
        lines.append("오늘은 신규 공고가 없습니다.")

    payload = {"text": "\n".join(lines)}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(webhook, data=data, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req)
