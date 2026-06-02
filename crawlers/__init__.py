# crawlers/__init__.py — 전체 크롤러 등록부
# 새 크롤러 추가 시: 파일 생성 → import 추가 → CRAWLER_REGISTRY 등록
# → config/search_conditions.yaml sites 목록에 추가

# ── 영국(UK) 사이트 ─────────────────────────────────────────
from crawlers.un_careers         import UnCareersCrawler
from crawlers.reliefweb          import ReliefWebCrawler
from crawlers.jobs_ac_uk         import JobsAcUkCrawler
from crawlers.guardian_jobs      import GuardianJobsCrawler
from crawlers.prospects          import ProspectsCrawler
from crawlers.idealist           import IdealistCrawler
from crawlers.development_aid    import DevelopmentAidCrawler
from crawlers.civil_service_jobs import CivilServiceJobsCrawler
from crawlers.w4mp               import W4MPCrawler

# ── 한국(KR) 사이트 ─────────────────────────────────────────
from crawlers.koica         import KoicaCrawler
from crawlers.mofa_unrecruit import MofaUnrecruitCrawler
from crawlers.gojobs        import GojobsCrawler
from crawlers.alio          import AlioCrawler
from crawlers.jobkorea      import JobKoreaCrawler
from crawlers.saramin       import SaraminCrawler
from crawlers.wanted_kr     import WantedKrCrawler
from crawlers.worldjob      import WorldJobCrawler
from crawlers.incruit       import IncruitCrawler
from crawlers.ngo_kr        import NgoKrCrawler

# yaml의 crawler 값 → 크롤러 클래스 매핑
CRAWLER_REGISTRY = {
    # UK
    "un_careers":         UnCareersCrawler,
    "reliefweb":          ReliefWebCrawler,
    "jobs_ac_uk":         JobsAcUkCrawler,
    "guardian_jobs":      GuardianJobsCrawler,
    "prospects":          ProspectsCrawler,
    "idealist":           IdealistCrawler,
    "development_aid":    DevelopmentAidCrawler,
    "civil_service_jobs": CivilServiceJobsCrawler,
    "w4mp":               W4MPCrawler,
    # KR
    "koica":              KoicaCrawler,
    "mofa_unrecruit":     MofaUnrecruitCrawler,
    "gojobs":             GojobsCrawler,
    "alio":               AlioCrawler,
    "jobkorea":           JobKoreaCrawler,
    "saramin":            SaraminCrawler,
    "wanted_kr":          WantedKrCrawler,
    "worldjob":           WorldJobCrawler,
    "incruit":            IncruitCrawler,
    "ngo_kr":             NgoKrCrawler,
}
