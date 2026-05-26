from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class DataEndpoint:
    name: str
    category: str
    description: str


ENDPOINTS: List[DataEndpoint] = [
    DataEndpoint("realtime_quote", "行情", "腾讯/通达信实时行情、估值、市值、涨跌停"),
    DataEndpoint("daily_bars", "行情", "日 K 线"),
    DataEndpoint("index_bars", "行情", "指数 K 线"),
    DataEndpoint("tick_trades", "行情", "逐笔成交"),
    DataEndpoint("order_book", "行情", "五档盘口"),
    DataEndpoint("baidu_kline", "行情", "百度股市通 K 线与均线"),
    DataEndpoint("research_reports", "研报", "东财研报列表"),
    DataEndpoint("research_pdf", "研报", "研报 PDF 下载"),
    DataEndpoint("consensus_eps", "研报", "同花顺一致预期 EPS"),
    DataEndpoint("iwencai_report_search", "研报", "iwencai 语义研报搜索"),
    DataEndpoint("hot_stocks", "信号", "同花顺热点强势股"),
    DataEndpoint("northbound_flow", "信号", "北向资金实时/历史"),
    DataEndpoint("concept_blocks", "信号", "百度概念/行业/地域归属"),
    DataEndpoint("capital_flow_minute", "信号", "东财分钟级资金流"),
    DataEndpoint("dragon_tiger", "信号", "龙虎榜席位"),
    DataEndpoint("market_dragon_tiger", "信号", "全市场龙虎榜"),
    DataEndpoint("lockup_calendar", "信号", "限售解禁日历"),
    DataEndpoint("sector_performance", "信号", "行业板块排名"),
    DataEndpoint("margin_trading", "资金面", "融资融券明细"),
    DataEndpoint("block_trades", "资金面", "大宗交易"),
    DataEndpoint("shareholder_count", "资金面", "股东户数变化"),
    DataEndpoint("dividend_history", "资金面", "分红送转历史"),
    DataEndpoint("capital_flow_120d", "资金面", "个股资金流 120 日"),
    DataEndpoint("stock_news", "新闻", "东财个股新闻"),
    DataEndpoint("cls_news", "新闻", "财联社快讯"),
    DataEndpoint("global_news", "新闻", "东财全球财经资讯"),
    DataEndpoint("financial_snapshot", "基础数据", "季报财务快照"),
    DataEndpoint("f10_profile", "基础数据", "F10 公司资料"),
    DataEndpoint("stock_basic", "基础数据", "东财个股基础信息"),
    DataEndpoint("financial_statements", "基础数据", "新浪财报三表"),
    DataEndpoint("announcements", "公告", "巨潮公告全文检索"),
    DataEndpoint("f10_announcements", "公告", "F10 最新公告摘要"),
]


def endpoint_names() -> List[str]:
    return [endpoint.name for endpoint in ENDPOINTS]
