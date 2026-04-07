import os, json, re
from backend.agents.base_agent import BaseAgent

STRATEGY = "Inovatívna rastová stratégia (Tech + Krypto)"
BUY_LIST = ['NVDA', 'MSFT', 'GOOGL', 'META', 'AMD', 'BTC-USD', 'ETH-USD', 'SOL-USD']


class GPTAgent(BaseAgent):
    def __init__(self):
        super().__init__('gpt', 'GPT-4o')
        self.api_key = os.getenv('OPENAI_API_KEY', '')

    def run_round(self, round_id: int) -> dict:
        if not self.api_key:
            return self.run_demo_round(round_id, STRATEGY, BUY_LIST, risk='high')
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model='gpt-4o',
                messages=[
                    {'role': 'system', 'content': 'Si AI investičný agent. Odpovedaj výlučne v JSON.'},
                    {'role': 'user', 'content': self._build_prompt()}
                ],
                temperature=0.7,
                max_tokens=1000,
            )
            return self._parse_and_execute(response.choices[0].message.content, round_id)
        except Exception as e:
            self.save_log(round_id, '', '', error=str(e))
            return self.run_demo_round(round_id, STRATEGY, BUY_LIST, risk='high')

    def _build_prompt(self) -> str:
        return f"""Si skúsený finančný poradca vo vrecku používateľa, ktorý investuje na platforme Revolut (kde sú poplatky nulové). Tvojou úlohou nie je hrať sa na simuláciu, ale poskytnúť presný, stručný a úderný tip na nákup alebo predaj na aktuálny deň.

{self.get_portfolio_summary()}

{self.get_market_context()}

Na základe aktuálneho vývoja (S&P 500, klesajúce a rastúce trhy), vyber z dostupných akcií alebo kryptomien tú najrozumnejšiu investíciu na krátkodobé či strednodobé držanie. 
Odpovedz VÝLUČNE v JSON formáte (žiadny iný text nezadávaj mimo JSON), kde tvoja "reasoning" časť bude znieť ako priama rada používateľovi a končiť priamym pokynom čo a prečo má nakúpiť.

Príklad formátu odpovede:
{{
  "reasoning": "Ahoj! Trh dnes kvôli správe z FEDu mierne klesá, čo je výborná príležitosť. Akcie Nvidia (NVDA) zlacneli o 3%, hoci firma hlási rekordný zisk. MÔJ TIP DO REVOLUTU: Nakúp jednoznačne NVDA, v priebehu týždňa očakávame nárast na pôvodnú hodnotu.",
  "strategy": "Osobný Revolut Advisor (GPT-4o)",
  "trades": [
    {{"action": "buy", "ticker": "NVDA", "amount_eur": 25}}
  ]
}}

Pravidlá:
- Odpovedaj priamo konkrétnemu používateľovi ako jeho asistent v slovenčine (vykaj mu, buď priateľský a rázny expert).
- Úvahu ukonči jasným príkazom: MÔJ TIP NA REVOLUT: [čo má spraviť]
- Tickery akcií ktoré môže radiť: AAPL, TSLA, NVDA, MSFT, GOOGL, META, AMD, AMZN, NFLX
- Tickery krypto: BTC-USD, ETH-USD, SOL-USD
- Z úcty k nemu mu nezabudni aj reálne tie peniaze vo virtuálnom portfóliu spravovať (max do výšky cashu, min €1)."""

    def _parse_and_execute(self, text: str, round_id: int) -> dict:
        try:
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if m:
                data = json.loads(m.group())
                trades = self.execute_trades(data.get('trades', []), round_id)
                reasoning = data.get('reasoning', text)
                self.save_log(round_id, reasoning, data.get('strategy', ''))
                return {'agent': self.agent_id, 'trades': trades, 'reasoning': reasoning, 'demo_mode': False}
        except Exception as e:
            self.save_log(round_id, text, '', error=str(e))
        return self.run_demo_round(round_id, STRATEGY, BUY_LIST, risk='medium')
