# 🌐 Job Crawler

여러 채용 사이트를 매일 자동으로 크롤링하여 HTML 리포트를 생성합니다.  
GitHub Actions로 매일 오전 9시(KST)에 자동 실행됩니다.

---

## 📁 프로젝트 구조

```
job-crawler/
├── .github/workflows/
│   └── daily_crawl.yml        ← GitHub Actions 스케줄러
├── crawlers/
│   ├── base.py                ← 크롤러 기본 클래스 (수정 불필요)
│   ├── __init__.py            ← 크롤러 등록부
│   └── un_careers.py          ← UN Careers 크롤러
├── config/
│   └── search_conditions.yaml ← ✏️ 검색 조건 설정 (자주 수정)
├── templates/
│   └── jobs.html.j2           ← HTML 템플릿
├── output/                    ← 생성된 HTML 저장 위치
├── aggregator.py              ← 결과 병합 & 필터링
├── renderer.py                ← HTML 렌더링
├── notifier.py                ← 이메일/Slack 알림
├── main.py                    ← 진입점
└── requirements.txt
```

---

## 🚀 시작하기

### 1. 저장소 Fork 또는 Clone

```bash
git clone https://github.com/your-username/job-crawler.git
cd job-crawler
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. 테스트 실행 (더미 데이터)

```bash
python main.py --dry-run
```

`output/jobs_YYYY-MM-DD.html` 파일이 생성되면 성공입니다.

### 4. 실제 크롤링 실행

```bash
python main.py
```

---

## ✏️ 검색 조건 변경하기

`config/search_conditions.yaml` 파일만 수정하면 됩니다.

### 키워드 추가/삭제

```yaml
keywords:
  - "political science"
  - "international relations"
  - "governance"
  - "humanitarian"          # ← 추가
  # - "social science"      # ← 주석 처리로 비활성화
```

### 근무지 추가/삭제

```yaml
locations:
  - "United Kingdom"
  - "London"
  - "Geneva"                # ← 추가
  # - "New York"            # ← 주석 처리로 비활성화
```

### 새 사이트 추가

1. `config/search_conditions.yaml`의 `sites` 목록에 추가:

```yaml
sites:
  - name: "ReliefWeb"
    url: "https://reliefweb.int/jobs"
    crawler: "reliefweb"
    enabled: true
```

2. `crawlers/reliefweb.py` 파일을 생성하고 `BaseCrawler`를 상속:

```python
from crawlers.base import BaseCrawler, Job

class ReliefWebCrawler(BaseCrawler):
    def fetch_jobs(self) -> list[Job]:
        # 크롤링 로직 구현
        ...
```

3. `crawlers/__init__.py`에 등록:

```python
from crawlers.reliefweb import ReliefWebCrawler

CRAWLER_REGISTRY = {
    "un_careers": UnCareersCrawler,
    "reliefweb":  ReliefWebCrawler,   # ← 추가
}
```

---

## ⚙️ GitHub Actions 자동화

### 설정 방법

1. GitHub에 저장소 Push
2. **Settings → Pages → Source: Deploy from a branch → `main` / `output`** 설정  
   → `https://your-username.github.io/job-crawler/` 에서 결과 열람 가능

3. 알림 설정 (선택사항):
   - **Settings → Secrets and variables → Actions** 에서 Secret 추가:
     - `GMAIL_USER` : Gmail 주소
     - `GMAIL_APP_PASSWORD` : [Gmail 앱 비밀번호](https://support.google.com/accounts/answer/185833)
     - `SLACK_WEBHOOK_URL` : Slack Webhook URL

### 수동 실행

GitHub 저장소 → **Actions → Daily Job Crawl → Run workflow**

---

## 📧 알림 설정

`config/search_conditions.yaml`에서 활성화:

```yaml
notifications:
  email:
    enabled: true
    to: "your@email.com"
  slack:
    enabled: true
    mention_on_new: true
```

---

## 🗑️ 오래된 파일 관리

```yaml
output:
  keep_last_days: 30    # 최근 30일치만 보관
```
