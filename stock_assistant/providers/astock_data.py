from __future__ import annotations

import json
import os
import re
import secrets
import time
import urllib.request
import uuid
from datetime import date, datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import requests

from stock_assistant.data_gateway import DAILY_COLUMNS
from stock_assistant.utils import market_prefix, normalize_symbol

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"


class AStockDataLiveProvider:
    """HTTP subset adapted from the installed a-stock-data skill.

    The provider intentionally starts with keyless, stable endpoints:
    Tencent quote, Baidu daily K-line, Eastmoney stock info, Eastmoney sectors,
    and Eastmoney fund flow.
    """

    def tick_trades(self, symbol: str, trade_date: str | None = None) -> pd.DataFrame:
        code = normalize_symbol(symbol)
        client = self._mootdx_client()
        kwargs: Dict[str, Any] = {"symbol": code}
        if trade_date:
            kwargs["date"] = trade_date.replace("-", "")
        return client.transaction(**kwargs)

    def order_book(self, symbol: str) -> Dict[str, Any]:
        quote = self.quote(symbol)
        return {
            "symbol": normalize_symbol(symbol),
            "bid": [{"price": quote.get(f"bid{i}", 0), "volume": quote.get(f"bid_vol{i}", 0)} for i in range(1, 6)],
            "ask": [{"price": quote.get(f"ask{i}", 0), "volume": quote.get(f"ask_vol{i}", 0)} for i in range(1, 6)],
            "source": "a-stock-data:tencent",
        }

    def quote(self, symbol: str) -> Dict[str, Any]:
        code = normalize_symbol(symbol)
        prefixed = f"{market_prefix(code)}{code}"
        req = urllib.request.Request(f"https://qt.gtimg.cn/q={prefixed}", headers={"User-Agent": UA})
        data = urllib.request.urlopen(req, timeout=10).read().decode("gbk")
        vals = data.split('"')[1].split("~") if '"' in data else []
        if len(vals) < 53:
            raise RuntimeError(f"Tencent quote returned unexpected payload for {code}")
        return {
            "symbol": code,
            "name": vals[1],
            "price": self._num(vals[3]),
            "pct_chg": self._num(vals[32]),
            "open": self._num(vals[5]),
            "high": self._num(vals[33]),
            "low": self._num(vals[34]),
            "pre_close": self._num(vals[4]),
            "volume": int(self._num(vals[6]) * 100),
            "amount": self._num(vals[37]) * 10000,
            "turnover_rate": self._num(vals[38]),
            "pe_ttm": self._none_if_zero(self._num(vals[39])),
            "pb": self._none_if_zero(self._num(vals[46])),
            "market_cap": self._none_if_zero(self._num(vals[44]) * 100000000),
            "float_market_cap": self._none_if_zero(self._num(vals[45]) * 100000000),
            "limit_up": self._num(vals[47]),
            "limit_down": self._num(vals[48]),
            "vol_ratio": self._num(vals[49]),
            "pe_static": self._num(vals[52]),
            "bid1": self._num(vals[9]),
            "bid_vol1": self._num(vals[10]),
            "bid2": self._num(vals[11]),
            "bid_vol2": self._num(vals[12]),
            "bid3": self._num(vals[13]),
            "bid_vol3": self._num(vals[14]),
            "bid4": self._num(vals[15]),
            "bid_vol4": self._num(vals[16]),
            "bid5": self._num(vals[17]),
            "bid_vol5": self._num(vals[18]),
            "ask1": self._num(vals[19]),
            "ask_vol1": self._num(vals[20]),
            "ask2": self._num(vals[21]),
            "ask_vol2": self._num(vals[22]),
            "ask3": self._num(vals[23]),
            "ask_vol3": self._num(vals[24]),
            "ask4": self._num(vals[25]),
            "ask_vol4": self._num(vals[26]),
            "ask5": self._num(vals[27]),
            "ask_vol5": self._num(vals[28]),
            "source": "a-stock-data:tencent",
            "missing_data": [],
        }

    def index_quotes(self) -> List[Dict[str, Any]]:
        codes = ["sh000001", "sz399001", "sz399006", "sh000688", "bj899050"]
        req = urllib.request.Request("https://qt.gtimg.cn/q=" + ",".join(codes), headers={"User-Agent": UA})
        data = urllib.request.urlopen(req, timeout=10).read().decode("gbk")
        rows = []
        for line in data.strip().split(";"):
            if not line.strip() or '"' not in line:
                continue
            key = line.split("=")[0].split("_")[-1]
            vals = line.split('"')[1].split("~")
            if len(vals) < 45:
                continue
            rows.append(
                {
                    "code": key,
                    "name": vals[1],
                    "price": self._num(vals[3]),
                    "change": self._num(vals[31]),
                    "pct_chg": self._num(vals[32]),
                    "high": self._num(vals[33]),
                    "low": self._num(vals[34]),
                    "amount": self._num(vals[37]) * 10000,
                    "turnover": self._num(vals[38]),
                    "source": "a-stock-data:tencent",
                }
            )
        return rows

    def stock_basic(self, symbol: str) -> Dict[str, Any]:
        code = normalize_symbol(symbol)
        market_code = 1 if code.startswith(("6", "9")) else 0
        url = "https://push2.eastmoney.com/api/qt/stock/get"
        params = {
            "fltt": "2",
            "invt": "2",
            "fields": "f57,f58,f84,f85,f127,f116,f117,f189,f43",
            "secid": f"{market_code}.{code}",
        }
        try:
            data = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=10).json().get("data") or {}
        except Exception:
            data = {}
        concepts = []
        try:
            concepts = self.concept_blocks(code).get("concept_tags", [])
        except Exception:
            concepts = []
        if not data:
            quote = self.quote(code)
            return {
                "symbol": code,
                "name": quote.get("name") or code,
                "industry": "未知行业",
                "concepts": concepts,
                "market": "沪市" if market_code == 1 else "深市",
                "list_date": "",
                "source": "a-stock-data:tencent-fallback",
                "missing_data": [{"field": "eastmoney_stock_info", "reason": "Eastmoney stock info unavailable"}],
            }
        return {
            "symbol": code,
            "name": data.get("f58") or code,
            "industry": data.get("f127") or "未知行业",
            "concepts": concepts,
            "market": "沪市" if market_code == 1 else "深市",
            "list_date": str(data.get("f189") or ""),
            "source": "a-stock-data:eastmoney+baidu",
            "missing_data": [],
        }

    def concept_blocks(self, symbol: str) -> Dict[str, List[Dict[str, Any]] | List[str]]:
        code = normalize_symbol(symbol)
        url = (
            "https://finance.pae.baidu.com/api/getrelatedblock"
            f"?code={code}&market=ab&typeCode=all&finClientType=pc"
        )
        headers = {
            "Host": "finance.pae.baidu.com",
            "User-Agent": UA,
            "Accept": "application/vnd.finance-web.v1+json",
            "Origin": "https://gushitong.baidu.com",
            "Referer": "https://gushitong.baidu.com/",
        }
        payload = requests.get(url, headers=headers, timeout=10).json()
        if str(payload.get("ResultCode", -1)) != "0":
            raise RuntimeError(f"Baidu concept blocks failed for {code}: {payload}")
        result: Dict[str, List[Dict[str, Any]] | List[str]] = {
            "industry": [],
            "concept": [],
            "region": [],
            "concept_tags": [],
        }
        for block in payload.get("Result", []):
            block_type = block.get("type", "")
            for item in block.get("list", []):
                entry = {"name": item.get("name", ""), "change_pct": item.get("increase", ""), "desc": item.get("desc", "")}
                if "行业" in block_type:
                    result["industry"].append(entry)
                elif "概念" in block_type:
                    result["concept"].append(entry)
                    result["concept_tags"].append(entry["name"])
                elif "地域" in block_type:
                    result["region"].append(entry)
        return result

    def daily_bars(self, symbol: str) -> pd.DataFrame:
        code = normalize_symbol(symbol)
        url = "https://finance.pae.baidu.com/selfselect/getstockquotation"
        params = {
            "all": "1",
            "isIndex": "false",
            "isBk": "false",
            "isBlock": "false",
            "isFutures": "false",
            "isStock": "true",
            "newFormat": "1",
            "group": "quotation_kline_ab",
            "finClientType": "pc",
            "code": code,
            "ktype": "1",
        }
        headers = {
            "User-Agent": UA,
            "Accept": "application/vnd.finance-web.v1+json",
            "Origin": "https://gushitong.baidu.com",
            "Referer": "https://gushitong.baidu.com/",
        }
        payload = requests.get(url, params=params, headers=headers, timeout=10).json()
        market_data = (payload.get("Result") or {}).get("newMarketData") or {}
        keys = market_data.get("keys") or []
        rows = [row for row in (market_data.get("marketData") or "").split(";") if row]
        if not keys or not rows:
            raise RuntimeError(f"Baidu K-line empty for {code}")
        parsed: List[Dict[str, Any]] = []
        previous_close = None
        for raw in rows[-120:]:
            values = raw.split(",")
            item = dict(zip(keys, values))
            close = self._num(item.get("close"))
            pct_chg = 0.0 if not previous_close else round((close - previous_close) / previous_close * 100, 2)
            previous_close = close
            parsed.append(
                {
                    "date": str(item.get("time", "")),
                    "open": self._num(item.get("open")),
                    "high": self._num(item.get("high")),
                    "low": self._num(item.get("low")),
                    "close": close,
                    "volume": self._num(item.get("volume")),
                    "amount": self._num(item.get("amount")),
                    "turnover_rate": self._num(item.get("turnoverratio") or item.get("turnover_rate")),
                    "pct_chg": pct_chg,
                }
            )
        return pd.DataFrame(parsed, columns=DAILY_COLUMNS)

    def baidu_kline(self, symbol: str) -> Dict[str, Any]:
        code = normalize_symbol(symbol)
        url = "https://finance.pae.baidu.com/selfselect/getstockquotation"
        params = {
            "all": "1",
            "isIndex": "false",
            "isBk": "false",
            "isBlock": "false",
            "isFutures": "false",
            "isStock": "true",
            "newFormat": "1",
            "group": "quotation_kline_ab",
            "finClientType": "pc",
            "code": code,
            "ktype": "1",
        }
        headers = {
            "User-Agent": UA,
            "Accept": "application/vnd.finance-web.v1+json",
            "Origin": "https://gushitong.baidu.com",
            "Referer": "https://gushitong.baidu.com/",
        }
        payload = requests.get(url, params=params, headers=headers, timeout=10).json()
        market_data = (payload.get("Result") or {}).get("newMarketData") or {}
        rows = [row for row in (market_data.get("marketData") or "").split(";") if row]
        if not market_data.get("keys") or not rows:
            raise RuntimeError(f"Baidu K-line empty for {code}")
        return {
            "keys": market_data.get("keys") or [],
            "rows": rows,
            "source": "a-stock-data:baidu",
        }

    def index_bars(self, symbol: str = "000001", start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
        code = normalize_symbol(symbol)
        secid = f"1.{code}" if code.startswith(("0", "5")) else f"0.{code}"
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "secid": secid,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": "101",
            "fqt": "0",
            "beg": start_date or self._date_str(days_ago=365),
            "end": end_date or self._date_str(),
        }
        try:
            rows = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=15).json().get("data", {}).get("klines", [])
        except Exception:
            rows = []
        parsed = []
        for line in rows:
            parts = line.split(",")
            if len(parts) >= 9:
                parsed.append(
                    {
                        "date": parts[0],
                        "open": self._num(parts[1]),
                        "close": self._num(parts[2]),
                        "high": self._num(parts[3]),
                        "low": self._num(parts[4]),
                        "volume": self._num(parts[5]),
                        "amount": self._num(parts[6]),
                        "turnover_rate": self._num(parts[7]),
                        "pct_chg": self._num(parts[8]),
                    }
                )
        if parsed:
            return pd.DataFrame(parsed, columns=DAILY_COLUMNS)
        mootdx_bars = self._mootdx_client().bars(symbol=code, category=4, offset=120)
        if mootdx_bars is None or mootdx_bars.empty:
            return pd.DataFrame(columns=DAILY_COLUMNS)
        df = mootdx_bars.rename(columns={"vol": "volume"})
        df["date"] = df.get("datetime", "").astype(str).str[:10] if "datetime" in df else ""
        if "pct_chg" not in df:
            df["pct_chg"] = df["close"].pct_change().fillna(0) * 100
        for column in DAILY_COLUMNS:
            if column not in df:
                df[column] = 0
        return df[DAILY_COLUMNS]

    def research_reports(self, symbol: str, max_pages: int = 2) -> List[Dict[str, Any]]:
        code = normalize_symbol(symbol)
        session = requests.Session()
        session.headers.update({"User-Agent": UA, "Referer": "https://data.eastmoney.com/"})
        rows: List[Dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            params = {
                "industryCode": "*",
                "pageSize": "100",
                "industry": "*",
                "rating": "*",
                "ratingChange": "*",
                "beginTime": "2000-01-01",
                "endTime": "2030-01-01",
                "pageNo": str(page),
                "fields": "",
                "qType": "0",
                "orgCode": "",
                "code": code,
                "rcode": "",
                "p": str(page),
                "pageNum": str(page),
                "pageNumber": str(page),
            }
            payload = session.get("https://reportapi.eastmoney.com/report/list", params=params, timeout=30).json()
            data = payload.get("data") or []
            if not data:
                break
            rows.extend(data)
            if page >= (payload.get("TotalPage", 1) or 1):
                break
            time.sleep(0.2)
        return rows

    def research_pdf(self, symbol: str, info_code: str | None = None) -> Dict[str, Any]:
        if not info_code:
            reports = self.research_reports(symbol, max_pages=1)
            if not reports:
                return {"downloaded": False, "path": "", "message": "no research report found"}
            info_code = reports[0].get("infoCode")
        if not info_code:
            return {"downloaded": False, "path": "", "message": "missing infoCode"}
        url = f"https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"
        response = requests.get(url, headers={"User-Agent": UA, "Referer": "https://data.eastmoney.com/"}, timeout=60)
        if response.status_code != 200 or len(response.content) < 1024:
            return {"downloaded": False, "path": "", "message": f"pdf unavailable HTTP {response.status_code}"}
        target_dir = Path(os.environ.get("STOCK_ASSISTANT_REPORT_DIR", ".cache/reports"))
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{normalize_symbol(symbol)}_{info_code}.pdf"
        target.write_bytes(response.content)
        return {"downloaded": True, "path": str(target), "url": url}

    def consensus_eps(self, symbol: str) -> pd.DataFrame:
        code = normalize_symbol(symbol)
        response = requests.get(
            f"https://basic.10jqka.com.cn/new/{code}/worth.html",
            headers={"User-Agent": UA, "Referer": "https://basic.10jqka.com.cn/"},
            timeout=15,
        )
        response.encoding = "gbk"
        tables = pd.read_html(StringIO(response.text))
        for table in tables:
            columns = [str(column) for column in table.columns]
            if any("每股收益" in column or "均值" in column for column in columns):
                return table
        return tables[0] if tables else pd.DataFrame()

    def iwencai_report_search(self, query: str, channel: str = "report", size: int = 50) -> List[Dict[str, Any]]:
        api_key = os.environ.get("IWENCAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("IWENCAI_API_KEY is not configured")
        base_url = os.environ.get("IWENCAI_BASE_URL", "https://openapi.iwencai.com")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Claw-Call-Type": "normal",
            "X-Claw-Skill-Id": "report-search",
            "X-Claw-Skill-Version": "2.0.0",
            "X-Claw-Plugin-Id": "none",
            "X-Claw-Plugin-Version": "none",
            "X-Claw-Trace-Id": secrets.token_hex(32),
        }
        payload = {"channels": [channel], "app_id": "AIME_SKILL", "query": query, "size": size}
        response = requests.post(f"{base_url}/v1/comprehensive/search", json=payload, headers=headers, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"iwencai HTTP {response.status_code}: {response.text[:200]}")
        data = response.json()
        if data.get("status_code", 0) != 0:
            raise RuntimeError(f"iwencai error: {data.get('status_msg', '')}")
        return data.get("data") or []

    def hot_stocks(self, trade_date: str | None = None) -> pd.DataFrame:
        day = trade_date or date.today().strftime("%Y-%m-%d")
        url = f"http://zx.10jqka.com.cn/event/api/getharden/date/{day}/orderby/date/orderway/desc/charset/GBK/"
        payload = requests.get(url, headers={"User-Agent": UA}, timeout=10).json()
        if payload.get("errocode", 0) != 0:
            raise RuntimeError(f"ths hot stocks failed: {payload.get('errormsg', '')}")
        return pd.DataFrame(payload.get("data") or [])

    def northbound_flow(self) -> pd.DataFrame:
        url = "https://data.hexin.cn/market/hsgtApi/method/dayChart/"
        headers = {"User-Agent": UA, "Host": "data.hexin.cn", "Referer": "https://data.hexin.cn/"}
        payload = requests.get(url, headers=headers, timeout=10).json()
        times = payload.get("time", [])
        hgt = payload.get("hgt", [])
        sgt = payload.get("sgt", [])
        n = len(times)
        return pd.DataFrame({"time": times, "hgt_yi": hgt[:n] + [None] * (n - len(hgt)), "sgt_yi": sgt[:n] + [None] * (n - len(sgt))})

    def capital_flow_minute(self, symbol: str) -> List[Dict[str, Any]]:
        code = normalize_symbol(symbol)
        market_code = 1 if code.startswith(("6", "9")) else 0
        url = "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get"
        params = {"secid": f"{market_code}.{code}", "klt": 1, "fields1": "f1,f2,f3,f7", "fields2": "f51,f52,f53,f54,f55,f56,f57"}
        klines = requests.get(url, params=params, headers={"User-Agent": UA, "Referer": "https://quote.eastmoney.com/", "Origin": "https://quote.eastmoney.com"}, timeout=10).json().get("data", {}).get("klines", [])
        rows = []
        for line in klines:
            parts = line.split(",")
            if len(parts) >= 6:
                rows.append({"time": parts[0], "main_net": self._num(parts[1]), "small_net": self._num(parts[2]), "mid_net": self._num(parts[3]), "large_net": self._num(parts[4]), "super_net": self._num(parts[5])})
        return rows

    def dragon_tiger(self, symbol: str, trade_date: str | None = None, look_back: int = 30) -> Dict[str, Any]:
        code = normalize_symbol(symbol)
        end = trade_date or date.today().strftime("%Y-%m-%d")
        start = (datetime.strptime(end, "%Y-%m-%d") - timedelta(days=look_back)).strftime("%Y-%m-%d")
        data = self._eastmoney_datacenter(
            "RPT_DAILYBILLBOARD_DETAILSNEW",
            filter_str=f"(TRADE_DATE>='{start}')(TRADE_DATE<='{end}')(SECURITY_CODE=\"{code}\")",
            page_size=50,
            sort_columns="TRADE_DATE",
            sort_types="-1",
        )
        records = [
            {
                "date": str(row.get("TRADE_DATE", ""))[:10],
                "reason": row.get("EXPLANATION", ""),
                "net_buy": round((row.get("BILLBOARD_NET_AMT") or 0) / 10000, 1),
                "turnover": round(float(row.get("TURNOVERRATE") or 0), 2),
            }
            for row in data
        ]
        buy_data: List[Dict[str, Any]] = []
        sell_data: List[Dict[str, Any]] = []
        seats = {"buy": [], "sell": []}
        if records:
            latest_date = records[0]["date"]
            buy_data = self._eastmoney_datacenter("RPT_BILLBOARD_DAILYDETAILSBUY", filter_str=f"(TRADE_DATE='{latest_date}')(SECURITY_CODE=\"{code}\")", page_size=10, sort_columns="BUY", sort_types="-1")
            sell_data = self._eastmoney_datacenter("RPT_BILLBOARD_DAILYDETAILSSELL", filter_str=f"(TRADE_DATE='{latest_date}')(SECURITY_CODE=\"{code}\")", page_size=10, sort_columns="SELL", sort_types="-1")
            seats["buy"] = [self._seat(row) for row in buy_data[:5]]
            seats["sell"] = [self._seat(row) for row in sell_data[:5]]
        institution = {"buy_amt": 0.0, "sell_amt": 0.0, "net_amt": 0.0}
        for row in buy_data:
            if str(row.get("OPERATEDEPT_CODE", "")) == "0":
                institution["buy_amt"] += row.get("BUY") or 0
        for row in sell_data:
            if str(row.get("OPERATEDEPT_CODE", "")) == "0":
                institution["sell_amt"] += row.get("SELL") or 0
        institution["buy_amt"] = round(institution["buy_amt"] / 10000, 1)
        institution["sell_amt"] = round(institution["sell_amt"] / 10000, 1)
        institution["net_amt"] = round(institution["buy_amt"] - institution["sell_amt"], 1)
        return {"records": records, "seats": seats, "institution": institution}

    def market_dragon_tiger(self, trade_date: str | None = None, min_net_buy: float | None = None) -> Dict[str, Any]:
        day = trade_date or date.today().strftime("%Y-%m-%d")
        data = self._eastmoney_datacenter(
            "RPT_DAILYBILLBOARD_DETAILSNEW",
            filter_str=f"(TRADE_DATE>='{day}')(TRADE_DATE<='{day}')",
            page_size=500,
            sort_columns="BILLBOARD_NET_AMT",
            sort_types="-1",
        )
        stocks = []
        for row in data:
            net_buy = (row.get("BILLBOARD_NET_AMT") or 0) / 10000
            if min_net_buy is not None and net_buy < min_net_buy:
                continue
            stocks.append(
                {
                    "code": row.get("SECURITY_CODE", ""),
                    "name": row.get("SECURITY_NAME_ABBR", ""),
                    "reason": row.get("EXPLANATION", ""),
                    "close": row.get("CLOSE_PRICE") or 0,
                    "change_pct": round(float(row.get("CHANGE_RATE") or 0), 2),
                    "net_buy_wan": round(net_buy, 1),
                    "buy_wan": round((row.get("BILLBOARD_BUY_AMT") or 0) / 10000, 1),
                    "sell_wan": round((row.get("BILLBOARD_SELL_AMT") or 0) / 10000, 1),
                    "turnover_pct": round(float(row.get("TURNOVERRATE") or 0), 2),
                }
            )
        actual_date = str(data[0].get("TRADE_DATE", ""))[:10] if data else day
        return {"date": actual_date, "total_records": len(stocks), "stocks": stocks}

    def lockup_calendar(self, symbol: str, trade_date: str | None = None, forward_days: int = 90) -> Dict[str, Any]:
        code = normalize_symbol(symbol)
        day = trade_date or date.today().strftime("%Y-%m-%d")
        history_data = self._eastmoney_datacenter("RPT_LIFT_STAGE", filter_str=f"(SECURITY_CODE=\"{code}\")", page_size=15, sort_columns="FREE_DATE", sort_types="-1")
        end = (datetime.strptime(day, "%Y-%m-%d") + timedelta(days=forward_days)).strftime("%Y-%m-%d")
        upcoming_data = self._eastmoney_datacenter("RPT_LIFT_STAGE", filter_str=f"(SECURITY_CODE=\"{code}\")(FREE_DATE>='{day}')(FREE_DATE<='{end}')", page_size=20, sort_columns="FREE_DATE", sort_types="1")
        return {
            "history": [{"date": str(row.get("FREE_DATE", ""))[:10], "type": row.get("LIMITED_STOCK_TYPE", ""), "shares": row.get("FREE_SHARES_NUM", 0), "ratio": row.get("FREE_RATIO", 0)} for row in history_data],
            "upcoming": [{"date": str(row.get("FREE_DATE", ""))[:10], "type": row.get("LIMITED_STOCK_TYPE", ""), "shares": row.get("FREE_SHARES_NUM", 0), "ratio": row.get("FREE_RATIO", 0)} for row in upcoming_data],
        }

    def sector_performance(self) -> pd.DataFrame:
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1",
            "pz": "100",
            "po": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "fs": "m:90+t:2",
            "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207",
        }
        items = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=15).json().get("data", {}).get("diff", [])
        rows = [
            {
                "sector": item.get("f14", ""),
                "pct_chg": self._num(item.get("f3")),
                "amount": 0,
                "strength": "强于大盘" if self._num(item.get("f3")) > 0 else "弱于大盘",
            }
            for item in items
        ]
        return pd.DataFrame(rows)

    def capital_flow(self, symbol: str) -> pd.DataFrame:
        code = normalize_symbol(symbol)
        market_code = 1 if code.startswith(("6", "9")) else 0
        url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
        params = {
            "secid": f"{market_code}.{code}",
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
            "lmt": "120",
        }
        headers = {"User-Agent": UA, "Referer": "https://quote.eastmoney.com/", "Origin": "https://quote.eastmoney.com"}
        klines = requests.get(url, params=params, headers=headers, timeout=15).json().get("data", {}).get("klines", [])
        rows = []
        for line in klines:
            parts = line.split(",")
            if len(parts) >= 6:
                rows.append(
                    {
                        "symbol": code,
                        "date": parts[0],
                        "main_net_inflow": self._num(parts[1]),
                        "small_net_inflow": self._num(parts[2]),
                        "medium_net_inflow": self._num(parts[3]),
                        "large_net_inflow": self._num(parts[4]),
                        "super_large_net_inflow": self._num(parts[5]),
                        "net_inflow_pct": 0,
                    }
                )
        return pd.DataFrame(rows)

    def margin_trading(self, symbol: str, page_size: int = 30) -> List[Dict[str, Any]]:
        code = normalize_symbol(symbol)
        data = self._eastmoney_datacenter(
            "RPTA_WEB_RZRQ_GGMX",
            filter_str=f'(SCODE="{code}")',
            page_size=page_size,
            sort_columns="DATE",
            sort_types="-1",
        )
        return [
            {
                "date": str(row.get("DATE", ""))[:10],
                "rzye": row.get("RZYE", 0),
                "rzmre": row.get("RZMRE", 0),
                "rzche": row.get("RZCHE", 0),
                "rqye": row.get("RQYE", 0),
                "rqmcl": row.get("RQMCL", 0),
                "rqchl": row.get("RQCHL", 0),
                "rzrqye": row.get("RZRQYE", 0),
            }
            for row in data
        ]

    def block_trades(self, symbol: str, page_size: int = 20) -> List[Dict[str, Any]]:
        code = normalize_symbol(symbol)
        data = self._eastmoney_datacenter(
            "RPT_DATA_BLOCKTRADE",
            filter_str=f'(SECURITY_CODE="{code}")',
            page_size=page_size,
            sort_columns="TRADE_DATE",
            sort_types="-1",
        )
        rows = []
        for row in data:
            close = row.get("CLOSE_PRICE") or 0
            deal_price = row.get("DEAL_PRICE") or 0
            premium = ((deal_price / close - 1) * 100) if close else 0
            rows.append(
                {
                    "date": str(row.get("TRADE_DATE", ""))[:10],
                    "price": deal_price,
                    "close": close,
                    "premium_pct": round(premium, 2),
                    "vol": row.get("DEAL_VOLUME", 0),
                    "amount": row.get("DEAL_AMT", 0),
                    "buyer": row.get("BUYER_NAME", ""),
                    "seller": row.get("SELLER_NAME", ""),
                }
            )
        return rows

    def shareholder_count(self, symbol: str, page_size: int = 10) -> List[Dict[str, Any]]:
        code = normalize_symbol(symbol)
        data = self._eastmoney_datacenter(
            "RPT_HOLDERNUMLATEST",
            filter_str=f'(SECURITY_CODE="{code}")',
            page_size=page_size,
            sort_columns="END_DATE",
            sort_types="-1",
        )
        return [
            {
                "date": str(row.get("END_DATE", ""))[:10],
                "holder_num": row.get("HOLDER_NUM", 0),
                "change_num": row.get("HOLDER_NUM_CHANGE", 0),
                "change_ratio": row.get("HOLDER_NUM_RATIO", 0),
                "avg_shares": row.get("AVG_FREE_SHARES", 0),
            }
            for row in data
        ]

    def dividend_history(self, symbol: str, page_size: int = 20) -> List[Dict[str, Any]]:
        code = normalize_symbol(symbol)
        data = self._eastmoney_datacenter(
            "RPT_SHAREBONUS_DET",
            filter_str=f'(SECURITY_CODE="{code}")',
            page_size=page_size,
            sort_columns="EX_DIVIDEND_DATE",
            sort_types="-1",
        )
        return [
            {
                "date": str(row.get("EX_DIVIDEND_DATE", ""))[:10],
                "bonus_rmb": row.get("PRETAX_BONUS_RMB", 0),
                "transfer_ratio": row.get("TRANSFER_RATIO", 0),
                "bonus_ratio": row.get("BONUS_RATIO", 0),
                "plan": row.get("ASSIGN_PROGRESS", ""),
            }
            for row in data
        ]

    def stock_news(self, symbol: str, page_size: int = 20) -> List[Dict[str, Any]]:
        code = normalize_symbol(symbol)
        callback = "jQuery_news"
        url = "https://search-api-web.eastmoney.com/search/jsonp"
        inner_params = json.dumps(
            {
                "uid": "",
                "keyword": code,
                "type": ["cmsArticleWebOld"],
                "client": "web",
                "clientType": "web",
                "clientVersion": "curr",
                "param": {
                    "cmsArticleWebOld": {
                        "searchScope": "default",
                        "sort": "default",
                        "pageIndex": 1,
                        "pageSize": page_size,
                        "preTag": "",
                        "postTag": "",
                    }
                },
            },
            separators=(",", ":"),
            ensure_ascii=False,
        )
        response = requests.get(
            url,
            params={"cb": callback, "param": inner_params},
            headers={"User-Agent": UA, "Referer": "https://so.eastmoney.com/"},
            timeout=15,
        )
        text = response.text
        payload = json.loads(text[text.index("(") + 1 : text.rindex(")")])
        cms_articles = payload.get("result", {}).get("cmsArticleWebOld", [])
        articles = cms_articles.get("list", []) if isinstance(cms_articles, dict) else cms_articles
        rows = []
        for article in articles:
            rows.append(
                {
                    "symbol": code,
                    "title": self._strip_html(article.get("title", "")),
                    "publish_time": article.get("date", ""),
                    "source": article.get("mediaName", ""),
                    "url": article.get("url", ""),
                    "summary": self._strip_html(article.get("content", ""))[:200],
                    "raw_text": self._strip_html(article.get("content", "")),
                }
            )
        return rows

    def cls_news(self, page_size: int = 50) -> List[Dict[str, Any]]:
        url = "https://www.cls.cn/nodeapi/telegraphList"
        payload = requests.get(url, params={"rn": str(page_size), "page": "1"}, headers={"User-Agent": UA, "Referer": "https://www.cls.cn/"}, timeout=10).json()
        return [
            {
                "title": item.get("title", "") or item.get("brief", ""),
                "content": item.get("content", "") or item.get("brief", ""),
                "time": item.get("ctime", ""),
                "source": "cls",
            }
            for item in payload.get("data", {}).get("roll_data", [])
        ]

    def global_news(self, page_size: int = 50) -> List[Dict[str, Any]]:
        url = "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
        params = {"client": "web", "biz": "web_724", "fastColumn": "102", "sortEnd": "", "pageSize": str(page_size), "req_trace": str(uuid.uuid4())}
        payload = requests.get(url, params=params, headers={"User-Agent": UA, "Referer": "https://kuaixun.eastmoney.com/"}, timeout=10).json()
        return [
            {
                "title": item.get("title", ""),
                "summary": (item.get("summary", "") or "")[:200],
                "time": item.get("showTime", ""),
                "source": "eastmoney_global",
            }
            for item in payload.get("data", {}).get("fastNewsList", [])
        ]

    def announcements(self, symbol: str, page_size: int = 30) -> List[Dict[str, Any]]:
        code = normalize_symbol(symbol)
        if code.startswith("6"):
            org_id = f"gssh0{code}"
        elif code.startswith(("8", "4")):
            org_id = f"gsbj0{code}"
        else:
            org_id = f"gssz0{code}"
        payload = {
            "stock": f"{code},{org_id}",
            "tabName": "fulltext",
            "pageSize": str(page_size),
            "pageNum": "1",
            "column": "",
            "category": "",
            "plate": "",
            "seDate": "",
            "searchkey": "",
            "secid": "",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
        headers = {
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://www.cninfo.com.cn/new/disclosure",
            "Origin": "https://www.cninfo.com.cn",
        }
        data = requests.post("https://www.cninfo.com.cn/new/hisAnnouncement/query", data=payload, headers=headers, timeout=15).json()
        rows = []
        for item in data.get("announcements", []) or []:
            rows.append(
                {
                    "symbol": code,
                    "title": self._strip_html(item.get("announcementTitle", "")),
                    "publish_time": self._format_timestamp(item.get("announcementTime", "")),
                    "url": f"https://www.cninfo.com.cn/new/disclosure/detail?annoId={item.get('announcementId', '')}",
                    "announcement_type": item.get("announcementTypeName", ""),
                    "raw_text": "",
                    "source": "cninfo",
                }
            )
        return rows

    def financial_report(self, symbol: str, report_type: str = "lrb") -> List[Dict[str, Any]]:
        code = normalize_symbol(symbol)
        prefix = "sh" if code.startswith(("6", "9")) else "sz"
        url = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"
        params = {"paperCode": f"{prefix}{code}", "source": report_type, "type": "0", "page": "1", "num": "20"}
        data = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=15).json()
        rows = data.get("result", {}).get("data", {}).get(report_type, [])
        return rows if isinstance(rows, list) else []

    def financial_snapshot(self, symbol: str) -> Dict[str, Any]:
        rows = self.financial_report(symbol, "lrb")
        if not rows:
            raise RuntimeError(f"Sina financial report empty for {symbol}")
        latest = rows[0]
        return {
            "report_date": latest.get("报告日") or latest.get("report_date", ""),
            "revenue": self._num(latest.get("营业总收入") or latest.get("营业收入")),
            "revenue_yoy": self._num(latest.get("营业总收入同比增长") or latest.get("营业收入同比增长")),
            "net_profit": self._num(latest.get("净利润") or latest.get("归属于母公司所有者的净利润")),
            "net_profit_yoy": self._num(latest.get("净利润同比增长") or latest.get("归母净利润同比增长")),
            "gross_margin": 0,
            "net_margin": 0,
            "roe": 0,
            "debt_ratio": 0,
            "operating_cashflow": 0,
            "free_cashflow": 0,
            "eps": self._num(latest.get("基本每股收益")),
            "bps": 0,
            "source": "a-stock-data:sina",
            "missing_data": [],
        }

    def f10_profile(self, symbol: str, category: str = "公司概况") -> Dict[str, Any]:
        code = normalize_symbol(symbol)
        client = self._mootdx_client()
        text = client.F10(symbol=code, name=category)
        return {"symbol": code, "category": category, "text": text or "", "source": "a-stock-data:mootdx"}

    def f10_announcements(self, symbol: str) -> Dict[str, Any]:
        return self.f10_profile(symbol, category="最新提示")

    def _num(self, value: Any) -> float:
        try:
            if value in ("", "-", None):
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _none_if_zero(self, value: float) -> float | None:
        return None if value == 0 else value

    def _strip_html(self, value: str) -> str:
        return re.sub(r"<[^>]+>", "", value or "").strip()

    def _format_timestamp(self, value: Any) -> str:
        if isinstance(value, (int, float)) and value > 1000000000:
            return datetime.fromtimestamp(value / 1000).strftime("%Y-%m-%d")
        return str(value or "")

    def _eastmoney_datacenter(
        self,
        report_name: str,
        columns: str = "ALL",
        filter_str: str = "",
        page_size: int = 50,
        sort_columns: str = "",
        sort_types: str = "-1",
    ) -> List[Dict[str, Any]]:
        params = {
            "reportName": report_name,
            "columns": columns,
            "filter": filter_str,
            "pageNumber": "1",
            "pageSize": str(page_size),
            "sortColumns": sort_columns,
            "sortTypes": sort_types,
            "source": "WEB",
            "client": "WEB",
        }
        payload = requests.get(DATACENTER_URL, params=params, headers={"User-Agent": UA}, timeout=15).json()
        result = payload.get("result") or {}
        data = result.get("data") or []
        return data if isinstance(data, list) else []

    def _seat(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "name": row.get("OPERATEDEPT_NAME", ""),
            "buy_amt": round((row.get("BUY") or 0) / 10000, 1),
            "sell_amt": round((row.get("SELL") or 0) / 10000, 1),
            "net": round((row.get("NET") or 0) / 10000, 1),
        }

    def _mootdx_client(self) -> Any:
        try:
            from mootdx.quotes import Quotes
        except ImportError as exc:
            raise RuntimeError("mootdx is not installed") from exc
        return Quotes.factory(market="std")

    def _date_str(self, days_ago: int = 0) -> str:
        return (date.today() - timedelta(days=days_ago)).strftime("%Y%m%d")
