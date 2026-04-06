import os, json, re
from backend.agents.base_agent import BaseAgent

STRATEGY = "Diverzifikovaná portfóliová stratégia"
BUY_LIST = ['AAPL', 'MSFT', 'JNJ', 'V', 'AMZN', 'SPY', 'QQQ', 'BTC-USD']


class GPTAgent(BaseAgent):
    def __init__(self):
        super().__init__('gpt', 'GPT-4o')
        self.api_key = os.getenv('OPENAI_API_KEY', '')

    def run_round(self, round_id: int) -> dict:
        if not self.api_key:
            return self.run_demo_round(round_id, STRATEGY, BUY_LIST, risk='medium')
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
            return self.run_demo_round(round_id, STRATEGY, BUY_LIST, risk='medium')

    def _build_prompt(self) -> str:
        return f"""Si AI investičný agent GPT-4o. Spravuješ virtuálne portfólio (simulácia).

{self.get_portfolio_summary()}

{self.get_market_context()}

Analyzuj a rozhodni o obchodoch. Odpovedz VÝLUČNE v JSON:
{{
  "reasoning": "Tvoja analýza v slovenčine",
  "strategy": "Názov stratégie",
  "trades": [
    {{"action": "buy", "ticker": "AAPL", "amount_eur": 20}},
    {{"action": "sell", "ticker": "SPY", "percentage": 30}}
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
        return self.run_demo_round(round_id, STRATEGY, BUY_LIST, risk='medium')
