#!/usr/bin/env python3
"""
Dashboard Generator - HTML Stats Display
"""

import json
from datetime import datetime

BOT_NAME = "Apex Shorts"

def generate_dashboard(bot, output_file='dashboard.html'):
    """Generate HTML dashboard"""
    
    stats = bot.get_stats()
    
    # Build position rows
    position_rows = ""
    for pos in bot.positions:
        position_rows += f"""
        <tr>
            <td><span class="ticker">{pos['symbol']}</span></td>
            <td>${pos['entry_price']:.2f}</td>
            <td>{pos['shares']:,}</td>
            <td>${pos['value']:,.2f}</td>
            <td class="stop">${pos['stop_loss']:.2f}</td>
            <td>{pos['entry_date'][:10]}</td>
        </tr>
        """
    
    if not position_rows:
        position_rows = "<tr><td colspan='6' class='empty'>No open positions</td></tr>"
    
    # Build trade history rows
    trade_rows = ""
    for trade in bot.trade_history[-20:]:  # Last 20 trades
        pnl_class = 'win' if trade['win'] else 'loss'
        trade_rows += f"""
        <tr class="{pnl_class}">
            <td><span class="ticker">{trade['symbol']}</span></td>
            <td>${trade['entry_price']:.2f}</td>
            <td>${trade['exit_price']:.2f}</td>
            <td>{trade['shares']:,}</td>
            <td class="{pnl_class}">${trade['pnl']:,.2f}</td>
            <td>{trade['exit_date'][:10]}</td>
        </tr>
        """
    
    if not trade_rows:
        trade_rows = "<tr><td colspan='6' class='empty'>No trades yet</td></tr>"
    
    win_rate_class = "win" if stats['win_rate'] > 50 else "loss"
    pnl_class = "win" if stats['total_pnl'] > 0 else "loss"
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{BOT_NAME}</title>
    <meta http-equiv="refresh" content="30">
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        :root {{
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-card: #1a1a24;
            --border: #2a2a3a;
            --text-primary: #f0f0f5;
            --text-secondary: #8888a0;
            --accent: #6366f1;
            --accent-glow: #818cf8;
            --win: #10b981;
            --win-bg: #10b98120;
            --loss: #ef4444;
            --loss-bg: #ef444420;
        }}
        
        body {{ 
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            background-image: 
                radial-gradient(ellipse at top, #6366f115 0%, transparent 50%),
                radial-gradient(ellipse at bottom right, #10b98110 0%, transparent 40%);
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 24px;
        }}
        
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 40px;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--border);
        }}
        
        .logo {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        
        .logo-icon {{
            width: 48px;
            height: 48px;
            background: linear-gradient(135deg, var(--accent), var(--accent-glow));
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            box-shadow: 0 0 30px #6366f140;
        }}
        
        .logo h1 {{
            font-size: 28px;
            font-weight: 700;
            background: linear-gradient(135deg, #fff 0%, #aaa 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.5px;
        }}
        
        .status {{
            display: flex;
            align-items: center;
            gap: 8px;
            background: var(--bg-card);
            padding: 8px 16px;
            border-radius: 20px;
            border: 1px solid var(--border);
            font-size: 13px;
            font-weight: 500;
            color: var(--text-secondary);
        }}
        
        .status-dot {{
            width: 8px;
            height: 8px;
            background: var(--win);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 16px;
            margin-bottom: 40px;
        }}
        
        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
            text-align: center;
            transition: all 0.3s ease;
        }}
        
        .stat-card:hover {{
            border-color: var(--accent);
            transform: translateY(-2px);
            box-shadow: 0 8px 32px #6366f120;
        }}
        
        .stat-card .label {{
            color: var(--text-secondary);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            font-weight: 600;
            margin-bottom: 12px;
        }}
        
        .stat-card .value {{
            font-size: 32px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        }}
        
        .stat-card .value.win {{ color: var(--win); }}
        .stat-card .value.loss {{ color: var(--loss); }}
        
        .section {{
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 24px;
        }}
        
        .section h2 {{ 
            color: var(--text-primary);
            margin-bottom: 20px;
            font-size: 16px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        th, td {{
            text-align: left;
            padding: 14px 16px;
            border-bottom: 1px solid var(--border);
        }}
        
        th {{
            color: var(--text-secondary);
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        td {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 14px;
        }}
        
        .ticker {{
            background: var(--accent);
            color: white;
            padding: 4px 10px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 12px;
        }}
        
        .stop {{ color: var(--loss); }}
        .win {{ color: var(--win); }}
        .loss {{ color: var(--loss); }}
        
        tr:hover {{ background: #ffffff05; }}
        
        .empty {{
            text-align: center;
            color: var(--text-secondary);
            padding: 40px !important;
            font-family: 'Inter', sans-serif !important;
        }}
        
        .footer {{
            text-align: center;
            color: var(--text-secondary);
            font-size: 12px;
            padding-top: 20px;
            opacity: 0.6;
        }}
        
        @media (max-width: 768px) {{
            .stats-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
            .header {{
                flex-direction: column;
                gap: 16px;
                text-align: center;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">
                <div class="logo-icon">📉</div>
                <h1>{BOT_NAME}</h1>
            </div>
            <div class="status">
                <div class="status-dot"></div>
                Paper Trading Active
            </div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">Total Trades</div>
                <div class="value">{stats['total_trades']}</div>
            </div>
            <div class="stat-card">
                <div class="label">Win Rate</div>
                <div class="value {win_rate_class}">{stats['win_rate']}%</div>
            </div>
            <div class="stat-card">
                <div class="label">W / L</div>
                <div class="value">{stats['wins']} / {stats['losses']}</div>
            </div>
            <div class="stat-card">
                <div class="label">Total P&L</div>
                <div class="value {pnl_class}">${stats['total_pnl']:,.2f}</div>
            </div>
            <div class="stat-card">
                <div class="label">Open Positions</div>
                <div class="value">{stats['open_positions']}</div>
            </div>
        </div>
        
        <div class="section">
            <h2>📊 Open Positions</h2>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Entry Price</th>
                        <th>Shares</th>
                        <th>Value</th>
                        <th>Stop Loss</th>
                        <th>Entry Date</th>
                    </tr>
                </thead>
                <tbody>
                    {position_rows}
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>📜 Trade History</h2>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Entry</th>
                        <th>Exit</th>
                        <th>Shares</th>
                        <th>P&L</th>
                        <th>Date</th>
                    </tr>
                </thead>
                <tbody>
                    {trade_rows}
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} • {BOT_NAME}
        </div>
    </div>
</body>
</html>"""
    
    with open(output_file, 'w') as f:
        f.write(html)
    
    print(f"📊 Dashboard updated: {output_file}")


if __name__ == '__main__':
    from bot import PennyShortBot
    bot = PennyShortBot()
    generate_dashboard(bot, '/data/.openclaw/workspace/penny-short-bot/dashboard.html')
