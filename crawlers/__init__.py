# crawlers/__init__.py
# 크롤러 등록부.
# 새 크롤러를 추가할 때 이 파일에도 등록하세요.
#
# 등록 방법:
#   1. crawlers/ 폴더에 새 파일 생성 (예: my_site.py)
#   2. BaseCrawler 상속 후 fetch_jobs() 구현
#   3. 아래에 import 추가
#   4. CRAWLER_REGISTRY 딕셔너리에 키:클래스 추가
#   5. config/search_conditions.yaml 의 sites 목록에 추가

from crawlers.un_careers         import UnCareersCrawler
from crawlers.reliefweb          import ReliefWebCrawler
from crawlers.jobs_ac_uk         import JobsAcUkCrawler
from crawlers.guardian_jobs      import GuardianJobsCrawler
from crawlers.prospects          import ProspectsCrawler
from crawlers.idealist           import IdealistCrawler
from crawlers.development_aid    import DevelopmentAidCrawler
from crawlers.civil_service_jobs import CivilServiceJobsCrawler
from crawlers.w4mp               import W4MPCrawler

# yaml의 crawler 값 → 크롤러 클래스 매핑
CRAWLER_REGISTRY = {
    "un_careers":         UnCareersCrawler,
    "reliefweb":          ReliefWebCrawler,
    "jobs_ac_uk":         JobsAcUkCrawler,
    "guardian_jobs":      GuardianJobsCrawler,
    "prospects":          ProspectsCrawler,
    "idealist":           IdealistCrawler,
    "development_aid":    DevelopmentAidCrawler,
    "civil_service_jobs": CivilServiceJobsCrawler,
    "w4mp":               W4MPCrawler,
}
