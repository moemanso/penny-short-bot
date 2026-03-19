#!/usr/bin/env python3
"""
Penny Short Bot - Main Trading System
"""

import json
import os
from datetime import datetime, timedelta
from config import *

class PennyShortBot:
    def __init__(self, paper_mode=True):
        self.paper_mode = paper_mode
        self.positions = []
        self.trade_history = []
        self.portfolio_value = DEFAULT_PORTFOLIO
        self.wins = 0
        self.losses = 0
        
    def calculate_position_size(self, stock_price, stop_pct=STOP_LOSS_PCT):
        """Calculate how many shares to short based on risk parameters"""
        risk_amount = self.portfolio_value * MAX_RISK_PER_TRADE
        stop_dollars = stock_price * stop_pct
        shares = risk_amount / stop_dollars
        return int(shares)
    
    def check_risk_limits(self, new_position_value):
        """Check if adding this position would exceed risk limits"""
        total_exposure = sum(p['value'] for p in self.positions)
        if total_exposure + new_position_value > self.portfolio_value * 0.5:
            return False  # Max 50% portfolio exposure
        if len(self.positions) >= MAX_CONCURRENT_SHORTS:
            return False
        return True
    
    def execute_short(self, symbol, price, shares):
        """Execute a short position"""
        position = {
            'symbol': symbol,
            'entry_price': price,
            'shares': shares,
            'value': price * shares,
            'entry_date': datetime.now().isoformat(),
            'stop_loss': price * (1 + STOP_LOSS_PCT)
        }
        self.positions.append(position)
        print(f"📉 SHORT: {symbol} @ ${price:.2f} x {shares} shares")
        return position
    
    def check_stops(self, current_prices):
        """Check if any positions hit stop loss"""
        to_close = []
        for pos in self.positions:
            symbol = pos['symbol']
            if symbol in current_prices:
                current = current_prices[symbol]
                if current >= pos['stop_loss']:
                    to_close.append(pos)
        return to_close
    
    def close_position(self, position, exit_price):
        """Close a position and record P&L"""
        pnl = (position['entry_price'] - exit_price) * position['shares']
        is_win = pnl > 0
        
        trade_record = {
            'symbol': position['symbol'],
            'entry_price': position['entry_price'],
            'exit_price': exit_price,
            'shares': position['shares'],
            'pnl': pnl,
            'win': is_win,
            'entry_date': position['entry_date'],
            'exit_date': datetime.now().isoformat()
        }
        
        self.trade_history.append(trade_record)
        
        if is_win:
            self.wins += 1
        else:
            self.losses += 1
        
        self.positions = [p for p in self.positions if p['symbol'] != position['symbol']]
        
        print(f"✂️ CLOSED: {position['symbol']} @ ${exit_price:.2f} | P&L: ${pnl:.2f} ({'WIN' if is_win else 'LOSS'})")
        return trade_record
    
    def get_stats(self):
        """Get current statistics"""
        total_trades = self.wins + self.losses
        win_rate = (self.wins / total_trades * 100) if total_trades > 0 else 0
        total_pnl = sum(t['pnl'] for t in self.trade_history)
        
        return {
            'total_trades': total_trades,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': round(win_rate, 1),
            'total_pnl': round(total_pnl, 2),
            'open_positions': len(self.positions),
            'portfolio_value': round(self.portfolio_value, 2)
        }
    
    def save_state(self, filepath='bot_state.json'):
        """Save bot state to file"""
        state = {
            'positions': self.positions,
            'trade_history': self.trade_history,
            'wins': self.wins,
            'losses': self.losses,
            'portfolio_value': self.portfolio_value,
            'last_update': datetime.now().isoformat()
        }
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)
    
    def load_state(self, filepath='bot_state.json'):
        """Load bot state from file"""
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                state = json.load(f)
                self.positions = state.get('positions', [])
                self.trade_history = state.get('trade_history', [])
                self.wins = state.get('wins', 0)
                self.losses = state.get('losses', 0)
                self.portfolio_value = state.get('portfolio_value', DEFAULT_PORTFOLIO)


def main():
    """Test initialization"""
    bot = PennyShortBot(paper_mode=True)
    print("🤖 Penny Short Bot initialized")
    print(f"   Paper mode: {bot.paper_mode}")
    print(f"   Portfolio: ${bot.portfolio_value:,.2f}")
    stats = bot.get_stats()
    print(f"   Total trades: {stats['total_trades']}")
    return bot


if __name__ == '__main__':
    main()