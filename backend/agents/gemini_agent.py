import os, json, re
from backend.agents.base_agent import BaseAgent

STRATEGY = "Inovatívna rastová stratégia (Tech + Krypto)"
BUY_LIST = ['NVDA', 'MSFT', 'GOOGL', 'META', 'AMD', 'BTC-USD', 'ETH-USD', 'SOL-USD']


class GeminiAgent(BaseAgent):
    def __init__(self):
        super().__init__('gemini', 'Gemini')
        self.api_key = os.getenv('GOOGLE_API_KEY', '')

    def run_round(self, round_id: int) -> dict:
        if not self.api_key:
            return self.run_demo_round(round_id, STRATEGY, BUY_LIST, risk='high')
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            prompt = self._build_prompt()
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            return self._parse_and_execute(response.text, round_id)
        except Exception as e:
            err = str(e)
            print(f"[Gemini] API chyba: {err[:200]}")
            # Pri kvóte alebo chybe použij demo mód
            self.save_log(round_id, f'[Fallback na DEMO – chyba API: {err[:100]}]', STRATEGY)
            return self.run_demo_round(round_id, STRATEGY, BUY_LIST, risk='high')

    def _build_prompt(self) -> str:
        return f"""Si AI investičný agent Gemini. Spravuješ virtuálne portfólio (simulácia, nie skutočné peniaze).
Tvoja stratégia: rast, technológie, kryptomeny, vysoké výnosy.

{self.get_portfolio_summary()}

{self.get_market_context()}

Na základe analýzy trhu rozhodni o obchodoch. Odpovedz VÝLUČNE v JSON formáte (žiadny iný text):
{{
  "reasoning": "Tvoja detailná analýza a zdôvodnenie v slovenčine (2-3 vety)",
  "strategy": "Rastová tech + krypto stratégia",
  "trades": [
    {{"action": "buy", "ticker": "NVDA", "amount_eur": 25}},
    {{"action": "sell", "ticker": "ETH-USD", "percentage": 50}}
  ]
}}

Pravidlá:
- Neprekroč dostupnú hotovosť pri nákupoch
- Minimálna transakcia: €1
- Tickery akcií: AAPL, TSLA, NVDA, MSFT, GOOGL, META, AMD, AMZN, NFLX
- Tickery krypto: BTC-USD, ETH-USD, SOL-USD
- Môžeš mať prázdny zoznam trades ak nechceš obchodovať"""

    def _parse_and_execute(self, text: str, round_id: int) -> dict:
        try:
            # Extrahuj JSON z odpovede
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if m:
                data = json.loads(m.group())
                trades = self.execute_trades(data.get('trades', []), round_id)
                reasoning = data.get('reasoning', text[:300])
                self.save_log(round_id, reasoning, data.get('strategy', STRATEGY))
                return {'agent': self.agent_id, 'trades': trades, 'reasoning': reasoning, 'demo_mode': False}
        except Exception as e:
            self.save_log(round_id, text[:300], STRATEGY, error=str(e))
        return self.run_demo_round(round_id, STRATEGY, BUY_LIST, risk='high')
