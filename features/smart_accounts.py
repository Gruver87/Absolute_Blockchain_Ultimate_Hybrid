#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
👤 ЧАСТЬ 26: SMART ACCOUNTS - ЯДРО И АБСТРАКЦИЯ
🔐 WATERMARK: DABRANSKI ULADZIMIR PETROVICH | 14.07.1987 | GRODNO

Абстракция аккаунта (Account Abstraction)
Социальный вход, сессионные ключи, оплата комиссий любыми токенами
"""

import hashlib
import time
import json
import secrets
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict
import threading


# ============================================================================
# ТИПЫ АККАУНТОВ И АУТЕНТИФИКАЦИИ
# ============================================================================

class AuthMethod(Enum):
    """Методы аутентификации"""
    PRIVATE_KEY = "private_key"        # Классический приватный ключ
    SOCIAL = "social"                   # Социальный вход (Google/Apple)
    MULTISIG = "multisig"               # Мультиподпись
    SESSION_KEY = "session_key"         # Сессионный ключ
    PASSKEY = "passkey"                 # WebAuthn/Passkey
    BIOMETRIC = "biometric"             # Биометрия (через телефон)
    HARDWARE = "hardware"                # Аппаратный кошелёк


class SessionPermission(Enum):
    """Разрешения для сессионных ключей"""
    BASIC = "basic"                      # Базовые операции
    TRANSFER = "transfer"                 # Только переводы
    SWAP = "swap"                         # Только обмены
    NFT = "nft"                           # Только NFT операции
    GAME = "game"                          # Только игровые действия
    ADMIN = "admin"                        # Административные
    CUSTOM = "custom"                      # Пользовательские


class RecoveryMethod(Enum):
    """Методы восстановления аккаунта"""
    SOCIAL = "social"                      # Через друзей/семью
    EMAIL = "email"                         # Через email
    PHONE = "phone"                         # Через телефон
    MULTISIG = "multisig"                   # Через мультиподпись
    TIME_LOCK = "time_lock"                  # Временная задержка
    GUARDIAN = "guardian"                    # Через хранителей


# ============================================================================
# ДАТАКЛАССЫ
# ============================================================================

@dataclass
class SessionKey:
    """Сессионный ключ для временного доступа"""
    
    id: str
    public_key: str
    permissions: List[SessionPermission]
    expires_at: float
    max_uses: int = 0  # 0 = без ограничений
    uses: int = 0
    created_at: float = field(default_factory=time.time)
    allowed_dapps: List[str] = field(default_factory=list)  # Ограничение по dApps
    
    def is_valid(self) -> bool:
        """Проверка валидности сессионного ключа"""
        if time.time() > self.expires_at:
            return False
        
        if self.max_uses > 0 and self.uses >= self.max_uses:
            return False
        
        return True
    
    def use(self):
        """Использование ключа"""
        self.uses += 1
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id[:8],
            'permissions': [p.value for p in self.permissions],
            'expires': self.expires_at,
            'uses': f"{self.uses}/{self.max_uses if self.max_uses else '∞'}"
        }

@dataclass
class SocialLogin:
    """Социальный вход"""
    
    provider: str  # google, apple, twitter
    provider_id: str
    email: str
    name: str
    avatar: Optional[str] = None
    verified: bool = False
    linked_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            'provider': self.provider,
            'email': self.email,
            'name': self.name,
            'verified': self.verified
        }


@dataclass
class Guardian:
    """Хранитель для восстановления аккаунта"""
    
    address: str
    name: str
    weight: int = 1  # Вес голоса
    approved: bool = False
    added_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            'address': self.address[:8] + '...',
            'name': self.name,
            'weight': self.weight
        }


@dataclass
class RecoveryRequest:
    """Запрос на восстановление аккаунта"""
    
    id: str
    account: str
    requested_by: str
    expires_at: float  # ← ПЕРЕНЕСЕНО НАВЕРХ!
    guardians_approved: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    status: str = "pending"
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id[:8],
            'account': self.account[:8] + '...',
            'approvals': len(self.guardians_approved),
            'expires': self.expires_at,
            'status': self.status
        }


# ============================================================================
# СМАРТ-АККАУНТ
# ============================================================================

class SmartAccount:
    """
    Умный аккаунт с поддержкой абстракции
    """
    
    def __init__(self, address: str, owner: str):
        self.address = address
        self.owner = owner  # Основной владелец
        self.created_at = time.time()
        
        # Методы аутентификации
        self.auth_methods: Dict[AuthMethod, Any] = {}
        self.primary_method: AuthMethod = AuthMethod.PRIVATE_KEY
        
        # Сессионные ключи
        self.session_keys: Dict[str, SessionKey] = {}
        
        # Социальные логины
        self.social_logins: Dict[str, SocialLogin] = {}
        
        # Хранители для восстановления
        self.guardians: Dict[str, Guardian] = {}
        self.recovery_requests: Dict[str, RecoveryRequest] = {}
        self.recovery_threshold: int = 2  # Сколько хранителей нужно
        
        # Настройки
        self.settings: Dict = {
            'auto_approve_dapps': [],  # Автоматическое одобрение dApps
            'daily_limit': 10000,       # Дневной лимит
            'max_fee': 0.01,             # Максимальная комиссия
            'notifications': True         # Уведомления
        }
        
        # Статистика
        self.stats = {
            'total_transactions': 0,
            'total_volume': 0.0,
            'active_sessions': 0,
            'last_active': time.time()
        }
        
    # ------------------------------------------------------------------------
    # Аутентификация
    # ------------------------------------------------------------------------
    
    def add_auth_method(self, method: AuthMethod, data: Any) -> bool:
        """Добавление метода аутентификации"""
        self.auth_methods[method] = data
        return True
    
    def remove_auth_method(self, method: AuthMethod) -> bool:
        """Удаление метода аутентификации"""
        if method in self.auth_methods:
            del self.auth_methods[method]
            return True
        return False
    
    def authenticate(self, method: AuthMethod, credential: Any) -> bool:
        """Аутентификация через указанный метод"""
        
        if method not in self.auth_methods:
            return False
        
        if method == AuthMethod.PRIVATE_KEY:
            return self._verify_private_key(credential)
        elif method == AuthMethod.SESSION_KEY:
            return self._verify_session_key(credential)
        elif method == AuthMethod.SOCIAL:
            return self._verify_social(credential)
        elif method == AuthMethod.PASSKEY:
            return self._verify_passkey(credential)
        
        return False
    
    def _verify_private_key(self, signature: str) -> bool:
        """Private-key auth requires a real signature verifier."""
        return False
    
    def _verify_session_key(self, key_id: str) -> bool:
        """Проверка сессионного ключа"""
        if key_id not in self.session_keys:
            return False
        
        key = self.session_keys[key_id]
        return key.is_valid()
    
    def _verify_social(self, token: str) -> bool:
        """Social auth requires external provider/JWT verification."""
        return False
    
    def _verify_passkey(self, assertion: Dict) -> bool:
        """Passkey auth requires WebAuthn assertion verification."""
        return False
    
    # ------------------------------------------------------------------------
    # Сессионные ключи
    # ------------------------------------------------------------------------
    
    def create_session_key(
        self,
        permissions: List[SessionPermission],
        expires_in: int = 3600,  # 1 час
        max_uses: int = 0,
        allowed_dapps: Optional[List[str]] = None
    ) -> str:
        """Создание сессионного ключа"""
        
        key_id = hashlib.sha256(
            f"{self.address}{time.time()}{secrets.token_hex(8)}".encode()
        ).hexdigest()[:16]
        
        # Генерируем ключевую пару (упрощённо)
        public_key = hashlib.sha256(f"session_{key_id}".encode()).hexdigest()
        
        key = SessionKey(
            id=key_id,
            public_key=public_key,
            permissions=permissions,
            expires_at=time.time() + expires_in,
            max_uses=max_uses,
            allowed_dapps=allowed_dapps or []
        )
        
        self.session_keys[key_id] = key
        self.stats['active_sessions'] += 1
        
        return key_id
    
    def revoke_session_key(self, key_id: str) -> bool:
        """Отзыв сессионного ключа"""
        if key_id in self.session_keys:
            del self.session_keys[key_id]
            self.stats['active_sessions'] -= 1
            return True
        return False
    
    def get_session_keys(self) -> List[Dict]:
        """Получение всех активных сессионных ключей"""
        valid_keys = []
        for key in self.session_keys.values():
            if key.is_valid():
                valid_keys.append(key.to_dict())
        return valid_keys
    
    # ------------------------------------------------------------------------
    # Социальный вход
    # ------------------------------------------------------------------------
    
    def link_social_account(
        self,
        provider: str,
        provider_id: str,
        email: str,
        name: str,
        avatar: Optional[str] = None
    ) -> bool:
        """Привязка социального аккаунта"""
        
        social = SocialLogin(
            provider=provider,
            provider_id=provider_id,
            email=email,
            name=name,
            avatar=avatar
        )
        
        self.social_logins[provider] = social
        self.auth_methods[AuthMethod.SOCIAL] = provider
        
        return True
    
    def unlink_social_account(self, provider: str) -> bool:
        """Отвязка социального аккаунта"""
        if provider in self.social_logins:
            del self.social_logins[provider]
            return True
        return False
    
    def get_social_logins(self) -> List[Dict]:
        """Получение всех привязанных социальных аккаунтов"""
        return [s.to_dict() for s in self.social_logins.values()]
    
    # ------------------------------------------------------------------------
    # Хранители и восстановление
    # ------------------------------------------------------------------------
    
    def add_guardian(self, address: str, name: str, weight: int = 1) -> bool:
        """Добавление хранителя"""
        
        if address in self.guardians:
            return False
        
        guardian = Guardian(
            address=address,
            name=name,
            weight=weight
        )
        
        self.guardians[address] = guardian
        return True
    
    def remove_guardian(self, address: str) -> bool:
        """Удаление хранителя"""
        if address in self.guardians:
            del self.guardians[address]
            return True
        return False
    
    def approve_guardian(self, address: str, approver: str) -> bool:
        """Подтверждение хранителя (владельцем)"""
        if address not in self.guardians or approver != self.owner:
            return False
        
        self.guardians[address].approved = True
        return True
    
    def request_recovery(self, requested_by: str) -> Optional[str]:
        """Запрос на восстановление аккаунта"""
        
        if requested_by not in self.guardians:
            return None
        
        request_id = hashlib.sha256(
            f"{self.address}{requested_by}{time.time()}{secrets.token_hex(4)}".encode()
        ).hexdigest()[:16]
        
        request = RecoveryRequest(
            id=request_id,
            account=self.address,
            requested_by=requested_by,
            expires_at=time.time() + 86400 * 7  # 7 дней
        )
        
        self.recovery_requests[request_id] = request
        return request_id
    
    def approve_recovery(self, request_id: str, guardian: str) -> bool:
        """Одобрение восстановления хранителем"""
        
        if request_id not in self.recovery_requests:
            return False
        
        if guardian not in self.guardians:
            return False
        
        request = self.recovery_requests[request_id]
        
        if guardian not in request.guardians_approved:
            request.guardians_approved.append(guardian)
        
        # Проверяем, достаточно ли одобрений
        total_weight = sum(self.guardians[g].weight for g in request.guardians_approved)
        required_weight = sum(g.weight for g in self.guardians.values()) // 2
        
        if total_weight >= required_weight:
            request.status = "approved"
        
        return True
    
    def execute_recovery(self, request_id: str, new_owner: str) -> bool:
        """Исполнение восстановления (смена владельца)"""
        
        if request_id not in self.recovery_requests:
            return False
        
        request = self.recovery_requests[request_id]
        
        if request.status != "approved":
            return False
        
        if time.time() > request.expires_at:
            return False
        
        # Меняем владельца
        self.owner = new_owner
        request.status = "executed"
        
        return True
    
    # ------------------------------------------------------------------------
    # Транзакции с проверкой прав
    # ------------------------------------------------------------------------
    
    def execute_transaction(
        self,
        to: str,
        value: float,
        data: Optional[Dict] = None,
        auth_method: AuthMethod = AuthMethod.PRIVATE_KEY,
        credential: Any = None
    ) -> Optional[Dict]:
        """Исполнение транзакции с проверкой аутентификации"""
        
        # Проверяем аутентификацию
        if not self.authenticate(auth_method, credential):
            return None
        
        # Для сессионных ключей проверяем разрешения
        if auth_method == AuthMethod.SESSION_KEY:
            key = self.session_keys.get(credential)
            if not key or SessionPermission.TRANSFER not in key.permissions:
                return None
        
        # Проверяем дневной лимит
        if value > self.settings['daily_limit']:
            return None
        
        # Создаём транзакцию (упрощённо)
        tx = {
            'id': hashlib.sha256(f"{self.address}{to}{value}{time.time()}".encode()).hexdigest()[:16],
            'from': self.address,
            'to': to,
            'value': value,
            'data': data,
            'auth_method': auth_method.value,
            'timestamp': time.time()
        }
        
        # Обновляем статистику
        self.stats['total_transactions'] += 1
        self.stats['total_volume'] += value
        self.stats['last_active'] = time.time()
        
        return tx
    
    def execute_batch(
        self,
        transactions: List[Dict],
        auth_method: AuthMethod,
        credential: Any
    ) -> List[Dict]:
        """Пакетное исполнение транзакций"""
        
        results = []
        for tx in transactions:
            result = self.execute_transaction(
                to=tx['to'],
                value=tx['value'],
                data=tx.get('data'),
                auth_method=auth_method,
                credential=credential
            )
            results.append(result)
        
        return results
    
    # ------------------------------------------------------------------------
    # Настройки
    # ------------------------------------------------------------------------
    
    def update_settings(self, new_settings: Dict) -> bool:
        """Обновление настроек аккаунта"""
        self.settings.update(new_settings)
        return True
    
    def get_settings(self) -> Dict:
        """Получение настроек"""
        return self.settings.copy()
    
    # ------------------------------------------------------------------------
    # Информация
    # ------------------------------------------------------------------------
    
    def get_info(self) -> Dict:
        """Полная информация об аккаунте"""
        
        return {
            'address': self.address[:16] + '...',
            'owner': self.owner[:16] + '...',
            'created': self.created_at,
            'auth_methods': [m.value for m in self.auth_methods.keys()],
            'primary': self.primary_method.value,
            'social_logins': len(self.social_logins),
            'session_keys': len(self.get_session_keys()),
            'guardians': len(self.guardians),
            'settings': self.settings,
            'stats': self.stats
        }


# ============================================================================
# ФАБРИКА СМАРТ-АККАУНТОВ
# ============================================================================

class SmartAccountFactory:
    """
    Фабрика для создания умных аккаунтов
    """
    
    @staticmethod
    def create_with_private_key(address: str, private_key: str) -> SmartAccount:
        """Создание аккаунта с приватным ключом"""
        
        account = SmartAccount(address, address)
        account.add_auth_method(AuthMethod.PRIVATE_KEY, private_key)
        return account
    
    @staticmethod
    def create_with_social(
        address: str,
        provider: str,
        provider_id: str,
        email: str,
        name: str
    ) -> SmartAccount:
        """Создание аккаунта с социальным входом"""
        
        account = SmartAccount(address, address)
        account.link_social_account(provider, provider_id, email, name)
        account.primary_method = AuthMethod.SOCIAL
        return account
    
    @staticmethod
    def create_with_guardians(
        address: str,
        owner: str,
        guardians: List[tuple]  # (address, name, weight)
    ) -> SmartAccount:
        """Создание аккаунта с хранителями"""
        
        account = SmartAccount(address, owner)
        
        for g_addr, g_name, g_weight in guardians:
            account.add_guardian(g_addr, g_name, g_weight)
            account.approve_guardian(g_addr, owner)
        
        return account
    
    @staticmethod
    def create_with_session_keys(
        address: str,
        session_keys: List[Dict]
    ) -> SmartAccount:
        """Создание аккаунта с предустановленными сессионными ключами"""
        
        account = SmartAccount(address, address)
        
        for key_config in session_keys:
            account.create_session_key(
                permissions=key_config['permissions'],
                expires_in=key_config.get('expires_in', 3600),
                max_uses=key_config.get('max_uses', 0)
            )
        
        return account


# ============================================================================
# МЕНЕДЖЕР СМАРТ-АККАУНТОВ
# ============================================================================

class SmartAccountManager:
    """
    Менеджер для управления всеми умными аккаунтами
    """
    
    def __init__(self):
        self.accounts: Dict[str, SmartAccount] = {}
        self.address_index: Dict[str, str] = {}  # address -> account_id
        
    def register_account(self, account: SmartAccount) -> str:
        """Регистрация аккаунта"""
        
        account_id = hashlib.sha256(
            f"{account.address}{time.time()}{secrets.token_hex(4)}".encode()
        ).hexdigest()[:16]
        
        self.accounts[account_id] = account
        self.address_index[account.address] = account_id
        
        return account_id
    
    def get_account(self, identifier: str) -> Optional[SmartAccount]:
        """Получение аккаунта по ID или адресу"""
        
        if identifier in self.accounts:
            return self.accounts[identifier]
        
        if identifier in self.address_index:
            return self.accounts.get(self.address_index[identifier])
        
        return None
    
    def get_accounts_by_owner(self, owner: str) -> List[SmartAccount]:
        """Получение всех аккаунтов владельца"""
        
        return [acc for acc in self.accounts.values() if acc.owner == owner]
    
    def delete_account(self, account_id: str, owner: str) -> bool:
        """Удаление аккаунта"""
        
        if account_id not in self.accounts:
            return False
        
        account = self.accounts[account_id]
        
        if account.owner != owner:
            return False
        
        del self.accounts[account_id]
        if account.address in self.address_index:
            del self.address_index[account.address]
        
        return True
    
    def recover_account(self, identifier: str, new_owner: str, guardians: List[str]) -> bool:
        """Guardian quorum recovery — request, approve, execute."""
        account = self.get_account(identifier)
        if not account or not new_owner or not guardians:
            return False
        request_id = None
        for guardian in guardians:
            request_id = account.request_recovery(guardian) or request_id
            if request_id:
                account.approve_recovery(request_id, guardian)
        if not request_id:
            return False
        return account.execute_recovery(request_id, new_owner)

    def get_stats(self) -> Dict:
        """Статистика по всем аккаунтам"""
        
        total_accounts = len(self.accounts)
        total_volume = sum(acc.stats['total_volume'] for acc in self.accounts.values())
        total_txs = sum(acc.stats['total_transactions'] for acc in self.accounts.values())
        
        auth_counts = defaultdict(int)
        for acc in self.accounts.values():
            for method in acc.auth_methods.keys():
                auth_counts[method.value] += 1
        
        return {
            'total_accounts': total_accounts,
            'total_transactions': total_txs,
            'total_volume': total_volume,
            'auth_methods': dict(auth_counts),
            'active_sessions': sum(acc.stats['active_sessions'] for acc in self.accounts.values())
        }