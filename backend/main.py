import os
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['PYTHONHTTPSVERIFY'] = '0'
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

from backend.database import (
    init_db, get_agent_portfolio, get_performance_history,
    get_all_recent_trades, get_all_agents, create_round, complete_round
)
from backend.agents.gemini_agent import GeminiAgent
from backend.agents.gpt_agent import GPTAgent
from backend.agents.claude_agent import ClaudeAgent
from backend.agents.perplexity_agent import PerplexityAgent
from backend.simulation import update_all_prices

app = FastAPI(title="AI Investment Arena")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

AGENTS = {
    'gemini': GeminiAgent(),
    'gpt': GPTAgent(),
    'claude': ClaudeAgent(),
    'perplexity': PerplexityAgent(),
}

round_running = False


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/api/agents")
def api_agents():
    return get_all_agents()


@app.get("/api/status")
def api_status():
    result = []
    for agent_id in AGENTS:
        portfolio = get_agent_portfolio(agent_id)
        result.append(portfolio)
    return result


@app.get("/api/portfolio/{agent_id}")
def api_portfolio(agent_id: str):
    if agent_id not in AGENTS:
        raise HTTPException(status_code=404, detail="Agent nenájdený")
    return get_agent_portfolio(agent_id)


@app.get("/api/performance")
def api_performance():
    result = {}
    for agent_id in AGENTS:
        result[agent_id] = get_performance_history(agent_id, limit=100)
    return result


@app.get("/api/trades")
def api_trades():
    return get_all_recent_trades(limit=50)


@app.post("/api/round")
async def api_run_round(background_tasks: BackgroundTasks):
    global round_running
    if round_running:
        return {"status": "already_running", "message": "Kolo už beží, počkaj prosím..."}
    background_tasks.add_task(run_all_agents)
    return {"status": "started", "message": "Kolo spustené! Agenti analysujú trhy..."}


@app.post("/api/update-prices")
def api_update_prices():
    for agent_id in AGENTS:
        try:
            update_all_prices(agent_id)
        except Exception as e:
            pass
    return {"status": "ok", "message": "Ceny aktualizované"}


def run_all_agents():
    global round_running
    round_running = True
    round_id = create_round()
    try:
        for agent_id, agent in AGENTS.items():
            try:
                agent.run_round(round_id)
            except Exception as e:
                print(f"Chyba agenta {agent_id}: {e}")
        complete_round(round_id)
    finally:
        round_running = False


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
