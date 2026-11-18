"""우정사업본부 우편번호 검색을 서버에서 중계한다."""
from urllib.parse import unquote
from xml.etree import ElementTree

import httpx
from fastapi import APIRouter, HTTPException, Query
from team_backend.app.core.config import settings

router = APIRouter(tags=["우편번호"])
URL = "http://openapi.epost.go.kr/postal/retrieveNewAdressAreaCdSearchAllService/retrieveNewAdressAreaCdSearchAllService/getNewAddressListAreaCdSearchAll"

@router.get('/postal/search')
async def search_postal(keyword: str = Query(min_length=2, max_length=200), page: int = Query(default=1, ge=1, le=1000)):
    if not settings.DATA_GO_KEY:
        raise HTTPException(503, '우편번호 API 키가 설정되지 않았습니다.')
    try:
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            response = await client.get(URL, params={'serviceKey': unquote(settings.DATA_GO_KEY), 'srchwrd': keyword.strip(), 'countPerPage': 10, 'currentPage': page})
            response.raise_for_status()
        root = ElementTree.fromstring(response.content)
        if root.findtext('.//successYN') == 'N' or root.findtext('.//returnReasonCode'):
            raise HTTPException(502, '우편번호 검색 서비스에서 요청을 처리하지 못했습니다. API 활용 승인 상태를 확인해 주세요.')
        return [{'zip_code': item.findtext('zipNo', ''), 'road_address': item.findtext('lnmAdres', ''), 'jibun_address': item.findtext('rnAdres', '')} for item in root.findall('.//newAddressListAreaCdSearchAll')]
    except (httpx.HTTPError, ElementTree.ParseError):
        raise HTTPException(502, '우편번호 검색 서비스에 연결할 수 없습니다.')
