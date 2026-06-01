# crawlers/__init__.py
# 새 크롤러를 추가하면 이 파일에도 등록하세요.

from crawlers.un_careers import UnCareersCrawler

# 사이트 식별자(search_conditions.yaml의 crawler 값)와 클래스를 매핑합니다.
CRAWLER_REGISTRY = {
    "un_careers": UnCareersCrawler,
    # "reliefweb": ReliefWebCrawler,   # 추가 예시
    # "linkedin":  LinkedInCrawler,    # 추가 예시
    # "undp":      UndpCrawler,        # 추가 예시
}
