#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚡ ЧАСТЬ 22: AI AGENT FRAMEWORK - ТОРГОВЫЕ АГЕНТЫ
🔐 WATERMARK: DABRANSKI ULADZIMIR PETROVICH | 14.07.1987 | GRODNO

Специализированные агенты для торговли и управления ликвидностью
"""

import time
import math
import random
from typing import Dict, List, Optional, Tuple
import numpy as np

from Новый22ч1 import (
    AIAgent, AgentType, AgentCapability, AgentRiskLevel,
    AgentState, AgentPersonality, AgentIdentity
)


# ============================================================================
# ТОРГОВЫЙ АГЕНТ (Trading Agent)
# ============================================================================

class TradingAgent(AIAgent):
    """
    Агент для автоматической торговли на DEX
    Использует технический анализ и машинное обучение
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.strategies = []
        self.positions = {}
        self.orders = []
        self.performance = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'avg_hold_time': 0.0
        }
        self.price_history = []
        self.indicators = {}
        
    def add_strategy(self, strategy: Dict):
        """Добавление торговой стратегии"""
        self.strategies.append(strategy)
        
    def _think_and_act(self):
        """Основной цикл торгового агента"""
        
        # 1. Анализ рынка
        market_data = self._analyze_market_data()
        
        # 2. Генерация сигналов
        signals = self._generate_signals(market_data)
        
        # 3. Исполнение сделок
        for signal in signals:
            self._execute_signal(signal)
        
        # 4. Управление рисками
        self._risk_management()
        
        # 5. Обновление статистики
        self._update_performance()
    
    def _analyze_market_data(self) -> Dict:
        """Анализ рыночных данных"""
        
        # В реальности здесь будет подключение к DEX/API
        # Для примера генерируем случайные данные
        
        data = {
            'timestamp': time.time(),
            'prices': {
                'ΨQC/BTC': random.uniform(0.0001, 0.0002),
                'ΨQC/ETH': random.uniform(0.001, 0.002),
                'ΨQC/USDT': random.uniform(0.5, 1.5)
            },
            'volumes': {
                'ΨQC/BTC': random.uniform(1000, 10000),
                'ΨQC/ETH': random.uniform(1000, 10000),
                'ΨQC/USDT': random.uniform(1000, 10000)
            },
            'order_books': {},
            'volatility': random.uniform(0.01, 0.05)
        }
        
        # Сохраняем в историю
        self.price_history.append(data)
        if len(self.price_history) > 1000:
            self.price_history = self.price_history[-1000:]
        
        return data
    
    def _generate_signals(self, market_data: Dict) -> List[Dict]:
        """Генерация торговых сигналов на основе стратегий"""
        signals = []
        
        for strategy in self.strategies:
            # Проверяем условия стратегии
            if self._check_strategy_conditions(strategy, market_data):
                signal = {
                    'type': strategy.get('type', 'buy'),
                    'pair': strategy.get('pair', 'ΨQC/BTC'),
                    'amount': self._calculate_position_size(strategy, market_data),
                    'price': market_data['prices'].get(strategy.get('pair', 'ΨQC/BTC'), 0),
                    'strategy_id': strategy.get('id'),
                    'confidence': self._calculate_confidence(strategy, market_data)
                }
                
                # Проверяем порог уверенности
                if signal['confidence'] >= self.personality.confidence_threshold:
                    signals.append(signal)
        
        return signals
    
    def _check_strategy_conditions(self, strategy: Dict, market_data: Dict) -> bool:
        """Проверка условий стратегии"""
        
        strategy_type = strategy.get('type')
        
        if strategy_type == 'moving_average_cross':
            # Стратегия пересечения скользящих средних
            fast_ma = self._calculate_ma(strategy.get('fast_period', 10))
            slow_ma = self._calculate_ma(strategy.get('slow_period', 30))
            
            if fast_ma > slow_ma:
                return True
        
        elif strategy_type == 'rsi':
            # RSI стратегия
            rsi = self._calculate_rsi(strategy.get('period', 14))
            oversold = strategy.get('oversold', 30)
            overbought = strategy.get('overbought', 70)
            
            if rsi < oversold:
                return True  # Перепроданность - сигнал к покупке
            elif rsi > overbought:
                return True  # Перекупленность - сигнал к продаже
        
        elif strategy_type == 'breakout':
            # Стратегия пробоя уровней
            resistance = strategy.get('resistance', 0)
            support = strategy.get('support', 0)
            current_price = market_data['prices'].get(strategy.get('pair', 'ΨQC/BTC'), 0)
            
            if current_price > resistance:
                return True
            elif current_price < support:
                return True
        
        return False
    
    def _calculate_position_size(self, strategy: Dict, market_data: Dict) -> float:
        """Расчёт размера позиции с учётом риск-менеджмента"""
        
        base_size = strategy.get('base_size', 100)
        
        # Корректировка на волатильность
        volatility = market_data.get('volatility', 0.02)
        vol_factor = 1.0 / (1.0 + volatility * 10)
        
        # Корректировка на уверенность
        confidence = self._calculate_confidence(strategy, market_data)
        
        # Корректировка на риск-профиль
        risk_factors = {
            AgentRiskLevel.CONSERVATIVE: 0.5,
            AgentRiskLevel.MODERATE: 1.0,
            AgentRiskLevel.AGGRESSIVE: 2.0,
            AgentRiskLevel.YOLO: 5.0
        }
        risk_factor = risk_factors.get(self.personality.risk_level, 1.0)
        
        # Итоговый размер
        position_size = base_size * vol_factor * confidence * risk_factor
        
        # Проверка лимитов
        max_size = self.personality.max_position_size
        position_size = min(position_size, max_size)
        
        # Проверка баланса
        balance = self.state.balance.get('ΨQC', 0)
        position_size = min(position_size, balance * 0.1)  # Не больше 10% баланса
        
        return position_size
    
    def _calculate_confidence(self, strategy: Dict, market_data: Dict) -> float:
        """Расчёт уверенности в сигнале"""
        
        base_confidence = strategy.get('base_confidence', 0.7)
        
        # Корректировка на волатильность
        volatility = market_data.get('volatility', 0.02)
        vol_penalty = min(volatility * 5, 0.3)
        
        # Корректировка на историческую успешность
        historical_success = self._get_strategy_success_rate(strategy.get('id'))
        success_bonus = (historical_success - 0.5) * 0.2
        
        # Корректировка на объём
        volume = market_data['volumes'].get(strategy.get('pair', 'ΨQC/BTC'), 0)
        volume_factor = min(volume / 5000, 1.0)
        
        confidence = base_confidence - vol_penalty + success_bonus
        confidence = max(0.1, min(0.99, confidence))
        
        return confidence
    
    def _execute_signal(self, signal: Dict):
        """Исполнение торгового сигнала"""
        
        # Проверяем, нет ли уже такой позиции
        pair = signal['pair']
        if pair in self.positions:
            # Уже есть позиция - возможно, увеличиваем
            self._add_to_position(pair, signal)
        else:
            # Открываем новую позицию
            self._open_position(signal)
    
    def _open_position(self, signal: Dict):
        """Открытие новой позиции"""
        
        position = {
            'id': hashlib.sha256(f"{signal}{time.time()}".encode()).hexdigest()[:16],
            'pair': signal['pair'],
            'type': signal['type'],
            'amount': signal['amount'],
            'entry_price': signal['price'],
            'current_price': signal['price'],
            'stop_loss': signal['price'] * (1 - self.personality.stop_loss) if self.personality.stop_loss else None,
            'take_profit': signal['price'] * (1 + self.personality.take_profit) if self.personality.take_profit else None,
            'timestamp': time.time(),
            'strategy_id': signal.get('strategy_id'),
            'status': 'open'
        }
        
        self.positions[signal['pair']] = position
        
        # Уменьшаем баланс
        cost = signal['amount'] * signal['price']
        current_balance = self.state.balance.get('ΨQC', 0)
        self.state.balance['ΨQC'] = current_balance - cost
        
        # Логируем
        self.state.history.append({
            'timestamp': time.time(),
            'type': 'open_position',
            'position': position
        })
        
        self.state.total_trades += 1
    
    def _add_to_position(self, pair: str, signal: Dict):
        """Добавление к существующей позиции (усреднение)"""
        
        position = self.positions[pair]
        
        # Рассчитываем новую среднюю цену
        total_amount = position['amount'] + signal['amount']
        total_cost = (position['amount'] * position['entry_price'] + 
                     signal['amount'] * signal['price'])
        
        position['amount'] = total_amount
        position['entry_price'] = total_cost / total_amount
        position['current_price'] = signal['price']
        
        # Уменьшаем баланс
        cost = signal['amount'] * signal['price']
        self.state.balance['ΨQC'] -= cost
    
    def _close_position(self, pair: str, price: float, reason: str = "signal"):
        """Закрытие позиции"""
        
        if pair not in self.positions:
            return
        
        position = self.positions[pair]
        
        # Расчёт P&L
        pnl = position['amount'] * (price - position['entry_price'])
        if position['type'] == 'sell':
            pnl = -pnl  # Для шорт-позиций
        
        # Обновляем баланс
        self.state.balance['ΨQC'] += position['amount'] * price
        
        # Обновляем статистику
        self.state.total_pnl += pnl
        self.state.total_volume += position['amount'] * price
        
        if pnl > 0:
            self.performance['winning_trades'] += 1
        else:
            self.performance['losing_trades'] += 1
        
        # Логируем
        self.state.history.append({
            'timestamp': time.time(),
            'type': 'close_position',
            'position_id': position['id'],
            'pnl': pnl,
            'reason': reason
        })
        
        # Удаляем позицию
        del self.positions[pair]
    
    def _risk_management(self):
        """Управление рисками"""
        
        current_time = time.time()
        
        for pair, position in list(self.positions.items()):
            # Проверка стоп-лосса
            if position['stop_loss']:
                if position['type'] == 'buy':
                    if position['current_price'] <= position['stop_loss']:
                        self._close_position(pair, position['current_price'], "stop_loss")
                        continue
                else:
                    if position['current_price'] >= position['stop_loss']:
                        self._close_position(pair, position['current_price'], "stop_loss")
                        continue
            
            # Проверка тейк-профита
            if position['take_profit']:
                if position['type'] == 'buy':
                    if position['current_price'] >= position['take_profit']:
                        self._close_position(pair, position['current_price'], "take_profit")
                        continue
                else:
                    if position['current_price'] <= position['take_profit']:
                        self._close_position(pair, position['current_price'], "take_profit")
                        continue
            
            # Проверка максимального времени удержания
            max_hold = 86400 * 7  # 7 дней
            if current_time - position['timestamp'] > max_hold:
                self._close_position(pair, position['current_price'], "timeout")
    
    def _update_performance(self):
        """Обновление метрик производительности"""
        
        total_trades = self.performance['winning_trades'] + self.performance['losing_trades']
        if total_trades > 0:
            self.state.win_rate = self.performance['winning_trades'] / total_trades
        
        self.state.total_pnl = self.performance['total_pnl']
    
    def _calculate_ma(self, period: int) -> float:
        """Расчёт скользящей средней"""
        if len(self.price_history) < period:
            return 0
        
        prices = [h['prices'].get('ΨQC/BTC', 0) for h in self.price_history[-period:]]
        return sum(prices) / period
    
    def _calculate_rsi(self, period: int) -> float:
        """Расчёт RSI (Relative Strength Index)"""
        if len(self.price_history) < period + 1:
            return 50
        
        gains = []
        losses = []
        
        for i in range(1, period + 1):
            change = (self.price_history[-i]['prices'].get('ΨQC/BTC', 0) - 
                     self.price_history[-i-1]['prices'].get('ΨQC/BTC', 0))
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _get_strategy_success_rate(self, strategy_id: str) -> float:
        """Получение исторической успешности стратегии"""
        
        # Анализ истории сделок по стратегии
        strategy_trades = [
            h for h in self.state.history 
            if h.get('type') == 'close_position' and h.get('strategy_id') == strategy_id
        ]
        
        if not strategy_trades:
            return 0.5  # По умолчанию 50%
        
        winning = [t for t in strategy_trades if t.get('pnl', 0) > 0]
        return len(winning) / len(strategy_trades)
    
    def get_portfolio_value(self) -> float:
        """Расчёт общей стоимости портфеля"""
        
        total = self.state.balance.get('ΨQC', 0)
        
        # Добавляем стоимость открытых позиций
        for position in self.positions.values():
            total += position['amount'] * position['current_price']
        
        return total


# ============================================================================
# АГЕНТ-ПОСТАВЩИК ЛИКВИДНОСТИ
# ============================================================================

class LiquidityProviderAgent(AIAgent):
    """
    Агент для предоставления ликвидности в пулы DEX
    Оптимизирует доходность от комиссий
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.liquidity_positions = {}
        self.strategies = []
        self.impermanent_loss_history = []
        
    def add_liquidity(self, pool_id: str, amount0: float, amount1: float):
        """Добавление ликвидности в пул"""
        
        position = {
            'pool_id': pool_id,
            'amount0': amount0,
            'amount1': amount1,
            'timestamp': time.time(),
            'fees_earned': 0.0,
            'status': 'active'
        }
        
        self.liquidity_positions[pool_id] = position
        
        # Уменьшаем баланс
        self.state.balance['ΨQC'] = self.state.balance.get('ΨQC', 0) - (amount0 + amount1)
    
    def remove_liquidity(self, pool_id: str, percentage: float = 100):
        """Изъятие ликвидности из пула"""
        
        if pool_id not in self.liquidity_positions:
            return False
        
        position = self.liquidity_positions[pool_id]
        
        # Расчёт полученных средств (упрощённо)
        returned = (position['amount0'] + position['amount1']) * (percentage / 100)
        fees = position['fees_earned'] * (percentage / 100)
        
        # Обновляем баланс
        self.state.balance['ΨQC'] = self.state.balance.get('ΨQC', 0) + returned + fees
        
        if percentage >= 99.9:
            del self.liquidity_positions[pool_id]
        else:
            position['amount0'] *= (1 - percentage/100)
            position['amount1'] *= (1 - percentage/100)
            position['fees_earned'] -= fees
        
        return returned + fees
    
    def _think_and_act(self):
        """Основной цикл LP агента"""
        
        # Анализ доходности пулов
        yields = self._analyze_pool_yields()
        
        # Ребалансировка позиций
        self._rebalance_positions(yields)
        
        # Сбор накопленных комиссий
        self._collect_fees()
    
    def _analyze_pool_yields(self) -> Dict[str, float]:
        """Анализ доходности пулов"""
        
        yields = {}
        
        for pool_id, position in self.liquidity_positions.items():
            # В реальности здесь расчёт APY на основе объёмов
            apy = random.uniform(5, 50)  # 5-50% годовых
            yields[pool_id] = apy
        
        return yields
    
    def _rebalance_positions(self, yields: Dict[str, float]):
        """Ребалансировка позиций на основе доходности"""
        
        # Находим пулы с доходностью ниже порога
        threshold = 10  # 10% годовых
        
        for pool_id, apy in yields.items():
            if apy < threshold:
                # Частично выводим из низкодоходных пулов
                self.remove_liquidity(pool_id, 50)
        
        # Здесь можно добавить логику для входа в новые пулы
    
    def _collect_fees(self):
        """Сбор накопленных комиссий"""
        
        for pool_id, position in self.liquidity_positions.items():
            # В реальности здесь запрос к DEX
            fees_earned = random.uniform(0, 10)
            position['fees_earned'] += fees_earned
            
            self.state.history.append({
                'timestamp': time.time(),
                'type': 'fee_collection',
                'pool_id': pool_id,
                'amount': fees_earned
            })
    
    def calculate_impermanent_loss(self, pool_id: str, price_change: float) -> float:
        """Расчёт непостоянных потерь"""
        
        # Формула IL = 2√(r)/(1+r) - 1, где r - изменение цены
        if price_change == 0:
            return 0
        
        r = 1 + price_change
        il = 2 * math.sqrt(r) / (1 + r) - 1
        
        return il