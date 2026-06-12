# ============================================================
# MIGRATION PLAN - БЕЗОПАСНАЯ ОЧИСТКА ПРОЕКТА
# Ничего не удаляет, только создаёт план и бэкапы
# ============================================================

$PROJECT_PATH = "C:\Users\vovun\Desktop\Absolute_Blockchain_v2"
$BACKUP_PATH = "C:\Users\vovun\Desktop\Absolute_Blockchain_v2_BACKUP_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

Write-Host ""
Write-Host "████████████████████████████████████████████████████████████████" -ForegroundColor Cyan
Write-Host "██              MIGRATION PLAN - БЕЗОПАСНАЯ ОЧИСТКА           ██" -ForegroundColor Cyan
Write-Host "████████████████████████████████████████████████████████████████" -ForegroundColor Cyan
Write-Host ""

# 1. Создаём бэкап
Write-Host "[1/5] Создание бэкапа..." -ForegroundColor Yellow
Copy-Item -Path $PROJECT_PATH -Destination $BACKUP_PATH -Recurse
Write-Host "   ✅ Бэкап создан: $BACKUP_PATH" -ForegroundColor Green

# 2. Создаём CANONICAL ARCHITECTURE MAP
Write-Host "[2/5] Создание CANONICAL ARCHITECTURE MAP..." -ForegroundColor Yellow

$canonical_map = @'
# ABSOLUTE BLOCKCHAIN - CANONICAL ARCHITECTURE MAP v1
# Дата: 2026-06-09
# Статус: PRODUCTION READY

## ЕДИНСТВЕННЫЙ ENTRYPOINT
**main.py** - единственная точка входа

## CANONICAL NODE
**core/node.py** - оркестратор всей системы

## СЛОИ АРХИТЕКТУРЫ

### 1. CONSENSUS LAYER
| Статус | Файл | Описание |
|--------|------|----------|
| ✅ ACTIVE | `core/consensus/engine.py` | Единый консенсус-движок |
| ✅ ACTIVE | `core/consensus/chain_resolver.py` | Longest chain rule |
| ❌ DEPRECATE | `consensus/engine_v42.py` | Старая версия |
| ❌ DEPRECATE | `consensus/engine_v45.py` | Старая версия |
| ❌ DEPRECATE | `consensus/ghost.py` | Не используется |
| ❌ DEPRECATE | `consensus/lmd.py` | Не используется |
| ❌ DEPRECATE | `consensus/casper.py` | Не используется |

### 2. STORAGE LAYER
| Статус | Файл | Описание |
|--------|------|----------|
| ✅ ACTIVE | `core/storage/block_store.py` | Единое хранилище |
| ✅ ACTIVE | `storage/database.py` | SQLite интерфейс |
| ❌ DEPRECATE | `storage/rocksdb_storage.py` | Альтернатива |
| ❌ DEPRECATE | `storage/persistent_storage.py` | Дубликат |

### 3. NETWORK LAYER
| Статус | Файл | Описание |
|--------|------|----------|
| ✅ ACTIVE | `core/network/sync_manager.py` | Синхронизация |
| ✅ ACTIVE | `network/p2p/p2p.py` | P2P сеть |
| ❌ DEPRECATE | `global_p2p_network.py` | Дубликат |
| ❌ DEPRECATE | `p2p/full_node.py` | Старая версия |

### 4. API LAYER
| Статус | Файл | Описание |
|--------|------|----------|
| ✅ ACTIVE | `api/server.py` | Единый API |
| ❌ DEPRECATE | `extended_api_server.py` | Дубликат |
| ❌ DEPRECATE | `simple_api.py` | Тестовый |
| ❌ DEPRECATE | `level11_api.py` | Старая версия |

### 5. RPC LAYER
| Статус | Файл | Описание |
|--------|------|----------|
| ✅ ACTIVE | `rpc/server.py` | JSON-RPC |
| ❌ DEPRECATE | `rpc_proxy.py` | Дубликат |
| ❌ DEPRECATE | `rpc/json_rpc_server.py` | Дубликат |

### 6. EXECUTION LAYER
| Статус | Файл | Описание |
|--------|------|----------|
| ✅ ACTIVE | `execution/engine.py` | Единый движок |
| ✅ ACTIVE | `execution/vm.py` | EVM |
| ❌ DEPRECATE | `evm_engine.py` | Дубликат |
| ❌ DEPRECATE | `evm_interpreter.py` | Дубликат |

### 7. SERVICES
| Статус | Файл | Описание |
|--------|------|----------|
| ✅ ACTIVE | `services/indexer.py` | Единый индексер |
| ✅ ACTIVE | `services/websocket.py` | WebSocket |
| ❌ DEPRECATE | `indexer.py` (root) | Дубликат |

## DEPENDENCY GRAPH
