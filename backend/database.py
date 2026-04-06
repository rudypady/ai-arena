import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'burza.db')


def get_connection():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(os.path.abspath(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            model TEXT NOT NULL,
            color TEXT NOT NULL,
            icon TEXT NOT NULL,
            initial_capital REAL NOT NULL DEFAULT 100.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cash REAL NOT NULL,
            holdings_value REAL NOT NULL,
            total_value REAL NOT NULL,
            pnl_percent REAL NOT NULL,
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        );

        CREATE TABLE IF NOT EXISTS holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT,
            quantity REAL NOT NULL DEFAULT 0,
            avg_buy_price REAL NOT NULL,
            current_price REAL,
            asset_type TEXT DEFAULT 'stock',
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(agent_id, ticker),
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        );

        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT,
            action TEXT NOT NULL,
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            amount_eur REAL NOT NULL,
            round_id INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        );

        CREATE TABLE IF NOT EXISTS agent_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            round_id INTEGER,
            reasoning TEXT,
            strategy TEXT,
            error TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        );

        CREATE TABLE IF NOT EXISTS rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            status TEXT DEFAULT 'running'
        );
    ''')

    agents_data = [
        ('gemini', 'Gemini', 'Google Gemini 1.5 Pro', '#6c63ff', '✦'),
        ('gpt', 'GPT-4o', 'OpenAI GPT-4o', '#10b981', '⬡'),
        ('claude', 'Claude', 'Anthropic Claude 3.5', '#f59e0b', '◈'),
        ('perplexity', 'Perplexity', 'Perplexity Sonar', '#ec4899', '◎'),
    ]

    for agent_id, name, model, color, icon in agents_data:
        cursor.execute(
            'INSERT OR IGNORE INTO agents (id, name, model, color, icon, initial_capital) VALUES (?, ?, ?, ?, ?, 100.0)',
            (agent_id, name, model, color, icon)
        )
        existing = cursor.execute(
            'SELECT COUNT(*) FROM portfolio_snapshots WHERE agent_id = ?', (agent_id,)
        ).fetchone()[0]
        if existing == 0:
            cursor.execute(
                'INSERT INTO portfolio_snapshots (agent_id, cash, holdings_value, total_value, pnl_percent) VALUES (?, 100.0, 0.0, 100.0, 0.0)',
                (agent_id,)
            )

    conn.commit()
    conn.close()


def get_agent_portfolio(agent_id: str) -> dict:
    conn = get_connection()
    snapshot = conn.execute(
        'SELECT * FROM portfolio_snapshots WHERE agent_id = ? ORDER BY timestamp DESC LIMIT 1',
        (agent_id,)
    ).fetchone()
    holdings = conn.execute(
        'SELECT * FROM holdings WHERE agent_id = ? AND quantity > 0.0001',
        (agent_id,)
    ).fetchall()
    trades = conn.execute(
        'SELECT * FROM trades WHERE agent_id = ? ORDER BY timestamp DESC LIMIT 10',
        (agent_id,)
    ).fetchall()
    log = conn.execute(
        'SELECT * FROM agent_logs WHERE agent_id = ? ORDER BY timestamp DESC LIMIT 1',
        (agent_id,)
    ).fetchone()
    agent = conn.execute('SELECT * FROM agents WHERE id = ?', (agent_id,)).fetchone()
    conn.close()
    return {
        'agent': dict(agent) if agent else {},
        'snapshot': dict(snapshot) if snapshot else {},
        'holdings': [dict(h) for h in holdings],
        'recent_trades': [dict(t) for t in trades],
        'latest_log': dict(log) if log else {},
    }


def get_performance_history(agent_id: str, limit: int = 100) -> list:
    conn = get_connection()
    rows = conn.execute(
        'SELECT timestamp, total_value, pnl_percent FROM portfolio_snapshots WHERE agent_id = ? ORDER BY timestamp ASC LIMIT ?',
        (agent_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_recent_trades(limit: int = 50) -> list:
    conn = get_connection()
    rows = conn.execute(
        '''SELECT t.*, a.name as agent_name, a.color as agent_color
           FROM trades t JOIN agents a ON t.agent_id = a.id
           ORDER BY t.timestamp DESC LIMIT ?''',
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_agents() -> list:
    conn = get_connection()
    rows = conn.execute('SELECT * FROM agents').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_round() -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO rounds (status) VALUES ('running')")
    round_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return round_id


def complete_round(round_id: int):
    conn = get_connection()
    conn.execute(
        "UPDATE rounds SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
        (round_id,)
    )
    conn.commit()
    conn.close()


def get_current_cash(agent_id: str) -> float:
    conn = get_connection()
    row = conn.execute(
        'SELECT cash FROM portfolio_snapshots WHERE agent_id = ? ORDER BY timestamp DESC LIMIT 1',
        (agent_id,)
    ).fetchone()
    conn.close()
    return row['cash'] if row else 100.0


def get_current_holdings(agent_id: str) -> list:
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM holdings WHERE agent_id = ? AND quantity > 0.0001',
        (agent_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
