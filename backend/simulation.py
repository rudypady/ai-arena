from backend.database import get_connection, get_current_cash, get_current_holdings
from backend.market_data import get_price, get_usd_to_eur_rate, is_crypto


def execute_buy(agent_id: str, ticker: str, amount_eur: float, round_id: int = None) -> dict:
    conn = get_connection()
    try:
        cash = get_current_cash(agent_id)
        if amount_eur <= 0:
            return {'success': False, 'error': 'Suma musí byť kladná'}
        amount_eur = min(amount_eur, cash)
        if amount_eur < 0.5:
            return {'success': False, 'error': 'Nedostatok hotovosti'}

        data = get_price(ticker)
        if 'error' in data:
            return {'success': False, 'error': data['error']}

        price_usd = data.get('price', 0)
        if not price_usd or price_usd <= 0:
            return {'success': False, 'error': f'Neplatná cena pre {ticker}'}

        eur_rate = get_usd_to_eur_rate()
        price_eur = price_usd * eur_rate
        quantity = amount_eur / price_eur
        asset_name = data.get('name', ticker)
        asset_type = data.get('asset_type', 'stock')

        conn.execute('''
            INSERT INTO holdings (agent_id, ticker, name, quantity, avg_buy_price, current_price, asset_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id, ticker) DO UPDATE SET
                quantity = quantity + excluded.quantity,
                avg_buy_price = (avg_buy_price * quantity + excluded.avg_buy_price * excluded.quantity) / (quantity + excluded.quantity),
                current_price = excluded.current_price,
                name = excluded.name,
                last_updated = CURRENT_TIMESTAMP
        ''', (agent_id, ticker, asset_name, quantity, price_eur, price_eur, asset_type))

        conn.execute(
            'INSERT INTO trades (agent_id, ticker, name, action, quantity, price, amount_eur, round_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (agent_id, ticker, asset_name, 'buy', quantity, price_eur, amount_eur, round_id)
        )

        new_cash = cash - amount_eur
        _snapshot(conn, agent_id, new_cash)
        conn.commit()
        return {'success': True, 'action': 'buy', 'ticker': ticker, 'name': asset_name,
                'quantity': quantity, 'price_eur': price_eur, 'amount_eur': amount_eur}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def execute_sell(agent_id: str, ticker: str, percentage: float = 100.0, round_id: int = None) -> dict:
    conn = get_connection()
    try:
        holding = conn.execute(
            'SELECT * FROM holdings WHERE agent_id = ? AND ticker = ? AND quantity > 0.0001',
            (agent_id, ticker)
        ).fetchone()
        if not holding:
            return {'success': False, 'error': f'Nemáš pozíciu v {ticker}'}
        holding = dict(holding)

        sell_qty = holding['quantity'] * (percentage / 100.0)
        if sell_qty <= 0:
            return {'success': False, 'error': 'Nulové množstvo'}

        data = get_price(ticker)
        if 'error' in data:
            return {'success': False, 'error': data['error']}

        price_usd = data.get('price', 0)
        eur_rate = get_usd_to_eur_rate()
        price_eur = price_usd * eur_rate
        amount_eur = sell_qty * price_eur

        new_qty = holding['quantity'] - sell_qty
        if new_qty < 0.0001:
            conn.execute('DELETE FROM holdings WHERE agent_id = ? AND ticker = ?', (agent_id, ticker))
        else:
            conn.execute(
                'UPDATE holdings SET quantity = ?, current_price = ?, last_updated = CURRENT_TIMESTAMP WHERE agent_id = ? AND ticker = ?',
                (new_qty, price_eur, agent_id, ticker)
            )

        conn.execute(
            'INSERT INTO trades (agent_id, ticker, name, action, quantity, price, amount_eur, round_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (agent_id, ticker, holding.get('name', ticker), 'sell', sell_qty, price_eur, amount_eur, round_id)
        )

        new_cash = get_current_cash(agent_id) + amount_eur
        _snapshot(conn, agent_id, new_cash)
        conn.commit()
        return {'success': True, 'action': 'sell', 'ticker': ticker, 'name': holding.get('name', ticker),
                'quantity': sell_qty, 'price_eur': price_eur, 'amount_eur': amount_eur, 'percentage': percentage}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def _snapshot(conn, agent_id: str, new_cash: float):
    holdings = conn.execute(
        'SELECT * FROM holdings WHERE agent_id = ? AND quantity > 0.0001', (agent_id,)
    ).fetchall()
    holdings_value = sum(dict(h)['quantity'] * (dict(h).get('current_price') or dict(h)['avg_buy_price']) for h in holdings)
    total = new_cash + holdings_value
    pnl = ((total - 100.0) / 100.0) * 100
    conn.execute(
        'INSERT INTO portfolio_snapshots (agent_id, cash, holdings_value, total_value, pnl_percent) VALUES (?, ?, ?, ?, ?)',
        (agent_id, new_cash, holdings_value, total, pnl)
    )


def update_all_prices(agent_id: str):
    conn = get_connection()
    holdings = conn.execute(
        'SELECT * FROM holdings WHERE agent_id = ? AND quantity > 0.0001', (agent_id,)
    ).fetchall()
    eur_rate = get_usd_to_eur_rate()
    for h in holdings:
        h = dict(h)
        try:
            data = get_price(h['ticker'])
            price_usd = data.get('price', 0)
            if price_usd and price_usd > 0:
                conn.execute(
                    'UPDATE holdings SET current_price = ?, last_updated = CURRENT_TIMESTAMP WHERE agent_id = ? AND ticker = ?',
                    (price_usd * eur_rate, agent_id, h['ticker'])
                )
        except Exception:
            pass
    cash = get_current_cash(agent_id)
    _snapshot(conn, agent_id, cash)
    conn.commit()
    conn.close()
