import os, json, re
from backend.agents.base_agent import BaseAgent

STRATEGY = "Momentum a trendová stratégia"
BUY_LIST = ['TSLA', 'NVDA', 'AMD', 'NFLX', 'UBER', 'BTC-USD', 'ETH-USD', 'SOL-USD']


class PerplexityAgent(BaseAgent):
    def __init__(self):
        super().__init__('perplexity', 'Perplexity')
        self.api_key = os.getenv('PERPLEXITY_API_KEY', '')

    def run_round(self, round_id: int) -> dict:
        if not self.api_key:
            return self.run_demo_round(round_id, STRATEGY, BUY_LIST, risk='high')
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, base_url='https://api.perplexity.ai')
            response = client.chat.completions.create(
                model='llama-3.1-sonar-large-128k-online',
                messages=[
                    {'role': 'system', 'content': 'Si AI investičný agent. Vyhľadávaš aktuálne správy a trendy. Odpovedaj výlučne v JSON.'},
                    {'role': 'user', 'content': self._build_prompt()}
                ],
            )
            return self._parse_and_execute(response.choices[0].message.content, round_id)
        except Exception as e:
            self.save_log(round_id, '', '', error=str(e))
            return self.run_demo_round(round_id, STRATEGY, BUY_LIST, risk='high')

    def _build_prompt(self) -> str:
        return f"""Si AI investičný agent Perplexity so schopnosťou vyhľadávať aktuálne správy.
Tvoja stratégia: momentum trading, sledovanie trendov a správ.

{self.get_portfolio_summary()}

{self.get_market_context()}

Na základe najnovších správ a trhových trendov rozhodni o obchodoch. Odpovedz VÝLUČNE v JSON:
{{
  "reasoning": "Tvoja analýza správ a trendov v slovenčine",
  "strategy": "Názov stratégie",
  "trades": [
    {{"action": "buy", "ticker": "NVDA", "amount_eur": 30}}
  ]
}}"""

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
        return self.run_demo_round(round_id, STRATEGY, BUY_LIST, risk='high')
