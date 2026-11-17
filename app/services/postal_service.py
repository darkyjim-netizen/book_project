"""우체국 우편번호 정보조회 API 연동."""

import xml.etree.ElementTree as ET
from urllib.parse import unquote

import requests

from app.core.config import get_settings
from app.core.exceptions import BusinessError


POSTAL_API_URL = (
    "http://openapi.epost.go.kr/postal/"
    "retrieveNewAdressAreaCdSearchAllService/"
    "retrieveNewAdressAreaCdSearchAllService/"
    "getNewAddressListAreaCdSearchAll"
)


def search_addresses(keyword: str, page: int) -> list[dict[str, str]]:
    # 기존 설정 객체에서 .env의 DATA_GO_KEY를 가져온다.
    encoded_key = get_settings().DATA_GO_KEY.strip()
    if not encoded_key:
        raise BusinessError("우편번호 조회 서비스가 설정되지 않았습니다.", "POSTAL_NOT_CONFIGURED", 503)

    try:
        response = requests.get(
            POSTAL_API_URL,
            params={
                # 저장된 키는 이미 URL 인코딩돼 있다. 한 번 디코딩해서
                # requests가 쿼리 문자열을 만들 때 이중 인코딩되지 않게 한다.
                "ServiceKey": unquote(encoded_key),
                # 우체국 API가 정한 이름으로 검색어와 페이지 정보를 전달한다.
                "srchwrd": keyword,
                "countPerPage": 10,
                "currentPage": page,
            },
            timeout=20,
        )
        response.raise_for_status()  # HTTP 4xx·5xx 응답은 예외로 처리한다.
        root = ET.fromstring(response.content)  # XML 응답을 읽어 검색할 수 있는 트리로 만든다.
    except requests.Timeout:
        raise BusinessError("우체국 API 응답 시간이 초과되었습니다.", "POSTAL_TIMEOUT", 504) from None
    except (requests.RequestException, ET.ParseError):
        raise BusinessError("우체국 API 응답을 처리할 수 없습니다.", "POSTAL_UPSTREAM_ERROR", 502) from None

    # HTTP 요청이 성공해도 우체국이 XML 안에 조회 실패를 표시할 수 있다.
    if root.findtext("./cmmMsgHeader/successYN") != "Y":
        raise BusinessError("우체국 API에서 조회 요청을 처리하지 못했습니다.", "POSTAL_UPSTREAM_ERROR", 502)

    # 검색 결과 한 건마다 우편번호, 도로명주소, 지번주소를 꺼낸다.
    # 우편번호를 문자열로 유지해 04524처럼 앞자리가 0인 값도 보존한다.
    return [
        {
            "zip_code": item.findtext("zipNo", default=""),
            "road_address": item.findtext("lnmAdres", default=""),
            "jibun_address": item.findtext("rnAdres", default=""),
        }
        for item in root.findall("./newAddressListAreaCdSearchAll")
    ]
