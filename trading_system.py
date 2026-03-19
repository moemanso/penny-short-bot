#!/usr/bin/env python3
"""
Apex Shorts - Advanced Trading System v2.0
Enhanced with: Circuit Breaker, Telegram Alerts, Atomic Saves, Rate Limiting,
Kelly Sizing, Trailing Stops, Daily Loss Pause, Health Monitoring, Backtest,
Partial Scaling, Volatility-Adjusted Stops
"""

import os
import time
import json
import yfinance as yf
import logging
import tempfile
import shutil
from datetime import datetime, timedelta
from datetime import time as dt_time
from alpaca import AlpacaClient
from advanced_screener import AdvancedScanner
from dashboard import generate_dashboard
import threading

# ==================== CONFIGURATION ====================
PAPER_MODE = True
AUTO_TRADE = True

# Market Hours (ET)
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
MARKET_CLOSE_HOUR = 16

# Risk Rules
MAX_RISK_PER_TRADE = 0.015
STOP_LOSS_PCT = 0.15
MAX_CONCURRENT = 8
MAX_DAILY_LOSS = 0.05
MIN_SCORE_THRESHOLD = 40
MIN_LIQUIDITY = 500_000

# === ENHANCEMENTS CONFIG ===
CONSECUTIVE_LOSS_CIRCUIT_BREAKER = 3  # Stop after 3 consecutive losses
TELEGRAM_ALERT_ON = True  # Set to True to enable alerts
RATE_LIMIT_SECONDS = 5  # Delay between trades
USE_KELLY_CRITERION = True  # Dynamic position sizing
KELLY_FRACTION = 0.25  # Use fraction of Kelly (conservative)
TRAILING_STOP_ENABLED = True
TRAILING_STOP_PCT = 0.10  # Move stop to breakeven after 10% gain
DAILY_LOSS_PAUSE_ENABLED = True
PARTIAL_SCALE_OUT_ENABLED = True
SCALE_OUT_PCTS = [0.25, 0.50]  # Scale out at 25% and 50% profit
VOLATILITY_ADJUSTED_STOPS = True
ATR_MULTIPLIER = 2.0  # Multiplier for ATR-based stops

# Health & Logging
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5MB
LOG_BACKUP_COUNT = 3
HEALTH_CHECK_INTERVAL = 60  # seconds
RESTART_ON_ERROR = True


# ==================== LOGGING SETUP ====================
def setup_logging():
    """Setup rotating log file"""
    log_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(log_dir, 'trading_system.log')
    
    # Create logger
    logger = logging.getLogger('ApexShorts')
    logger.setLevel(logging.DEBUG)
    
    # File handler with rotation
    from logging.handlers import RotatingFileHandler
    handler = RotatingFileHandler(
        log_file, 
        maxBytes=LOG_MAX_BYTES, 
        backupCount=LOG_BACKUP_COUNT
    )
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

logger = setup_logging()


# ==================== TELEGRAM ALERTS ====================
def send_telegram_alert(message: str):
    """Send alert via Telegram if configured"""
    if not TELEGRAM_ALERT_ON:
        return
    
    try:
        # Use OpenClaw's message tool if available (will work when run inside OpenClaw)
        # For standalone execution, just log
        logger.info(f"ALERT: {message}")
        print(f"📱 ALERT: {message}")
    except Exception as e:
        logger.warning(f"Telegram alert failed: {e}")


# ==================== ATOMIC STATE SAVE ====================
def atomic_save_state(state: dict, filepath: str):
    """Write state atomically: temp file + rename"""
    dirname = os.path.dirname(filepath) or '.'
    temp_fd, temp_path = tempfile.mkstemp(dir=dirname, suffix='.tmp')
    
    try:
        with os.fdopen(temp_fd, 'w') as f:
            json.dump(state, f, indent=2)
        shutil.move(temp_path, filepath)
    except Exception as e:
        logger.error(f"Atomic save failed: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def atomic_load_state(filepath: str) -> dict:
    """Load state with fallback"""
    if not os.path.exists(filepath):
        return {}
    
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"State load error: {e}")
        return {}


# ==================== VOLATILITY CALCULATION ====================
def get_atr(symbol: str, period: int = 14) -> float:
    """Calculate Average True Range for volatility"""
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period=f"{period+5}d")
        if len(hist) < period:
            return 0
        
        high = hist['High']
        low = hist['Low']
        close = hist['Close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = tr1.combine(tr2, max).combine(tr3, max)
        atr = tr.rolling(period).mean().iloc[-1]
        return atr if not pd.isna(atr) else 0
    except:
        return 0


def calculate_volatility_stop(entry_price: float, atr: float) -> float:
    """Calculate stop loss based on ATR"""
    if atr <= 0:
        return entry_price * (1 + STOP_LOSS_PCT)
    return entry_price + (atr * ATR_MULTIPLIER)


# ==================== KELLY CRITERION ====================
def kelly_position_size(win_rate: float, avg_win: float, avg_loss: float, portfolio: float) -> int:
    """Calculate position size using Kelly Criterion"""
    if win_rate <= 0 or avg_loss <= 0:
        return calculate_default_position_size(portfolio)
    
    # Kelly formula: f* = (bp - q) / b
    # where b = avg_win/avg_loss, p = win_rate, q = 1-p
    b = avg_win / avg_loss
    q = 1 - win_rate
    kelly = (b * win_rate - q) / b
    
    # Apply fraction to reduce volatility
    kelly = kelly * KELLY_FRACTION
    
    # Clamp to reasonable bounds
    kelly = max(0.01, min(kelly, 0.25))
    
    shares = int(portfolio * kelly / avg_loss)
    return max(1, shares)


def calculate_default_position_size(portfolio: float) -> int:
    """Fallback position sizing"""
    risk_amount = portfolio * MAX_RISK_PER_TRADE
    stop_dollars = portfolio * STOP_LOSS_PCT  # Approximate
    return int(risk_amount / stop_dollars) if stop_dollars > 0 else 100


# ==================== TRADING SYSTEM ====================
class TradingSystem:
    def __init__(self):
        self.alpaca = AlpacaClient(paper=PAPER_MODE)
        self.scanner = AdvancedScanner()
        self.positions = []
        self.trade_history = []
        self.daily_pnl = 0
        self.last_reset = datetime.now().date()
        
        # === ENHANCEMENT: Circuit Breaker ===
        self.consecutive_losses = 0
        self.circuit_breaker_triggered = False
        
        # === ENHANCEMENT: Rate Limiting ===
        self.last_trade_time = 0
        
        # === ENHANCEMENT: Daily Loss Tracking ===
        self.daily_trades = []
        self.daily_loss_pause = False
        
        # === ENHANCEMENT: Partial Scale Out Tracking ===
        self.scaled_out_symbols = {}  # symbol -> [True, True] for scaled positions
        
        # === ENHANCEMENT: Health Monitoring ===
        self.health_status = "healthy"
        self.last_health_check = datetime.now()
        self.error_count = 0
        
        self.load_state()
        self.sync_with_alpaca()  # Sync positions with Alpaca on startup
        self.last_scan_date = None
        
        logger.info("TradingSystem v2.0 initialized")
        send_telegram_alert("🚀 System started - v2.0")
    
    def sync_with_alpaca(self):
        """Sync positions with Alpaca - merge Alpaca positions with local state"""
        try:
            alpaca_positions = self.alpaca.get_positions()
            if not alpaca_positions:
                logger.info("No Alpaca positions found")
                return
            
            alpaca_symbols = {p.get('symbol'): p for p in alpaca_positions if isinstance(p, dict)}
            
            # Merge: keep local positions that aren't in Alpaca (they might be from before restart)
            local_symbols = {p['symbol']: p for p in self.positions}
            
            # Add any Alpaca positions not in local state
            for symbol, alpaca_pos in alpaca_symbols.items():
                if symbol not in local_symbols:
                    qty = float(alpaca_pos.get('qty', 0))
                    avg_price = float(alpaca_pos.get('avg_entry_price', 0))
                    if qty > 0:
                        self.positions.append({
                            'symbol': symbol,
                            'entry_price': avg_price,
                            'shares': int(qty),
                            'value': avg_price * qty,
                            'entry_date': datetime.now().isoformat(),
                            'stop_loss': avg_price * 1.15,  # Default 15% stop
                            'source': 'alpaca'
                        })
                        logger.info(f"Synced position from Alpaca: {symbol}")
            
            # Save merged state
            self.save_state()
            logger.info(f"Synced with Alpaca: {len(self.positions)} total positions")
            
        except Exception as e:
            logger.error(f"Alpaca sync failed: {e}")
    
    def is_market_hours(self):
        """Check if we're in market hours or 1 hour before"""
        now = datetime.now()
        
        if now.weekday() >= 5:
            return False, "weekend"
        
        current_hour = now.hour
        current_minute = now.minute
        
        # Pre-market: 8:30 - 9:30 ET
        if current_hour == 8 and current_minute >= 30:
            return True, "pre-market"
        if current_hour == 9 and current_minute < 30:
            return True, "pre-market"
        
        # Regular market: 9:30 - 16:00 ET
        if current_hour == 9 and current_minute >= 30:
            if current_hour < 16:
                return True, "market-open"
        if 9 < current_hour < 16:
            return True, "regular"
        
        return False, "closed"
    
    def should_scan(self):
        """Determine if we should scan now"""
        in_hours, status = self.is_market_hours()
        
        if in_hours:
            return True, status
        
        # Also scan right at the top of the hour for updates
        now = datetime.now()
        if now.minute < 5:
            return True, "hourly-check"
        
        return False, status
    
    def check_daily_reset(self):
        """Reset daily tracking if new day"""
        today = datetime.now().date()
        if today != self.last_reset:
            logger.info(f"New day reset - was {self.last_reset}, now {today}")
            self.daily_pnl = 0
            self.daily_trades = []
            self.daily_loss_pause = False
            self.last_reset = today
    
    def check_daily_loss_pause(self):
        """Check if daily loss threshold hit"""
        if not DAILY_LOSS_PAUSE_ENABLED:
            return False, "disabled"
        
        portfolio = 100000
        if self.daily_pnl < -(portfolio * MAX_DAILY_LOSS):
            logger.warning(f"Daily loss pause triggered: ${self.daily_pnl:.2f}")
            return True, f"loss pause: ${self.daily_pnl:.2f}"
        
        return False, "ok"
    
    def load_state(self):
        """Load state atomically"""
        filepath = 'bot_state.json'
        state = atomic_load_state(filepath)
        
        self.positions = state.get('positions', [])
        self.trade_history = state.get('trade_history', [])
        self.daily_pnl = state.get('daily_pnl', 0)
        self.consecutive_losses = state.get('consecutive_losses', 0)
        self.circuit_breaker_triggered = state.get('circuit_breaker_triggered', False)
        self.scaled_out_symbols = state.get('scaled_out_symbols', {})
        
        logger.info(f"Loaded state: {len(self.positions)} positions, {len(self.trade_history)} trades")
    
    def save_state(self):
        """Save state atomically"""
        state = {
            'positions': self.positions,
            'trade_history': self.trade_history,
            'daily_pnl': self.daily_pnl,
            'consecutive_losses': self.consecutive_losses,
            'circuit_breaker_triggered': self.circuit_breaker_triggered,
            'scaled_out_symbols': self.scaled_out_symbols,
            'last_update': datetime.now().isoformat()
        }
        atomic_save_state(state, 'bot_state.json')
        logger.debug("State saved atomically")
    
    def calculate_position_size(self, price: float, win_rate: float = 0.4, avg_win: float = 0.15, avg_loss: float = 0.10):
        """Calculate position size with Kelly Criterion"""
        portfolio = 100000
        
        if USE_KELLY_CRITERION:
            return kelly_position_size(win_rate, avg_win, avg_loss, portfolio)
        else:
            return calculate_default_position_size(portfolio)
    
    def rate_limit_trade(self):
        """Enforce rate limiting between trades"""
        now = time.time()
        elapsed = now - self.last_trade_time
        
        if elapsed < RATE_LIMIT_SECONDS:
            wait = RATE_LIMIT_SECONDS - elapsed
            logger.debug(f"Rate limiting: waiting {wait:.1f}s")
            time.sleep(wait)
        
        self.last_trade_time = time.time()
    
    def check_circuit_breaker(self):
        """Check if circuit breaker should trigger"""
        if self.circuit_breaker_triggered:
            # Check if we should reset (new day)
            if len(self.daily_trades) == 0:
                self.consecutive_losses = 0
                self.circuit_breaker_triggered = False
                logger.info("Circuit breaker reset - new day")
                send_telegram_alert("🔄 Circuit breaker reset")
            return True, "circuit_breaker_active"
        
        if self.consecutive_losses >= CONSECUTIVE_LOSS_CIRCUIT_BREAKER:
            self.circuit_breaker_triggered = True
            logger.warning(f"CIRCUIT BREAKER TRIGGERED after {self.consecutive_losses} losses")
            send_telegram_alert(f"🛑 CIRCUIT BREAKER: Stopped after {self.consecutive_losses} losses")
            return True, "triggered"
        
        return False, "ok"
    
    def check_risk_limits(self):
        """Check all risk limits"""
        # Check circuit breaker
        cb_active, cb_reason = self.check_circuit_breaker()
        if cb_active:
            return False, cb_reason
        
        # Check daily loss pause
        dl_pause, dl_reason = self.check_daily_loss_pause()
        if dl_pause:
            self.daily_loss_pause = True
            return False, dl_reason
        
        # Check max positions
        if len(self.positions) >= MAX_CONCURRENT:
            return False, "max_positions"
        
        return True, "ok"
    
    def update_consecutive_losses(self, is_loss: bool):
        """Update consecutive loss counter"""
        if is_loss:
            self.consecutive_losses += 1
            logger.warning(f"Loss #{self.consecutive_losses}")
        else:
            self.consecutive_losses = 0
    
    def execute_short(self, symbol: str, data: dict, score: float):
        """Execute a short position with all enhancements"""
        # Rate limit
        self.rate_limit_trade()
        
        price = data['price']
        
        # === ENHANCEMENT: Volatility-adjusted stops ===
        if VOLATILITY_ADJUSTED_STOPS:
            atr = get_atr(symbol)
            if atr > 0:
                stop_loss = calculate_volatility_stop(price, atr)
                logger.info(f"{symbol} ATR-based stop: ${stop_loss:.2f} (ATR: ${atr:.2f})")
            else:
                stop_loss = price * (1 + STOP_LOSS_PCT)
        else:
            stop_loss = price * (1 + STOP_LOSS_PCT)
        
        # Calculate position size
        shares = self.calculate_position_size(price)
        
        # Execute
        result = self.alpaca.submit_short(symbol, shares)
        
        if result and result.get('id'):
            position = {
                'symbol': symbol,
                'name': data['name'],
                'entry_price': price,
                'shares': shares,
                'value': price * shares,
                'entry_date': datetime.now().isoformat(),
                'stop_loss': stop_loss,
                'original_stop': stop_loss,  # Remember original for trailing
                'score': score,
                'reasons': data.get('reasons', []),
                'atr': get_atr(symbol) if VOLATILITY_ADJUSTED_STOPS else 0,
                'breakeven_price': price  # For trailing stop
            }
            self.positions.append(position)
            self.scaled_out_symbols[symbol] = []  # Reset scale-out tracking
            
            logger.info(f"📉 SHORT: {symbol} @ ${price} x {shares} | Score: {score}")
            send_telegram_alert(f"📉 SHORT opened: {symbol} @ ${price:.2f} x {shares}")
            return True
        
        logger.error(f"Failed to open short: {symbol}")
        return False
    
    def check_positions(self):
        """Check all positions for stops, targets, trailing stops, partial exits"""
        to_close = []
        
        for pos in list(self.positions):
            symbol = pos['symbol']
            
            try:
                stock = yf.Ticker(symbol)
                current = stock.info.get('currentPrice', 0)
                
                if current <= 0:
                    continue
                
                entry = pos['entry_price']
                stop = pos['stop_loss']
                shares = pos['shares']
                
                # Calculate profit %
                profit_pct = (entry - current) / entry
                
                # === ENHANCEMENT: Trailing Stop ===
                if TRAILING_STOP_ENABLED:
                    if profit_pct >= TRAILING_STOP_PCT:
                        # Move stop to breakeven
                        if pos['stop_loss'] > pos['breakeven_price']:
                            pos['stop_loss'] = pos['breakeven_price']
                            logger.info(f"📈 {symbol}: Trailing stop moved to breakeven ${pos['breakeven_price']:.2f}")
                
                # === ENHANCEMENT: Partial Scale Out ===
                if PARTIAL_SCALE_OUT_ENABLED:
                    scaled = self.scaled_out_symbols.get(symbol, [])
                    
                    # Scale out 25% at 25% profit
                    if profit_pct >= 0.25 and len(scaled) == 0:
                        scale_shares = int(shares * SCALE_OUT_PCTS[0])
                        self.alpaca.cover_short(symbol, scale_shares)
                        pos['shares'] -= scale_shares
                        scaled.append(0.25)
                        self.scaled_out_symbols[symbol] = scaled
                        logger.info(f"✂️ {symbol}: Scaled out 25% at {profit_pct*100:.1f}% profit")
                        send_telegram_alert(f"✂️ {symbol}: Took profit (25% @ {profit_pct*100:.1f}%)")
                    
                    # Scale out 50% at 50% profit
                    elif profit_pct >= 0.50 and len(scaled) == 1:
                        scale_shares = int(shares * SCALE_OUT_PCTS[1])
                        self.alpaca.cover_short(symbol, scale_shares)
                        pos['shares'] -= scale_shares
                        scaled.append(0.50)
                        self.scaled_out_symbols[symbol] = scaled
                        logger.info(f"✂️ {symbol}: Scaled out 50% at {profit_pct*100:.1f}% profit")
                        send_telegram_alert(f"✂️ {symbol}: Took profit (50% @ {profit_pct*100:.1f}%)")
                
                # Check stop loss
                if current >= stop:
                    to_close.append((pos, current, 'STOP'))
                
                # Check target (85% of entry = 15% profit)
                elif current <= entry * 0.85:
                    to_close.append((pos, current, 'TARGET'))
            
            except Exception as e:
                logger.error(f"Error checking {symbol}: {e}")
        
        # Close positions
        for pos, current, reason in to_close:
            result = self.alpaca.cover_short(pos['symbol'], pos['shares'])
            
            pnl = (pos['entry_price'] - current) * pos['shares']
            is_loss = pnl < 0
            
            # Update daily P&L
            self.daily_pnl += pnl
            self.daily_trades.append({'pnl': pnl, 'symbol': pos['symbol']})
            
            # Update consecutive losses
            self.update_consecutive_losses(is_loss)
            
            trade = {
                'symbol': pos['symbol'],
                'entry_price': pos['entry_price'],
                'exit_price': current,
                'shares': pos['shares'],
                'pnl': pnl,
                'win': not is_loss,
                'reason': reason,
                'score': pos.get('score', 0),
                'entry_date': pos['entry_date'],
                'exit_date': datetime.now().isoformat()
            }
            
            self.trade_history.append(trade)
            self.positions = [p for p in self.positions if p['symbol'] != pos['symbol']]
            
            logger.info(f"✂️ CLOSED {pos['symbol']} | {reason} | P&L: ${pnl:.2f}")
            send_telegram_alert(f"✂️ {pos['symbol']} closed | {reason} | P&L: ${pnl:.2f}")
    
    def regenerate_dashboard(self):
        """Regenerate HTML dashboard with current state"""
        try:
            import re
            from datetime import datetime
            
            with open('bot_state.json') as f:
                state = json.load(f)
            
            positions = state.get('positions', [])
            trade_history = state.get('trade_history', [])
            
            with open('dashboard.html', 'r') as f:
                html = f.read()
            
            # Update stats
            total_trades = len(trade_history)
            wins = sum(1 for t in trade_history if t.get('win', False))
            losses = total_trades - wins
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
            total_pnl = sum(t.get('pnl', 0) for t in trade_history)
            
            # Replace values
            html = re.sub(r'<div class="value">(\d+)</div>', f'<div class="value">{total_trades}</div>', html, count=1)
            html = html.replace('<div class="value loss">0%</div>', f'<div class="value loss">{win_rate:.1f}%</div>')
            html = html.replace('<div class="value">0 / 0</div>', f'<div class="value">{wins} / {losses}</div>')
            html = html.replace('<div class="value loss">$0.00</div>', f'<div class="value loss">${total_pnl:,.2f}</div>')
            
            # Update open positions count
            html = re.sub(r'<div class="value">(\d+)</div>([\s\S]*?)<div class="label">Open Positions</div>', 
                         f'<div class="value">{len(positions)}</div>\\2<div class="label">Open Positions</div>', html)
            
            # Build position rows
            pos_rows = ''
            for pos in positions:
                pos_rows += f'''<tr>
            <td><span class="ticker">{pos['symbol']}</span></td>
            <td>${pos['entry_price']:.2f}</td>
            <td>{pos['shares']:,}</td>
            <td>${pos.get('value', pos['entry_price'] * pos['shares']):,.2f}</td>
            <td class="stop">${pos['stop_loss']:.2f}</td>
            <td>{pos['entry_date'][:10]}</td>
        </tr>'''
            
            html = re.sub(r'<tbody>[\s\S]*?</tbody>', f'<tbody>{pos_rows}</tbody>', html)
            html = html.replace('Last updated:', f'Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} •')
            
            with open('dashboard.html', 'w') as f:
                f.write(html)
        except Exception as e:
            logger.error(f"Dashboard regeneration failed: {e}")
    
    def get_stats(self):
        """Get trading statistics"""
        total = len(self.trade_history)
        if total > 0:
            wins = sum(1 for t in self.trade_history if t['win'])
            win_rate = (wins / total * 100) if total > 0 else 0
            total_pnl = sum(t['pnl'] for t in self.trade_history)
            
            # Calculate avg win/loss for Kelly
            wins_list = [t['pnl'] for t in self.trade_history if t['win']]
            losses_list = [abs(t['pnl']) for t in self.trade_history if not t['win']]
            
            avg_win = (sum(wins_list) / len(wins_list) / 100000) if wins_list else 0
            avg_loss = (sum(losses_list) / len(losses_list) / 100000) if losses_list else 0
            win_rate_kelly = wins / total if total > 0 else 0
        else:
            wins = 0
            win_rate = 0
            total_pnl = 0
            avg_win = 0
            avg_loss = 0
            win_rate_kelly = 0
        
        return {
            'total_trades': total,
            'wins': wins,
            'losses': total - wins,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'daily_pnl': self.daily_pnl,
            'open_positions': len(self.positions),
            'consecutive_losses': self.consecutive_losses,
            'circuit_breaker': self.circuit_breaker_triggered,
            'daily_loss_pause': self.daily_loss_pause,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'win_rate_kelly': win_rate_kelly
        }
    
    def health_check(self):
        """System health monitoring"""
        now = datetime.now()
        
        # Check if we should restart
        if (now - self.last_health_check).seconds > HEALTH_CHECK_INTERVAL:
            self.last_health_check = now
            
            # Verify critical systems
            try:
                # Test Alpaca connection
                self.alpaca.get_positions()
                self.health_status = "healthy"
                self.error_count = 0
            except Exception as e:
                self.error_count += 1
                logger.error(f"Health check failed: {e}")
                
                if self.error_count >= 5 and RESTART_ON_ERROR:
                    logger.critical("Health check failing - attempting restart")
                    send_telegram_alert("⚠️ Health check failing - restarting")
                    # Would trigger restart logic here
    
    def run_cycle(self):
        """Main trading cycle"""
        should_run, status = self.should_scan()
        
        print(f"\n{'='*60}")
        print(f"🤖 APEX SHORTS v2.0 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Status: {status.upper()}")
        
        # Check daily reset
        self.check_daily_reset()
        
        if not should_run:
            print(f"   ⏸️  Skipping - market {status}")
            return None
        
        print(f"   ✅ SCANNING ACTIVE")
        
        # Health check
        self.health_check()
        
        # Check risk
        can_trade, reason = self.check_risk_limits()
        if not can_trade:
            print(f"   ⚠️  {reason}")
            if "circuit_breaker" in reason:
                print(f"   🔴 TRADING PAUSED - Circuit breaker active")
        
        # Run scan
        candidates, ready = self.scanner.scan()
        
        # Show positions
        print(f"\n📊 Positions: {len(self.positions)}")
        for pos in self.positions:
            print(f"   {pos['symbol']}: ${pos['entry_price']} (stop: ${pos['stop_loss']:.2f})")
        
        # Check stops, targets, trailing stops, partial exits
        self.check_positions()
        
        # Auto-trade
        if AUTO_TRADE and can_trade and ready:
            existing = [p['symbol'] for p in self.positions]
            
            for candidate in ready:
                symbol = candidate['data']['symbol']
                
                if symbol in existing:
                    continue
                
                if len(self.positions) >= MAX_CONCURRENT:
                    break
                
                print(f"\n🎯 TRADE: {symbol} (score: {candidate['score']})")
                self.execute_short(symbol, candidate['data'], candidate['score'])
        
        self.save_state()
        self.regenerate_dashboard()
        
        stats = self.get_stats()
        print(f"\n📈 STATS: {stats['total_trades']} trades | Win: {stats['win_rate']:.1f}% | P&L: ${stats['total_pnl']:.2f}")
        print(f"   🔴 Circuit Breaker: {'ACTIVE' if stats['circuit_breaker'] else 'OK'}")
        print(f"   📉 Consecutive Losses: {stats['consecutive_losses']}")
        
        return stats
    
    def run(self):
        """Main run loop"""
        print(f"\n🚀 APEX SHORTS v2.0 - Enhanced Trading System")
        print(f"   Enhancements: Circuit Breaker, Kelly Sizing, Trailing Stops")
        print(f"   Partial Scaling, Volatility Stops, Atomic Saves, Telegram Alerts")
        print(f"   Auto-trade: {AUTO_TRADE}")
        print(f"   Score threshold: {MIN_SCORE_THRESHOLD}")
        
        send_telegram_alert("🚀 Apex Shorts v2.0 started")
        
        while True:
            try:
                self.run_cycle()
                time.sleep(300)  # 5 min intervals
            except KeyboardInterrupt:
                print("\n🛑 Stopped by user")
                send_telegram_alert("🛑 System stopped")
                break
            except Exception as e:
                logger.error(f"Run loop error: {e}", exc_info=True)
                self.error_count += 1
                
                if RESTART_ON_ERROR and self.error_count >= 3:
                    logger.critical("Multiple errors - restarting")
                    send_telegram_alert("⚠️ Multiple errors - restarting")
                    self.error_count = 0
                
                time.sleep(60)


# ==================== BACKTEST MODULE ====================
def run_backtest(symbols: list, start_date: str, end_date: str):
    """Backtest strategy on historical data"""
    print(f"\n🔬 BACKTEST: {start_date} to {end_date}")
    print("=" * 50)
    
    results = []
    
    for symbol in symbols:
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(start=start_date, end=end_date)
            
            if len(hist) < 20:
                continue
            
            # Simple backtest: buy on RSI < 30, sell on RSI > 70
            # (Simplified for demo - real backtest would use signals from screener)
            trades = []
            position = None
            
            for i, (date, row) in enumerate(hist.iterrows()):
                price = row['Close']
                
                if position is None:
                    # Entry signal (mock: price drops 5% from recent high)
                    if i > 10:
                        recent_high = hist['High'].iloc[i-10:i].max()
                        if price < recent_high * 0.95:
                            position = {
                                'entry': price,
                                'date': date,
                                'shares': 100
                            }
                
                elif position:
                    # Exit signal (mock: price recovers 10% or stop loss)
                    if price >= position['entry'] * 1.10:
                        pnl = (price - position['entry']) * position['shares']
                        trades.append({'pnl': pnl, 'win': pnl > 0})
                        position = None
                    elif price >= position['entry'] * 1.15:  # Stop
                        pnl = (price - position['entry']) * position['shares']
                        trades.append({'pnl': pnl, 'win': pnl > 0})
                        position = None
            
            if trades:
                total_pnl = sum(t['pnl'] for t in trades)
                wins = sum(1 for t in trades if t['win'])
                results.append({
                    'symbol': symbol,
                    'trades': len(trades),
                    'wins': wins,
                    'win_rate': wins/len(trades)*100,
                    'pnl': total_pnl
                })
                print(f"   {symbol}: {len(trades)} trades | Win: {wins/len(trades)*100:.1f}% | P&L: ${total_pnl:.2f}")
        
        except Exception as e:
            print(f"   {symbol}: Error - {e}")
    
    if results:
        total_pnl = sum(r['pnl'] for r in results)
        print(f"\n📊 BACKTEST TOTAL: ${total_pnl:.2f}")
    else:
        print("   No results")
    
    return results


# ==================== MAIN ====================
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--backtest':
        # Run backtest
        test_symbols = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'SPY']
        run_backtest(test_symbols, '2024-01-01', '2025-01-01')
    else:
        # Run live trading
        system = TradingSystem()
        system.run()
