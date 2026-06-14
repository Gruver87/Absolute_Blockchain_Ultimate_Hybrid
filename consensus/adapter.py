#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Consensus Adapter — связывает все компоненты консенсуса с живым узлом.

Интегрирует:
  - ConsensusEngineSlashing  : LMD-GHOST fork choice + Casper FFG + Slashing
  - ConsensusEngine          : PoS proposer rotation, slots/epochs (fallback)
  - FinalityEngine           : Casper FFG checkpoint finalization
  - ValidatorRegistry        : Репутация, слэшинг, статистика валидаторов
  - PBSMarket                : Proposer/Builder Separation (MEV protection)
"""

import time
import sys
import os
from typing import Optional, Dict, List

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from consensus_engine import ConsensusEngine, Validator
from finality_engine import FinalityEngine
from storage.database import Database
from runtime.config import Config
from kernel.event_bus import EventBus

# --- System C consensus (LMD-GHOST + Slashing + BeaconFinality) ---
try:
    from consensus.engine_slashing import ConsensusEngineSlashing
    from consensus.validator_registry import ValidatorRegistry
    from consensus.pbs import PBSMarket, Builder, Proposer
    _SLASHING_AVAILABLE = True
except ImportError:
    _SLASHING_AVAILABLE = False

# --- Casper FFG finality engine (alternative two-step finality) ---
try:
    from consensus.engine_casper import ConsensusEngineCasper
    from consensus.finality_casper import CasperFinality
    _CASPER_AVAILABLE = True
except ImportError:
    _CASPER_AVAILABLE = False

# --- Beacon Chain consensus engine ---
try:
    from consensus.engine_beacon import ConsensusEngineBeacon
    _BEACON_AVAILABLE = True
except ImportError:
    _BEACON_AVAILABLE = False


class ConsensusAdapter:
    """
    Unified consensus adapter — объединяет лучшее из трёх систем:

    System A (основная):
      ConsensusEngine      → proposer selection, slot advancement
      FinalityEngine       → Casper FFG checkpoints

    System C (расширенная):
      ConsensusEngineSlashing → LMD-GHOST fork choice + slashing protection
      ValidatorRegistry       → reputation, missed-block penalties
      PBSMarket               → proposer/builder separation (MEV)
    """

    def __init__(self, config: Config, db: Database, bus: Optional[EventBus] = None):
        self.config = config
        self.db = db
        self.bus = bus

        # --- System A engines (always available) ---
        self.engine = ConsensusEngine()
        self.finality = FinalityEngine()

        # --- System C engines (available if imported) ---
        if _SLASHING_AVAILABLE:
            epoch_size = getattr(config, "epoch_size", 32)
            self.slashing_engine = ConsensusEngineSlashing(epoch_size=epoch_size)
            self.validator_registry = ValidatorRegistry()
            self.pbs_market = PBSMarket()
            # Default builder/proposer
            self.pbs_market.add_builder(Builder("default-builder"))
            self.pbs_market.add_proposer(Proposer("default-proposer"))
            print("[Consensus] LMD-GHOST + Slashing + ValidatorRegistry + PBS: enabled")
        else:
            self.slashing_engine = None
            self.validator_registry = None
            self.pbs_market = None
            print("[Consensus] Basic PoS mode (engine_slashing not available)")

        # --- Casper FFG engine (two-step finality, alternative to FinalityEngine) ---
        if _CASPER_AVAILABLE:
            epoch_sz = getattr(config, "epoch_size", 32)
            self.casper_engine = ConsensusEngineCasper(epoch_size=epoch_sz)
            print("[Consensus] CasperFFG two-step finality: enabled")
        else:
            self.casper_engine = None

        # --- Beacon Chain consensus engine ---
        if _BEACON_AVAILABLE:
            epoch_sz = getattr(config, "epoch_size", 32)
            self.beacon_engine = ConsensusEngineBeacon(epoch_size=epoch_sz)
            print("[Consensus] BeaconChain engine: enabled (parallel fork choice)")
        else:
            self.beacon_engine = None

        self._last_block_time: float = 0.0
        self._load_validators_from_db()
        self._sync_finality_validator_count()

        if self.bus:
            self.bus.on("block.new", self._on_new_block)

    # ── Инициализация ────────────────────────────────────────────────────────

    def _load_validators_from_db(self):
        """Загружает валидаторов из БД при старте."""
        validators = self.db.get_validators(active_only=True)
        for v in validators:
            self._register_validator_all(v["address"], float(v["stake"]))
        if validators:
            print(f"[Consensus] Loaded {len(validators)} validators from DB")

        if self.slashing_engine:
            self.slashing_engine.slashing.register_slash_callback(self._on_validator_slashed)

    def _on_validator_slashed(self, address: str, reason: str, slot: int, penalty: int):
        """Persist slash to SQLite and validator registry."""
        try:
            self.db.slash_validator(address)
        except Exception:
            pass
        if self.validator_registry:
            self.validator_registry.slash_validator(address)

    def _register_validator_all(self, address: str, stake: float):
        """Регистрирует валидатора во всех подсистемах."""
        self.engine.add_validator(address, stake)
        if self.slashing_engine:
            self.slashing_engine.add_validator(address, int(stake))
        if self.validator_registry:
            self.validator_registry.register_validator(address, int(stake))

    def _sync_finality_validator_count(self):
        """Keep Casper FFG quorum aligned with live validator registry."""
        count = 0
        if self.db and hasattr(self.db, "get_validators"):
            count = len(self.db.get_validators(active_only=True) or [])
        if count <= 0:
            count = len(self.engine.validators)
        self.finality.set_active_validator_count(max(1, count))

    def get_finalized_floor_height(self) -> int:
        """Highest block height protected from rollback (0 if none finalized)."""
        floor = 0
        for epoch in self.finality.finalized_checkpoints:
            cp = self.finality.checkpoints.get(epoch)
            if cp and int(cp.block_number) > floor:
                floor = int(cp.block_number)
        return floor

    # ── Управление валидаторами ──────────────────────────────────────────────

    def add_validator(self, address: str, stake: float) -> bool:
        """Регистрирует нового валидатора (сохраняет в БД + во все движки)."""
        ok = self.engine.add_validator(address, stake)
        if ok:
            self.db.save_validator(address, stake)
            if self.slashing_engine:
                self.slashing_engine.add_validator(address, int(stake))
            if self.validator_registry:
                self.validator_registry.register_validator(address, int(stake))
            self._sync_finality_validator_count()
            print(f"[Consensus] New validator: {address[:12]}... stake={stake}")
        return ok

    def slash_validator(self, address: str):
        """Слэшит валидатора (нарушение консенсуса)."""
        if self.validator_registry:
            self.validator_registry.slash_validator(address)
            print(f"[Consensus] Validator slashed: {address[:12]}...")

    def get_validators(self) -> List[Dict]:
        if self.validator_registry:
            return [v.to_dict() for v in self.validator_registry.get_all_validators()]
        return [
            {
                "address": v.address,
                "stake": v.stake,
                "is_active": v.is_active,
                "attestations": v.attestations,
                "blocks_proposed": v.blocks_proposed,
            }
            for v in self.engine.validators.values()
        ]

    def get_total_stake(self) -> float:
        return self.engine.get_total_stake()

    # ── Выбор proposer ───────────────────────────────────────────────────────

    def select_proposer(self) -> Optional[str]:
        """Deterministic stake-weighted proposer — all nodes agree on same slot."""
        if not self.engine.validators:
            return self.config.miner_address or "genesis"

        validator = self.engine.select_proposer()
        return validator.address if validator else self.config.miner_address or "genesis"

    def should_produce_block(self) -> bool:
        """Проверяет, наступило ли время форжить следующий блок."""
        now = time.time()
        return now - self._last_block_time >= self.config.block_time

    def mark_block_produced(self, proposer: str = None):
        """Вызывается после успешного форжинга блока."""
        self._last_block_time = time.time()
        self.engine.advance_slot()
        if proposer and self.validator_registry:
            self.validator_registry.record_produced_block(proposer)

    # ── Аттестации ───────────────────────────────────────────────────────────

    def attest(self, validator_addr: str, block_hash: str) -> bool:
        """Аттестация блока от валидатора. Проверяет на double-vote (slashing)."""
        slot = self.engine.current_slot

        # LMD-GHOST + slashing check
        if self.slashing_engine:
            ok = self.slashing_engine.on_attestation(validator_addr, block_hash, slot)
            if not ok:
                print(f"[Consensus] Attestation rejected (slashing): {validator_addr[:12]}...")
                return False

        ok = self.engine.attest(validator_addr, slot, block_hash)
        if ok:
            if self.validator_registry:
                self.validator_registry.record_vote(validator_addr)
            if self.bus:
                self.bus.emit("consensus.attestation", {
                    "validator": validator_addr,
                    "slot": slot,
                    "block_hash": block_hash,
                })
        return ok

    # ── GHOST fork choice ────────────────────────────────────────────────────

    def get_canonical_head(self) -> Optional[str]:
        """Возвращает хэш канонической головы цепи по LMD-GHOST."""
        if self.slashing_engine:
            return self.slashing_engine.get_head()
        return None

    def add_block_to_fork_choice(self, block: Dict):
        """Добавляет блок в дерево для GHOST fork choice."""
        if self.slashing_engine:
            self.slashing_engine.add_block(block)

    def get_cumulative_weight(self, block_hash: str) -> int:
        """Кумулятивный вес блока для LMD-GHOST."""
        if self.slashing_engine:
            return self.slashing_engine.get_cumulative_weight(block_hash)
        return 0

    # ── PBS (MEV protection) ─────────────────────────────────────────────────

    def run_pbs_auction(self, pending_txs: List[Dict]) -> Optional[Dict]:
        """
        Запускает аукцион PBS: builders создают блоки,
        proposer выбирает наиболее доходный.
        """
        if self.pbs_market and pending_txs:
            return self.pbs_market.run_auction(pending_txs)
        return None

    # ── Финальность ──────────────────────────────────────────────────────────

    def process_block_finality(self, block_number: int, block_hash: str,
                               proposer: str) -> Dict:
        """Обновляет статус финализации после добавления блока."""
        result = self.finality.process_block(block_number, block_hash, proposer)

        epoch = result["epoch"]
        justified = epoch in result["justified"]
        finalized = epoch in result["finalized"]
        self.db.save_checkpoint(epoch, block_hash, justified, finalized)

        if finalized and self.bus:
            self.bus.emit("consensus.finalized", {"epoch": epoch, "block": block_number})

        # Также обновляем слэшинг-движок финальностью
        if self.slashing_engine:
            self.slashing_engine.finality.set_total_stake(
                self.slashing_engine.slashing.get_total_active_stake()
            )

        return result

    def is_finalized(self, block_number: int) -> bool:
        epoch = self.finality.get_epoch(block_number)
        if epoch in self.finality.finalized_checkpoints:
            return True
        blk = self.db.get_block(block_number) if self.db else None
        block_hash = blk.get("hash", "") if blk else ""
        if block_hash and self.slashing_engine:
            if self.slashing_engine.is_finalized(block_hash):
                return True
        if block_hash and self.casper_engine:
            try:
                if self.casper_engine.is_finalized(block_hash):
                    return True
            except Exception:
                pass
        if block_hash and self.beacon_engine:
            try:
                if self.beacon_engine.is_finalized(block_hash):
                    return True
            except Exception:
                pass
        return False

    def get_finality_status(self, block_number: int) -> Dict:
        return self.finality.get_finality_status(block_number)

    # ── Слушатель событий ────────────────────────────────────────────────────

    def _on_new_block(self, block_data: Dict):
        """Автоматически обрабатывает финализацию при каждом новом блоке."""
        if not isinstance(block_data, dict):
            return
        proposer = block_data.get("miner", "")
        self.process_block_finality(
            block_number=block_data.get("height", 0),
            block_hash=block_data.get("hash", ""),
            proposer=proposer,
        )
        # Feed block to GHOST fork tree
        blk_for_fork = {
            "hash": block_data.get("hash", ""),
            "parent_hash": block_data.get("parent_hash", ""),
            "number": block_data.get("height", 0),
        }
        self.add_block_to_fork_choice(blk_for_fork)

        # Feed block to Casper FFG engine (two-step finality)
        if self.casper_engine:
            try:
                self.casper_engine.add_block(blk_for_fork)
            except Exception:
                pass

        # Feed block to Beacon Chain engine
        if self.beacon_engine:
            try:
                self.beacon_engine.add_block(blk_for_fork)
            except Exception:
                pass

        # Record block production in validator registry
        if proposer and self.validator_registry:
            self.validator_registry.record_produced_block(proposer)

    # ── Статистика ───────────────────────────────────────────────────────────

    def get_casper_status(self) -> Dict:
        """Returns Casper FFG two-step finality status."""
        if not self.casper_engine:
            return {"enabled": False}
        try:
            return {"enabled": True, "finality": self.casper_engine.get_finality_status()}
        except Exception as e:
            return {"enabled": True, "error": str(e)}

    def get_beacon_status(self) -> Dict:
        """Returns Beacon Chain engine status (head, finality)."""
        if not self.beacon_engine:
            return {"enabled": False}
        try:
            return {"enabled": True, "stats": self.beacon_engine.get_stats()}
        except Exception as e:
            return {"enabled": True, "error": str(e)}

    def get_stats(self) -> Dict:
        engine_stats = self.engine.get_stats()
        finality_stats = self.finality.get_stats()
        lmd_on = self.slashing_engine is not None
        casper_on = self.casper_engine is not None or self.finality is not None
        slashing_on = self.slashing_engine is not None
        pbs_on = self.pbs_market is not None
        registry_on = self.validator_registry is not None
        stats = {
            **engine_stats,
            **finality_stats,
            "enabled": True,
            "block_time": self.config.block_time,
            "min_stake": self.config.min_stake,
            "lmd_ghost_enabled": lmd_on,
            "casper_ffg": casper_on,
            "casper_ffg_enabled": self.casper_engine is not None,
            "finality_engine_enabled": self.finality is not None,
            "slashing_enabled": slashing_on,
            "pbs_enabled": pbs_on,
            "validator_registry": registry_on,
            "beacon_enabled": self.beacon_engine is not None,
            "systems": {
                "lmd_ghost": lmd_on,
                "casper_ffg": casper_on,
                "slashing": slashing_on,
                "pbs": pbs_on,
                "validator_registry": registry_on,
                "beacon": self.beacon_engine is not None,
            },
        }
        if self.slashing_engine:
            try:
                slashing_stats = self.slashing_engine.get_stats()
                stats["slashed_validators"] = slashing_stats.get("slashed_validators", 0)
                stats["slashed_stake"] = slashing_stats.get("slashed_stake", 0)
                stats["canonical_head"] = slashing_stats.get("head_hash")
                stats["attestation_count"] = slashing_stats.get("active_votes", 0)
                stats["active_votes"] = slashing_stats.get("active_votes", 0)
                stats["head_height"] = slashing_stats.get("head_height")
            except Exception as e:
                stats["head_stats_error"] = str(e)
        if self.validator_registry:
            try:
                reg_stats = self.validator_registry.get_stats()
                stats.update(reg_stats)
            except Exception as e:
                stats["registry_stats_error"] = str(e)
        return stats

    def get_attestations(self) -> List[Dict]:
        """Latest LMD votes per validator (live attestation table)."""
        if not self.slashing_engine:
            return []
        out = []
        lmd = getattr(self.slashing_engine, "lmd", None)
        if not lmd:
            return []
        weights = lmd.get_weights()
        for validator, (block_hash, slot) in lmd.latest_vote.items():
            out.append({
                "validator": validator,
                "block_hash": block_hash,
                "slot": int(slot),
                "stake": int(lmd.validator_stake.get(validator, 0)),
                "block_weight": int(weights.get(block_hash, 0)),
            })
        out.sort(key=lambda x: (-x["slot"], x["validator"]))
        return out

    def get_attestations_by_block(self) -> List[Dict]:
        """Aggregate LMD votes grouped by target block hash."""
        grouped: Dict[str, Dict] = {}
        for vote in self.get_attestations():
            block_hash = vote.get("block_hash", "")
            if not block_hash:
                continue
            entry = grouped.get(block_hash)
            if not entry:
                entry = {
                    "block_hash": block_hash,
                    "votes": 0,
                    "total_stake": 0,
                    "validators": [],
                }
                grouped[block_hash] = entry
            entry["votes"] += 1
            entry["total_stake"] += int(vote.get("stake", 0))
            entry["validators"].append(vote.get("validator", ""))
        rows = list(grouped.values())
        rows.sort(key=lambda x: (-x["votes"], -x["total_stake"]))
        return rows

    def get_attestations_for_block(self, block_hash: str) -> List[Dict]:
        """Votes targeting a specific block hash."""
        target = (block_hash or "").strip().lower()
        if not target:
            return []
        return [
            v for v in self.get_attestations()
            if str(v.get("block_hash", "")).lower().startswith(target)
            or target in str(v.get("block_hash", "")).lower()
        ]
