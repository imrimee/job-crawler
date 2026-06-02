"""
crawlers/base.py
모든 크롤러가 상속받는 기본 클래스입니다.
새 사이트를 추가할 때는 이 클래스를 상속하고
fetch_jobs() 메서드만 구현하면 됩니다.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class Job:
    """크롤링된 채용 공고 하나를 나타내는 데이터 클래스"""
    title: str                              # 직위명
    organization: str                       # 조직/부서명
    location: str                           # 근무지
    category: str                           # 카테고리 (Internship, P-3 등)
    deadline: Optional[str]                 # 마감일 (문자열)
    url: str                                # 상세 페이지 URL
    job_id: str = ""                        # 공고 ID
    date_posted: Optional[str] = None       # 게시일
    description: str = ""                   # 직무 설명 (요약)
    source_site: str = ""                   # 출처 사이트명
    deadline_dt: Optional[datetime] = None  # 마감일 (datetime, 정렬용)
    keywords_matched: list = field(default_factory=list)  # 매칭된 키워드
    is_new: bool = False                                   # HTML 기준 신규 여부 (renderer에서 설정)


class BaseCrawler(ABC):
    """
    모든 사이트별 크롤러의 기본 클래스.

    새 사이트 추가 방법:
    1. crawlers/ 폴더에 새 파일 생성 (예: reliefweb.py)
    2. BaseCrawler 를 상속
    3. fetch_jobs() 메서드 구현
    4. config/search_conditions.yaml 의 sites 목록에 추가
    """

    def __init__(self, site_config: dict, conditions: dict):
        self.site_config = site_config
        self.conditions = conditions
        self.name = site_config.get("name", "Unknown")
        self.base_url = site_config.get("url", "")

    @abstractmethod
    def fetch_jobs(self) -> list[Job]:
        """
        사이트에서 채용 공고를 크롤링하여 Job 객체 리스트로 반환합니다.
        반드시 구현해야 합니다.
        """
        pass

    def log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{self.name}] {msg}")
