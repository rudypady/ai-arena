"""
Náhrada za yfinance – používa Yahoo Finance API priamo cez requests.
Obchádza SSL problémy s curl-cffi.
"""
import requests
import json
import os
from datetime import datetime, timedelta

# Vypni SSL overenie
os.environ['PYTHONHTTPSVERIFY'] = '0'
import urllib3
urllib3.disable_warnings()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
}

SESSION = requests.Session()
SESSION.verify = False
SESSION.headers.update(HEADERS)


def _fetch_quote(ticker: str) -> dict:
    """Stiahni aktuálnu cenu z Yahoo Finance."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {'range': '2d', 'interval': '1d', 'includePrePost': False}
    try:
        r = SESSION.get(url, params=params, timeout=15)
        data = r.json()
        result = data.get('chart', {}).get('result', [])
        if not result:
            return {}
        meta = result[0].get('meta', {})
        closes = result[0].get('indicators', {}).get('quote', [{}])[0].get('close', [])
        closes = [c for c in closes if c is not None]
        return {
            'price': closes[-1] if closes else meta.get('regularMarketPrice', 0),
            'prev_close': closes[-2] if len(closes) > 1 else meta.get('chartPreviousClose', 0),
            'currency': meta.get('currency', 'USD'),
            'name': meta.get('longName', meta.get('shortName', ticker)),
            'exchange': meta.get('exchangeName', ''),
        }
    except Exception as e:
        return {}


def _fetch_history(ticker: str, period: str = '1mo') -> list:
    """Stiahni historické dáta."""
    period_map = {'1d': '1d', '5d': '5d', '1mo': '1mo', '3mo': '3mo', '1y': '1y'}
    p = period_map.get(period, '1mo')
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {'range': p, 'interval': '1d'}
    try:
        r = SESSION.get(url, params=params, timeout=15)
        data = r.json()
        result = data.get('chart', {}).get('result', [])
        if not result:
            return []
        timestamps = result[0].get('timestamp', [])
        closes = result[0].get('indicators', {}).get('quote', [{}])[0].get('close', [])
        volumes = result[0].get('indicators', {}).get('quote', [{}])[0].get('volume', [])
        rows = []
        for i, ts in enumerate(timestamps):
            c = closes[i] if i < len(closes) else None
            v = volumes[i] if i < len(volumes) else 0
            if c is not None:
                rows.append({
                    'date': datetime.fromtimestamp(ts).strftime('%Y-%m-%d'),
                    'close': round(c, 4),
                    'volume': int(v or 0),
                })
        return rows
    except Exception:
        return []


# Public API (rovnaké ako pôvodnú market_data.py)
import requests as _req
COINGECKO_BASE = "https://api.coingecko.com/api/v3"

CRYPTO_MAP = {
    'BTC-USD': 'bitcoin', 'ETH-USD': 'ethereum', 'SOL-USD': 'solana',
    'ADA-USD': 'cardano', 'BNB-USD': 'binancecoin', 'XRP-USD': 'ripple',
    'DOGE-USD': 'dogecoin', 'DOT-USD': 'polkadot', 'AVAX-USD': 'avalanche-2',
}
CRYPTO_TICKERS = set(CRYPTO_MAP.keys())


def is_crypto(ticker: str) -> bool:
    return ticker in CRYPTO_TICKERS


def get_stock_price(ticker: str) -> dict:
    q = _fetch_quote(ticker)
    if not q or not q.get('price'):
        return {'error': f'Ticker {ticker} nedostupný', 'ticker': ticker}
    price = q['price']
    prev = q.get('prev_close', price)
    change_pct = ((price - prev) / prev * 100) if prev else 0
    return {
        'ticker': ticker,
        'name': q.get('name', ticker),
        'price': round(price, 4),
        'change_pct': round(change_pct, 2),
        'currency': q.get('currency', 'USD'),
        'asset_type': 'stock',
    }


def get_crypto_price(symbol: str) -> dict:
    try:
        cid = CRYPTO_MAP.get(symbol, symbol.lower().replace('-usd', ''))
        url = f"{COINGECKO_BASE}/simple/price"
        params = {'ids': cid, 'vs_currencies': 'eur,usd', 'include_24hr_change': 'true'}
        r = SESSION.get(url, params=params, timeout=10)
        data = r.json()
        if cid not in data:
            return {'error': f'Krypto {symbol} nenájdené', 'ticker': symbol}
        cd = data[cid]
        return {
            'ticker': symbol, 'coingecko_id': cid,
            'name': cid.replace('-', ' ').title(),
            'price': cd.get('usd', 0), 'price_usd': cd.get('usd', 0),
            'price_eur': cd.get('eur', 0),
            'change_pct': cd.get('usd_24h_change', 0),
            'currency': 'USD', 'asset_type': 'crypto',
        }
    except Exception as e:
        return {'error': str(e), 'ticker': symbol}


def get_price(ticker: str) -> dict:
    if is_crypto(ticker):
        return get_crypto_price(ticker)
    return get_stock_price(ticker)


def get_stock_history(ticker: str, period: str = '1mo') -> dict:
    rows = _fetch_history(ticker, period)
    return {'ticker': ticker, 'period': period, 'data': rows}


def get_market_overview() -> dict:
    indices = {
        'S&P 500': '^GSPC', 'NASDAQ': '^IXIC', 'DOW JONES': '^DJI',
        'VIX': '^VIX', 'EUR/USD': 'EURUSD=X', 'DAX': '^GDAXI',
    }
    result = {}
    for name, ticker in indices.items():
        q = _fetch_quote(ticker)
        if q and q.get('price'):
            p = q['price']
            prev = q.get('prev_close', p)
            chg = ((p - prev) / prev * 100) if prev else 0
            result[name] = {'value': round(p, 2), 'change_pct': round(chg, 2)}
    return result


def get_top_movers() -> dict:
    watchlist = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META', 'NFLX', 'AMD', 'SPY']
    movers = []
    for ticker in watchlist:
        d = get_stock_price(ticker)
        if 'error' not in d:
            movers.append({'ticker': ticker, 'price': d.get('price', 0),
                          'change_pct': d.get('change_pct', 0), 'name': d.get('name', ticker)})
    movers.sort(key=lambda x: x.get('change_pct', 0), reverse=True)
    return {'gainers': movers[:5], 'losers': list(reversed(movers[-5:]))}


def get_usd_to_eur_rate() -> float:
    q = _fetch_quote('EURUSD=X')
    if q and q.get('price'):
        return float(q['price'])
    return 0.92
