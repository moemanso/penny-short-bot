#!/usr/bin/env python3
"""
Apex Shorts - Automated Penny Stock Shorting Bot
"""

import time
import os
import yfinance as yf
from datetime import datetime
from bot import PennyShortBot
from screener import StockScreener
from alpaca import AlpacaClient
from dashboard import generate_dashboard
from config import *

class TradingBot:
    def __init__(self):
        self.alpaca = AlpacaClient(paper=PAPER_TRADING)
        self.bot = PennyShortBot(paper_mode=PAPER_TRADING)
        self.screener = StockScreener()
        
        # SYNC with Alpaca - get real positions
        self.sync_alpaca_positions()
    
    def sync_alpaca_positions(self):
        """Sync positions from Alpaca"""
        try:
            alpaca_positions = self.alpaca.get_positions()
            
            if alpaca_positions and isinstance(alpaca_positions, list):
                # Clear local and sync from Alpaca
                self.bot.positions = []
                
                for pos in alpaca_positions:
                    symbol = pos.get('symbol', '')
                    qty = float(pos.get('qty', 0))
                    avg_price = float(pos.get('avg_entry_price', 0))
                    market_value = float(pos.get('market_value', 0))
                    
                    if qty > 0 and symbol:
                        # This is a short position
                        self.bot.positions.append({
                            'symbol': symbol,
                            'entry_price': avg_price,
                            'shares': int(qty),
                            'value': market_value,
                            'entry_date': datetime.now().isoformat(),
                            'stop_loss': avg_price * (1 + STOP_LOSS_PCT)
                        })
                
                print(f"   🔄 Synced {len(self.bot.positions)} positions from Alpaca")
        except Exception as e:
            print(f"   ⚠️  Sync error: {e}")
    
    def get_current_price(self, symbol):
        """Get current price for a symbol"""
        try:
            stock = yf.Ticker(symbol)
            price = stock.info.get('currentPrice', 0)
            return price if price > 0 else None
        except:
            return None
    
    def scan_and_execute(self):
        """Scan for opportunities and execute trades"""
        print(f"\n{'='*60}")
        print(f"🤖 APEX SHORTS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        # Sync first
        self.sync_alpaca_positions()
        
        # Get opportunities
        opportunities = self.screener.get_opportunities()
        
        if not opportunities:
            print("   No opportunities found")
            return
        
        # Check existing positions
        existing = [p['symbol'] for p in self.bot.positions]
        print(f"\n📊 Current positions: {existing if existing else 'None'}")
        
        # Try to open new positions
        for opp in opportunities[:3]:
            symbol = opp['symbol']
            
            if symbol in existing:
                print(f"   ⏭️  {symbol} - already shorting")
                continue
            
            if len(self.bot.positions) >= MAX_CONCURRENT_SHORTS:
                print(f"   ⚠️  Max positions reached")
                break
            
            price = self.get_current_price(symbol)
            if not price:
                print(f"   ❌ {symbol} - no price data")
                continue
            
            shares = self.bot.calculate_position_size(price)
            position_value = price * shares
            
            if position_value > self.bot.portfolio_value * 0.3:
                print(f"   ⚠️  {symbol} - position too large")
                continue
            
            print(f"\n   📉 OPENING SHORT: {symbol} @ ${price:.2f} x {shares} shares")
            
            result = self.alpaca.submit_short(symbol, shares)
            
            if result:
                self.bot.execute_short(symbol, price, shares)
                print(f"   ✅ SUCCESS! Short opened")
            else:
                print(f"   ❌ FAILED")
        
        # Check stop losses
        self.check_stops()
        
        # Save state
        self.bot.save_state()
        generate_dashboard(self.bot)
        
        stats = self.bot.get_stats()
        print(f"\n📈 STATS: {stats['total_trades']} trades | Win: {stats['win_rate']}% | P&L: ${stats['total_pnl']:,.2f}")
    
    def check_stops(self):
        """Check if any positions hit stop loss"""
        for pos in list(self.bot.positions):
            symbol = pos['symbol']
            current = self.get_current_price(symbol)
            
            if not current:
                continue
            
            print(f"   {symbol}: ${current:.2f} (entry: ${pos['entry_price']:.2f}, stop: ${pos['stop_loss']:.2f})")
            
            if current >= pos['stop_loss']:
                print(f"   🔴 STOP HIT - covering {symbol}")
                result = self.alpaca.cover_short(symbol, pos['shares'])
                if result:
                    self.bot.close_position(pos, current)
                    print(f"   ✅ Covered at ${current:.2f}")
    
    def run(self, interval=300):
        """Run continuously"""
        print(f"\n🚀 APEX SHORTS - Starting 24/7")
        print(f"   Scan interval: {interval/60:.0f} minutes")
        
        self.scan_and_execute()
        
        while True:
            try:
                time.sleep(interval)
                self.scan_and_execute()
            except KeyboardInterrupt:
                print("\n🛑 Stopping...")
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(60)


if __name__ == '__main__':
    bot = TradingBot()
    bot.run(interval=300)
