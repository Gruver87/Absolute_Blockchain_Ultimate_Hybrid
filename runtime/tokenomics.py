#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Absolute Blockchain — токеномика ABS.
221 000 000 монет, 17.4% основателю (D.U.P. / Uladzimir Dabranski).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ── Константы эмиссии ────────────────────────────────────────────────────────
MAX_SUPPLY_ABS: int = 221_000_000
FOUNDER_PERCENT: float = 17.4
FOUNDER_AMOUNT_ABS: float = round(MAX_SUPPLY_ABS * FOUNDER_PERCENT / 100, 6)  # 38_454_000

# ── Данные основателя ────────────────────────────────────────────────────────
FOUNDER_FULL_NAME: str = "Uladzimir Dabranski"
FOUNDER_INITIALS: str = "D.U.P."          # Dabranski Uladzimir Petrovich
FOUNDER_ALIAS: str = "Gruver87"
FOUNDER_BIRTHDATE: str = "1987-07-14"
FOUNDER_CITY: str = "Grodno"
FOUNDER_EMAIL: str = "gruverpetrov@gmail.com"
FOUNDER_GITHUB: str = "https://github.com/Gruver87/absolute-blockchain-ultimate"

# Адрес основателя (из data/wallet.json, можно переопределить в config)
DEFAULT_FOUNDER_ADDRESS: str = "0xbeb0962327d6f0ad8de263bd883bb184e88744a2"


@dataclass
class AllocationPool:
    """Один пул распределения монет."""
    id: str
    name: str
    percent: float
    amount_abs: float
    address_key: str          # ключ в genesis_alloc dict
    description: str
    locked: bool = False      # заблокирован до условия
    release_type: str = "genesis"  # genesis | mining | staking


def build_allocations(founder_address: Optional[str] = None) -> List[AllocationPool]:
    """
    Полное распределение 221M ABS:
      17.4% — основатель D.U.P. (genesis, сразу)
      10.0% — экосистема / разработка (genesis)
      10.0% — казначейство сообщества (genesis)
      12.6% — стейкинг-пул (genesis, разблокируется по эпохам)
      50.0% — майнинг-эмиссия (блок-награды до max supply)
    """
    founder_addr = founder_address or DEFAULT_FOUNDER_ADDRESS
    pools = [
        AllocationPool(
            id="founder",
            name="Founder Allocation (D.U.P.)",
            percent=FOUNDER_PERCENT,
            amount_abs=FOUNDER_AMOUNT_ABS,
            address_key=founder_addr,
            description=f"Основатель {FOUNDER_FULL_NAME} ({FOUNDER_INITIALS}) — 17.4% от 221M ABS",
            locked=False,
            release_type="genesis",
        ),
        AllocationPool(
            id="ecosystem",
            name="Ecosystem & Development",
            percent=10.0,
            amount_abs=MAX_SUPPLY_ABS * 0.10,
            address_key="0xecosystem000000000000000000000000000001",
            description="Фонд развития экосистемы, гранты, dApps",
            locked=True,
            release_type="genesis",
        ),
        AllocationPool(
            id="treasury",
            name="Community Treasury",
            percent=10.0,
            amount_abs=MAX_SUPPLY_ABS * 0.10,
            address_key="0xtreasury00000000000000000000000000001",
            description="Казначейство сообщества, DAO-голосования",
            locked=True,
            release_type="genesis",
        ),
        AllocationPool(
            id="staking",
            name="Staking Rewards Pool",
            percent=12.6,
            amount_abs=MAX_SUPPLY_ABS * 0.126,
            address_key="0xstaking0000000000000000000000000000001",
            description="Награды стейкерам, разблокировка по эпохам",
            locked=True,
            release_type="staking",
        ),
        AllocationPool(
            id="mining",
            name="Mining Emission",
            percent=50.0,
            amount_abs=MAX_SUPPLY_ABS * 0.50,
            address_key="mining_pool",
            description="Блок-награды майнерам/валидаторам до достижения max supply",
            locked=False,
            release_type="mining",
        ),
    ]
    return pools


def genesis_balances(founder_address: Optional[str] = None) -> Dict[str, int]:
    """
    Балансы, начисляемые в genesis-блоке (только genesis-пулы, без mining).
    Возвращает {address: amount_abs_int}.
    """
    result: Dict[str, int] = {}
    for pool in build_allocations(founder_address):
        if pool.release_type == "genesis":
            result[pool.address_key] = int(pool.amount_abs)
    return result


def resolve_founder_address(
    founder_address: str = "",
    miner_address: str = "",
) -> str:
    """Canonical founder address for tokenomics (config → miner → default)."""
    return founder_address or miner_address or DEFAULT_FOUNDER_ADDRESS


def founder_balance_lookup(
    db,
    founder_address: str = "",
    miner_address: str = "",
) -> dict:
    """
    Balance for founder allocation. Falls back to miner wallet when the
    configured founder address has no on-chain balance (legacy devnet DBs).
    """
    addr = resolve_founder_address(founder_address, miner_address)
    summary = get_tokenomics_summary(addr)
    founder_addr = summary["founder"]["address"]
    bal = float(db.get_balance(founder_addr)) if db and founder_addr else 0.0
    balance_address = founder_addr
    if bal <= 0 and db and miner_address and miner_address.lower() != founder_addr.lower():
        miner_bal = float(db.get_balance(miner_address))
        if miner_bal > 0:
            bal = miner_bal
            balance_address = miner_address
    return {
        "address": founder_addr,
        "balance_abs": bal,
        "balance_address": balance_address,
        "summary": summary,
    }


def get_tokenomics_summary(founder_address: Optional[str] = None) -> dict:
    """Полная сводка токеномики для API и веб-интерфейса."""
    pools = build_allocations(founder_address)
    genesis_total = sum(p.amount_abs for p in pools if p.release_type == "genesis")
    mining_total = sum(p.amount_abs for p in pools if p.release_type == "mining")

    return {
        "coin_symbol": "ABS",
        "coin_name": "Absolute",
        "max_supply": MAX_SUPPLY_ABS,
        "max_supply_formatted": f"{MAX_SUPPLY_ABS:,} ABS",
        "founder": {
            "full_name": FOUNDER_FULL_NAME,
            "initials": FOUNDER_INITIALS,
            "alias": FOUNDER_ALIAS,
            "birthdate": FOUNDER_BIRTHDATE,
            "city": FOUNDER_CITY,
            "email": FOUNDER_EMAIL,
            "github": FOUNDER_GITHUB,
            "address": founder_address or DEFAULT_FOUNDER_ADDRESS,
            "percent": FOUNDER_PERCENT,
            "amount_abs": FOUNDER_AMOUNT_ABS,
            "amount_formatted": f"{FOUNDER_AMOUNT_ABS:,.0f} ABS",
        },
        "conditions": {
            "burn_rate": "2% каждой комиссии сжигается навсегда",
            "block_reward": "50 ABS за блок (из mining pool)",
            "block_time": "15 секунд",
            "min_stake": "1000 ABS для валидатора",
            "max_supply_cap": f"Жёсткий лимит {MAX_SUPPLY_ABS:,} ABS",
            "founder_vesting": "Без вестинга — 17.4% доступны с genesis",
            "ecosystem_lock": "10% заблокированы до DAO-голосования",
            "treasury_lock": "10% заблокированы до DAO-голосования",
            "staking_release": "12.6% разблокируются по эпохам (32 блока)",
            "mining_emission": "50% эмитируются через block rewards",
        },
        "allocations": [
            {
                "id": p.id,
                "name": p.name,
                "percent": p.percent,
                "amount_abs": p.amount_abs,
                "amount_formatted": f"{p.amount_abs:,.0f} ABS",
                "address": p.address_key,
                "description": p.description,
                "locked": p.locked,
                "release_type": p.release_type,
            }
            for p in pools
        ],
        "genesis_minted": genesis_total,
        "mining_reserve": mining_total,
        "genesis_percent": round(genesis_total / MAX_SUPPLY_ABS * 100, 2),
        "mining_percent": round(mining_total / MAX_SUPPLY_ABS * 100, 2),
    }
