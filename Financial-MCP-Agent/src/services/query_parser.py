"""把自然语言查询转换为股票分析工作流所需的初始状态。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from src.utils.state_definition import AgentState


_CODE_PATTERN = re.compile(r"(?<!\d)(\d{6})(?!\d)")
_COMPANY_PATTERNS = (
    re.compile(r"(?:分析|研究|看看|了解|评估)(?:一下)?\s*([A-Za-z一-龥]{2,12})"),
    re.compile(r"^\s*([A-Za-z一-龥]{2,12})\s*(?:[（(]?\d{6}[)）]?|的)"),
)
_LEADING_WORDS = ("请", "帮我", "给我", "我想", "一下")
_TRAILING_WORDS = (
    "这只股票",
    "这个股票",
    "的投资价值",
    "的中长期风险",
    "的基本面",
    "的技术面",
    "的估值",
    "的财务状况",
    "的",
)
_INVALID_COMPANIES = {
    "推荐",
    "一只",
    "值得买",
    "股票",
    "投资价值",
    "中长期风险",
    "基本面",
    "技术面",
}


@dataclass(frozen=True, slots=True)
class StockTarget:
    """从用户查询中识别出的股票标的。"""

    company_name: str | None
    raw_code: str | None
    market_code: str | None


def _market_code(raw_code: str | None) -> str | None:
    if raw_code is None:
        return None
    if raw_code.startswith("6"):
        return f"sh.{raw_code}"
    if raw_code.startswith(("0", "3")):
        return f"sz.{raw_code}"
    return raw_code


def _clean_company_name(candidate: str | None) -> str | None:
    if not candidate:
        return None
    company_name = candidate.strip(" ，。！？,.!?（）()")
    for word in _LEADING_WORDS:
        if company_name.startswith(word):
            company_name = company_name[len(word) :].strip()
    for word in _TRAILING_WORDS:
        if word in company_name:
            company_name = company_name.split(word, 1)[0].strip()
    if len(company_name) < 2 or any(
        invalid in company_name for invalid in _INVALID_COMPANIES
    ):
        return None
    return company_name


def parse_stock_target(query: str) -> StockTarget:
    """从查询中提取公司名称、六位代码和带交易所前缀的代码。"""

    code_match = _CODE_PATTERN.search(query)
    raw_code = code_match.group(1) if code_match else None
    company_name = None

    for pattern in _COMPANY_PATTERNS:
        match = pattern.search(query)
        if match:
            company_name = _clean_company_name(match.group(1))
            if company_name:
                break

    return StockTarget(
        company_name=company_name,
        raw_code=raw_code,
        market_code=_market_code(raw_code),
    )


def build_initial_state(
    query: str,
    target: StockTarget,
    now: datetime | None = None,
) -> AgentState:
    """创建 CLI 与 Web 共用的 LangGraph 初始状态。"""

    current = now or datetime.now()
    current_date_cn = current.strftime("%Y年%m月%d日")
    current_date_en = current.strftime("%Y-%m-%d")
    current_weekday_cn = [
        "星期一",
        "星期二",
        "星期三",
        "星期四",
        "星期五",
        "星期六",
        "星期日",
    ][current.weekday()]
    current_time = current.strftime("%H:%M:%S")

    data = {
        "query": query,
        "current_date": current_date_en,
        "current_date_cn": current_date_cn,
        "current_time": current_time,
        "current_weekday_cn": current_weekday_cn,
        "current_time_info": (
            f"{current_date_cn} ({current_date_en}) {current_weekday_cn} {current_time}"
        ),
        "analysis_timestamp": current.isoformat(),
    }
    if target.company_name:
        data["company_name"] = target.company_name
    if target.market_code:
        data["stock_code"] = target.market_code

    return AgentState(messages=[], data=data, metadata={})
