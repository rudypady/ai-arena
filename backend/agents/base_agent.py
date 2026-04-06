from datetime import datetime
from backend.database import get_agent_portfolio, get_current_cash, get_connection
from backend.market_data import get_market_overview, get_top_movers
from backend.simulation import execute_buy, execute_sell, update_all_prices


class BaseAgent:
    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name

    def get_portfolio_summary(self) -> str:
        p = get_agent_portfolio(self.agent_id)
        s = p.get('snapshot', {})
        holdings = p.get('holdings', [])
        cash = s.get('cash', 100.0)
        total = s.get('total_value', cash)
        pnl = s.get('pnl_percent', 0)

        lines = [
            f"Dátum: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Hotovosť: €{cash:.2f}",
            f"Hodnota pozícií: €{s.get('holdings_value', 0):.2f}",
            f"TOTAL: €{total:.2f} (P&L: {pnl:+.2f}%)",
            "",
            "Pozície:"
        ]
        if holdings:
            for h in holdings:
                cur = h.get('current_price') or h.get('avg_buy_price', 0)
                val = h['quantity'] * cur
                ph = ((cur - h['avg_buy_price']) / h['avg_buy_price'] * 100) if h['avg_buy_price'] else 0
                lines.append(f"  {h['ticker']} ({h.get('name','')}): €{val:.2f} | P&L: {ph:+.1f}%")
        else:
            lines.append("  Žiadne pozície")
        return "\n".join(lines)

    def get_market_context(self) -> str:
        overview = get_market_overview()
        movers = get_top_movers()
        lines = ["Prehľad trhu:"]
        for name, d in overview.items():
            lines.append(f"  {name}: {d.get('value', 'N/A')} ({d.get('change_pct', 0):+.2f}%)")
        lines.append("\nTop rastúce tituly dnes:")
        for m in movers.get('gainers', [])[:5]:
            lines.append(f"  {m['ticker']} {m.get('name','')}: {m.get('change_pct', 0):+.2f}%")
        lines.append("\nTop klesajúce tituly dnes:")
        for m in movers.get('losers', [])[:5]:
            lines.append(f"  {m['ticker']} {m.get('name','')}: {m.get('change_pct', 0):+.2f}%")
        return "\n".join(lines)

    def execute_trades(self, trades: list, round_id: int = None) -> list:
        results = []
        for trade in trades:
            action = trade.get('action', '').lower()
            ticker = trade.get('ticker', '').upper()
            if action == 'buy':
                r = execute_buy(self.agent_id, ticker, trade.get('amount_eur', 0), round_id)
            elif action == 'sell':
                r = execute_sell(self.agent_id, ticker, trade.get('percentage', 100), round_id)
            else:
                continue
            r['instruction'] = trade
            results.append(r)
        return results

    def save_log(self, round_id: int, reasoning: str, strategy: str = '', error: str = ''):
        conn = get_connection()
        conn.execute(
            'INSERT INTO agent_logs (agent_id, round_id, reasoning, strategy, error) VALUES (?, ?, ?, ?, ?)',
            (self.agent_id, round_id, reasoning, strategy, error)
        )
        conn.commit()
        conn.close()

    def run_demo_round(self, round_id: int, strategy_name: str,
                       buy_list: list, risk: str = 'medium') -> dict:
        """Demo mód – funguje bez API kľúčov s reálnymi trhovými dátami."""
        update_all_prices(self.agent_id)
        p = get_agent_portfolio(self.agent_id)
        snapshot = p.get('snapshot', {})
        holdings = p.get('holdings', [])
        cash = snapshot.get('cash', 100.0)

        trades = []
        reasoning = []

        # Kontrola stop-loss a take-profit
        for h in holdings:
            cur = h.get('current_price') or h.get('avg_buy_price', 0)
            if not h['avg_buy_price']:
                continue
            pnl = (cur - h['avg_buy_price']) / h['avg_buy_price']
            stop = {'high': -0.08, 'medium': -0.12, 'low': -0.20}[risk]
            if pnl < stop:
                trades.append({'action': 'sell', 'ticker': h['ticker'], 'percentage': 100})
                reasoning.append(f"Stop-loss: predávam {h['ticker']} (strata {pnl*100:.1f}%)")
            elif pnl > 0.30:
                trades.append({'action': 'sell', 'ticker': h['ticker'], 'percentage': 25})
                reasoning.append(f"Take-profit: čiastočný predaj {h['ticker']} (+{pnl*100:.1f}%)")

        # Nákupy
        if cash > 2:
            held = {h['ticker'] for h in holdings}
            buf = {'high': 0.95, 'medium': 0.80, 'low': 0.60}[risk]
            available = cash * buf

            # Trhový kontext
            ov = get_market_overview()
            sp_chg = ov.get('S&P 500', {}).get('change_pct', 0)
            if sp_chg < -1.5 and risk != 'high':
                available *= 0.5
                reasoning.append(f"Trh slabší (S&P {sp_chg:+.1f}%), redukujem nákupy")
            elif sp_chg > 1.0:
                reasoning.append(f"Silný trh (S&P {sp_chg:+.1f}%), investujem viac")

            to_buy = [t for t in buy_list if t not in held][:3]
            if to_buy and available > 1:
                per = available / len(to_buy)
                for ticker in to_buy:
                    amt = round(min(per, cash * 0.95), 2)
                    if amt >= 0.5:
                        trades.append({'action': 'buy', 'ticker': ticker, 'amount_eur': amt})
                        reasoning.append(f"Nakupujem {ticker} za €{amt:.2f}")

        results = self.execute_trades(trades, round_id)
        text = f"[DEMO] {strategy_name}\n" + ("\n".join(reasoning) if reasoning else "Trhy sledované, žiadne zmeny.")
        self.save_log(round_id, text, strategy_name)
        return {'agent': self.agent_id, 'trades': results, 'reasoning': text, 'demo_mode': True}

    def run_round(self, round_id: int) -> dict:
        raise NotImplementedError
