"""
Unpaywall API 封装：查询 OA 状态
"""

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from papergazer.models import UnpaywallResponse
from papergazer.utils.http_client import async_client

UNPAYWALL_API_URL = "https://api.unpaywall.org/v2"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
async def best_oa(doi: str, email: str) -> UnpaywallResponse:
    """
    查询 DOI 的最佳 OA 位置

    Args:
        doi: DOI
        email: 联系邮箱

    Returns:
        UnpaywallResponse: OA 状态信息
    """
    url = f"{UNPAYWALL_API_URL}/{doi}"
    params = {"email": email}

    async with async_client(timeout=30.0) as client:
        response = await client.get(url, params=params)

        # 处理422错误（通常是邮箱验证失败）
        if response.status_code == 422:
            error_data = response.json()
            error_msg = error_data.get("message", "Unpaywall API 邮箱验证失败")
            raise httpx.HTTPStatusError(
                error_msg,
                request=response.request,
                response=response,
            )

        response.raise_for_status()

        data = response.json()
        return UnpaywallResponse(
            is_oa=data.get("is_oa", False),
            best_oa_location=data.get("best_oa_location"),
        )
