#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Event Bus - Core messaging backbone"""

import threading
import time
from typing import Callable, Dict, List, Any
from collections import defaultdict
from datetime import datetime

class EventBus:
    """
    Global event bus - single source of truth for all communications
    All components subscribe and emit events here
    """
    
    def __init__(self):
        self.listeners: Dict[str, List[Callable]] = defaultdict(list)
        self.event_history: List[Dict] = []
        self.lock = threading.RLock()
        
    def on(self, event: str, callback: Callable) -> None:
        """Subscribe to an event"""
        with self.lock:
            self.listeners[event].append(callback)
            print(f"[EventBus] Subscribed: {callback.__name__} -> {event}")
    
    def emit(self, event: str, data: Any = None) -> None:
        """Emit an event to all subscribers"""
        with self.lock:
            # Log event
            event_log = {
                "event": event,
                "timestamp": time.time(),
                "data": str(data)[:200] if data else None
            }
            self.event_history.append(event_log)
            
            # Keep last 1000 events
            if len(self.event_history) > 1000:
                self.event_history = self.event_history[-1000:]
            
            # Notify subscribers
            if event in self.listeners:
                for callback in self.listeners[event]:
                    try:
                        callback(data)
                    except Exception as e:
                        print(f"[EventBus] Error in {callback.__name__}: {e}")
    
    def get_history(self, limit: int = 100) -> List[Dict]:
        """Get recent events"""
        with self.lock:
            return self.event_history[-limit:]
    
    def clear(self) -> None:
        """Clear all listeners (for testing)"""
        with self.lock:
            self.listeners.clear()
            self.event_history.clear()

# Global instance
bus = EventBus()
