import os, json, re
from backend.agents.base_agent import BaseAgent

STRATEGY = "Konzervatívna hodnotová stratégia"
BUY_LIST = ['AAPL', 'MSFT', 'JNJ', 'KO', 'PG', 'BRK-B', 'VTI', 'SPY']


class ClaudeAgent(BaseAgent):
    def __init__(self):
        super().__init__('claude', 'Claude')
        self.api_key = os.getenv('ANTHROPIC_API_KEY', '')

    def run_round(self, round_id: int) -> dict:
        if not self.api_key:
            return self.run_demo_round(round_id, STRATEGY, BUY_LIST, risk='low')
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            message = client.messages.create(
                model='claude-3-5-sonnet-20241022',
                max_tokens=1024,
                messages=[{'role': 'user', 'content': self._build_prompt()}]
            )
            return self._parse_and_execute(message.content[0].text, round_id)
        except Exception as e:
            self.save_log(round_id, '', '', error=str(e))
            return self.run_demo_round(round_id, STRATEGY, BUY_LIST, risk='low')

    def _build_prompt(self) -> str:
        return f"""Si AI investičný agent Claude. Spravuješ virtuálne portfólio (simulácia).
Tvoja stratégia: konzervatívna, hodnotová investícia, blue-chip akcie, nízke riziko.

{self.get_portfolio_summary()}

{self.get_market_context()}

Analyzuj a rozhodni o obchodoch. Odpovedz VÝLUČNE v JSON:
{{
  "reasoning": "Tvoja analýza v slovenčine",
  "strategy": "Názov stratégie",
  "trades": [
    {{"action": "buy", "ticker": "JNJ", "amount_eur": 20}}
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
        return self.run_demo_round(round_id, STRATEGY, BUY_LIST, risk='low')
