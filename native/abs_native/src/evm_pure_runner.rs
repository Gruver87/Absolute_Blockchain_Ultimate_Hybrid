use primitive_types::U256;
use pyo3::prelude::*;
use pyo3::types::{PyByteArray, PyDict, PyList};
use std::collections::HashMap;

use crate::{
    evm_calldataload_inner, evm_is_jumpdest_inner, evm_keccak256_memory_inner,
    evm_memory_read_word_inner, evm_memory_slice_inner, evm_read_push_inner,
    evm_u256_addmod_inner, evm_u256_exp_inner, evm_u256_mulmod_inner, evm_u256_sdiv_inner,
    evm_u256_sar_inner, evm_u256_signextend_inner, evm_u256_slt_inner, evm_u256_smod_inner,
    keccak256_digest_bytes, u256_from_be32, u256_to_be32,
};

const U256_MASK: U256 = U256::MAX;
const MAX_PURE_STEPS: usize = 8192;
const MAX_FULL_STEPS: usize = 10_000_000;

pub fn evm_opcode_is_bridge(op: u8) -> bool {
    matches!(op, 0x31 | 0x3B | 0x3C | 0x3F | 0x40)
}

pub fn evm_opcode_is_host(op: u8) -> bool {
    matches!(op, 0xF0 | 0xF1 | 0xF2 | 0xF4 | 0xF5 | 0xFA | 0xFF)
        || (0xA0..=0xA4).contains(&op)
}

fn opcode_stops_segment(
    op: u8,
    host_context: Option<&Bound<'_, PyDict>>,
    host_bridge: Option<&Bound<'_, PyAny>>,
) -> bool {
    if (0xA0..=0xA4).contains(&op) {
        return !log_runtime_available(host_context, host_bridge);
    }
    if evm_opcode_is_host(op) {
        return !bridge_supports_runtime(host_bridge);
    }
    if evm_opcode_is_bridge(op) {
        return !bridge_opcode_available(host_context, host_bridge);
    }
    false
}

fn bridge_supports_inline(host_context: Option<&Bound<'_, PyDict>>) -> bool {
    let Some(ctx) = host_context else {
        return false;
    };
    if let Ok(Some(state)) = ctx.get_item("bridge_state") {
        if state.downcast::<PyDict>().is_ok() {
            return true;
        }
    }
    if let Ok(Some(hooks)) = ctx.get_item("bridge_hooks") {
        if let Ok(dict) = hooks.downcast::<PyDict>() {
            return dict.len() > 0;
        }
    }
    false
}

fn bridge_opcode_available(
    host_context: Option<&Bound<'_, PyDict>>,
    host_bridge: Option<&Bound<'_, PyAny>>,
) -> bool {
    host_bridge.is_some() || bridge_supports_inline(host_context)
}

fn bridge_supports_runtime(host_bridge: Option<&Bound<'_, PyAny>>) -> bool {
    host_bridge
        .map(|bridge| bridge.hasattr("apply_host_op").unwrap_or(false))
        .unwrap_or(false)
}

fn apply_runtime_host_op(
    py: Python<'_>,
    bridge: &Bound<'_, PyAny>,
    op: u8,
    stack: &mut Vec<U256>,
    memory: &mut Vec<u8>,
    gas_limit: u64,
    gas_used: &mut u64,
    storage: Option<&Bound<'_, PyDict>>,
    return_data: &mut Vec<u8>,
    running: &mut bool,
    reverted: &mut bool,
) -> PyResult<()> {
    let stack_list = stack_to_pylist(py, stack)?;
    let memory_ba = PyByteArray::new_bound(py, memory);
    let storage_obj: PyObject = match storage {
        Some(dict) => dict.clone().unbind().into(),
        None => PyDict::new_bound(py).into(),
    };
    let out = bridge.call_method1(
        "apply_host_op",
        (
            op,
            stack_list,
            memory_ba,
            gas_limit,
            *gas_used,
            storage_obj,
            return_data.as_slice(),
        ),
    )?;
    let out_dict = out.downcast::<PyDict>()?;
    *gas_used = out_dict.get_item("gas_used")?.unwrap().extract()?;
    *memory = out_dict
        .get_item("memory")?
        .unwrap()
        .extract::<Vec<u8>>()?;
    let stack_any = out_dict.get_item("stack")?.unwrap();
    let stack_list = stack_any.downcast::<PyList>()?;
    *stack = stack_from_py(stack_list)?;
    *return_data = out_dict
        .get_item("return_data")?
        .unwrap()
        .extract::<Vec<u8>>()?;
    *running = out_dict.get_item("running")?.unwrap().extract()?;
    *reverted = out_dict.get_item("reverted")?.unwrap().extract()?;
    Ok(())
}

struct EvmStaticContext {
    address: U256,
    caller: U256,
    origin: U256,
    value: U256,
    timestamp: U256,
    block_number: U256,
    chain_id: U256,
    base_fee: U256,
    gas_price: U256,
    difficulty: U256,
    coinbase: U256,
    blob_base_fee: U256,
    blob_hashes: Vec<U256>,
}

fn parse_static_context(host_context: Option<&Bound<'_, PyDict>>) -> PyResult<EvmStaticContext> {
    let Some(ctx) = host_context else {
        return Ok(EvmStaticContext {
            address: U256::zero(),
            caller: U256::zero(),
            origin: U256::zero(),
            value: U256::zero(),
            timestamp: U256::zero(),
            block_number: U256::zero(),
            chain_id: U256::zero(),
            base_fee: U256::zero(),
            gas_price: U256::zero(),
            difficulty: U256::zero(),
            coinbase: U256::zero(),
            blob_base_fee: U256::zero(),
            blob_hashes: Vec::new(),
        });
    };
    Ok(EvmStaticContext {
        address: dict_get_u256(ctx, "address")?,
        caller: dict_get_u256(ctx, "caller")?,
        origin: dict_get_u256(ctx, "origin")?,
        value: dict_get_u256(ctx, "value")?,
        timestamp: dict_get_u256(ctx, "timestamp")?,
        block_number: dict_get_u256(ctx, "block_number")?,
        chain_id: dict_get_u256(ctx, "chain_id")?,
        base_fee: dict_get_u256(ctx, "base_fee")?,
        gas_price: dict_get_u256(ctx, "gas_price")?,
        difficulty: dict_get_u256(ctx, "difficulty")?,
        coinbase: dict_get_u256(ctx, "coinbase")?,
        blob_base_fee: dict_get_u256(ctx, "blob_base_fee")?,
        blob_hashes: dict_get_u256_list(ctx, "blob_hashes")?,
    })
}

fn dict_get_u256_list(dict: &Bound<'_, PyDict>, key: &str) -> PyResult<Vec<U256>> {
    match dict.get_item(key)? {
        Some(value) => {
            let items: Vec<Bound<'_, PyAny>> = value.extract()?;
            items.into_iter().map(py_to_u256).collect()
        }
        None => Ok(Vec::new()),
    }
}

fn py_to_u256(obj: Bound<'_, PyAny>) -> PyResult<U256> {
    let bytes_obj = obj.call_method1("to_bytes", (32, "big"))?;
    let bytes: Vec<u8> = bytes_obj.extract()?;
    let mut buf = [0u8; 32];
    let start = 32usize.saturating_sub(bytes.len());
    buf[start..].copy_from_slice(&bytes);
    Ok(U256::from_big_endian(&buf))
}

fn dict_get_u256(dict: &Bound<'_, PyDict>, key: &str) -> PyResult<U256> {
    match dict.get_item(key)? {
        Some(value) => py_to_u256(value),
        None => Ok(U256::zero()),
    }
}

fn u256_to_py_int(py: Python<'_>, value: U256) -> PyResult<PyObject> {
    let builtins = py.import_bound("builtins")?;
    let int_cls = builtins.getattr("int")?;
    let bytes = u256_to_be32(value);
    Ok(int_cls
        .call_method1("from_bytes", (bytes.as_slice(), "big"))?
        .into())
}

fn storage_load(storage: Option<&Bound<'_, PyDict>>, key: U256) -> PyResult<U256> {
    let Some(dict) = storage else {
        return Err(pyo3::exceptions::PyRuntimeError::new_err("storage_unavailable"));
    };
    let py = dict.py();
    let key_obj = u256_to_py_int(py, key)?;
    match dict.get_item(key_obj)? {
        Some(value) => py_to_u256(value),
        None => Ok(U256::zero()),
    }
}

fn storage_store(storage: Option<&Bound<'_, PyDict>>, key: U256, value: U256) -> PyResult<()> {
    let Some(dict) = storage else {
        return Err(pyo3::exceptions::PyRuntimeError::new_err("storage_unavailable"));
    };
    let py = dict.py();
    let key_obj = u256_to_py_int(py, key)?;
    if value.is_zero() {
        let _ = dict.del_item(key_obj);
    } else {
        dict.set_item(key_obj, u256_to_py_int(py, value)?)?;
    }
    Ok(())
}

fn word_to_address(word: U256) -> String {
    let mask = (U256::one() << 160) - U256::one();
    format!("0x{:040x}", word & mask)
}

fn py_to_u256_or_int(obj: Bound<'_, PyAny>) -> PyResult<U256> {
    if let Ok(v) = obj.extract::<u64>() {
        return Ok(U256::from(v));
    }
    py_to_u256(obj)
}

fn bridge_balance(bridge: &Bound<'_, PyAny>, who: U256) -> PyResult<U256> {
    let addr = word_to_address(who);
    let result = bridge.call_method1("balance", (addr,))?;
    py_to_u256_or_int(result)
}

fn bridge_code_size(bridge: &Bound<'_, PyAny>, who: U256) -> PyResult<U256> {
    let addr = word_to_address(who);
    let result = bridge.call_method1("code_size", (addr,))?;
    py_to_u256_or_int(result)
}

fn bridge_code_copy(
    bridge: &Bound<'_, PyAny>,
    who: U256,
    code_offset: usize,
    size: usize,
) -> PyResult<Vec<u8>> {
    let addr = word_to_address(who);
    let result = bridge.call_method1("code_copy", (addr, code_offset, size))?;
    result.extract::<Vec<u8>>()
}

fn bridge_block_hash(bridge: &Bound<'_, PyAny>, block_num: U256) -> PyResult<U256> {
    let result = bridge.call_method1("block_hash", (block_num.as_u64(),))?;
    py_to_u256_or_int(result)
}

fn bridge_state_dict<'py>(
    host_context: Option<&Bound<'py, PyDict>>,
) -> Option<Bound<'py, PyDict>> {
    let ctx = host_context?;
    let state = ctx.get_item("bridge_state").ok()??;
    state.downcast::<PyDict>().ok().cloned()
}

fn bridge_hooks_dict<'py>(
    host_context: Option<&Bound<'py, PyDict>>,
) -> Option<Bound<'py, PyDict>> {
    let ctx = host_context?;
    let hooks = ctx.get_item("bridge_hooks").ok()??;
    hooks.downcast::<PyDict>().ok().cloned()
}

fn inline_balance(
    host_context: Option<&Bound<'_, PyDict>>,
    who: U256,
) -> Option<PyResult<U256>> {
    let state = bridge_state_dict(host_context)?;
    let balances = state.get_item("balances").ok()??;
    let dict = balances.downcast::<PyDict>().ok()?;
    let addr = word_to_address(who);
    let value = dict.get_item(addr.as_str()).ok()??;
    Some(py_to_u256_or_int(value))
}

fn inline_code_bytes(
    host_context: Option<&Bound<'_, PyDict>>,
    who: U256,
) -> Option<PyResult<Vec<u8>>> {
    let state = bridge_state_dict(host_context)?;
    let codes = state.get_item("codes").ok()??;
    let dict = codes.downcast::<PyDict>().ok()?;
    let addr = word_to_address(who);
    let value = dict.get_item(addr.as_str()).ok()??;
    Some(value.extract::<Vec<u8>>())
}

fn inline_block_hash(
    host_context: Option<&Bound<'_, PyDict>>,
    block_num: U256,
) -> Option<PyResult<U256>> {
    let state = bridge_state_dict(host_context)?;
    let hashes = state.get_item("block_hashes").ok()??;
    let dict = hashes.downcast::<PyDict>().ok()?;
    let block_key = block_num.as_u64();
    let value = dict
        .get_item(block_key)
        .ok()
        .flatten()
        .or_else(|| dict.get_item(block_key.to_string()).ok().flatten())?;
    Some(py_to_u256_or_int(value))
}

fn hook_balance(
    host_context: Option<&Bound<'_, PyDict>>,
    who: U256,
) -> Option<PyResult<U256>> {
    let hooks = bridge_hooks_dict(host_context)?;
    let func = hooks.get_item("balance").ok()??;
    let addr = word_to_address(who);
    Some(func.call1((addr,)).and_then(|value| py_to_u256_or_int(value)))
}

fn hook_code_size(
    host_context: Option<&Bound<'_, PyDict>>,
    who: U256,
) -> Option<PyResult<U256>> {
    let hooks = bridge_hooks_dict(host_context)?;
    let func = hooks.get_item("code_size").ok()??;
    let addr = word_to_address(who);
    Some(func.call1((addr,)).and_then(|value| py_to_u256_or_int(value)))
}

fn hook_code_copy(
    host_context: Option<&Bound<'_, PyDict>>,
    who: U256,
    code_offset: usize,
    size: usize,
) -> Option<PyResult<Vec<u8>>> {
    let hooks = bridge_hooks_dict(host_context)?;
    let func = hooks.get_item("code_copy").ok()??;
    let addr = word_to_address(who);
    Some(
        func.call1((addr, code_offset, size))
            .and_then(|value| value.extract::<Vec<u8>>()),
    )
}

fn hook_block_hash(
    host_context: Option<&Bound<'_, PyDict>>,
    block_num: U256,
) -> Option<PyResult<U256>> {
    let hooks = bridge_hooks_dict(host_context)?;
    let func = hooks.get_item("block_hash").ok()??;
    Some(
        func.call1((block_num.as_u64(),))
            .and_then(|value| py_to_u256_or_int(value)),
    )
}

fn hook_emit_log<'py>(
    host_context: Option<&Bound<'py, PyDict>>,
) -> Option<Bound<'py, PyAny>> {
    let hooks = bridge_hooks_dict(host_context)?;
    match hooks.get_item("emit_log") {
        Ok(Some(value)) => Some(value),
        _ => None,
    }
}

fn log_runtime_available(
    host_context: Option<&Bound<'_, PyDict>>,
    host_bridge: Option<&Bound<'_, PyAny>>,
) -> bool {
    hook_emit_log(host_context).is_some() || bridge_supports_runtime(host_bridge)
}

fn log_opcode_gas(n_topics: usize, data_size: usize) -> u64 {
    375 + (n_topics as u64 * 375) + data_size as u64
}

fn execute_log_hook(
    py: Python<'_>,
    emit_log: &Bound<'_, PyAny>,
    op: u8,
    stack: &mut Vec<U256>,
    memory: &mut Vec<u8>,
    gas_used: &mut u64,
    gas_limit: u64,
) -> PyResult<()> {
    let n_topics = (op - 0xA0) as usize;
    let mut topics = Vec::with_capacity(n_topics);
    for _ in 0..n_topics {
        topics.push(stack_pop(stack)?);
    }
    topics.reverse();
    let size = stack_pop(stack)?.as_usize();
    let offset = stack_pop(stack)?.as_usize();
    let cost = log_opcode_gas(n_topics, size);
    if let Err(reason) = consume_gas(gas_used, gas_limit, cost) {
        return Err(pyo3::exceptions::PyRuntimeError::new_err(reason));
    }
    mem_extend(memory, offset, size);
    let data = evm_memory_slice_inner(memory, offset, size);
    let topics_list = PyList::empty_bound(py);
    let builtins = py.import_bound("builtins")?;
    let int_cls = builtins.getattr("int")?;
    for topic in topics {
        let bytes = u256_to_be32(topic);
        let obj = int_cls.call_method1("from_bytes", (bytes.as_slice(), "big"))?;
        topics_list.append(obj)?;
    }
    emit_log.call1((n_topics, topics_list, data))?;
    Ok(())
}

fn resolve_balance(
    host_context: Option<&Bound<'_, PyDict>>,
    host_bridge: Option<&Bound<'_, PyAny>>,
    who: U256,
) -> PyResult<U256> {
    if let Some(result) = inline_balance(host_context, who) {
        return result;
    }
    if let Some(result) = hook_balance(host_context, who) {
        return result;
    }
    if let Some(bridge) = host_bridge {
        return bridge_balance(bridge, who);
    }
    Err(pyo3::exceptions::PyRuntimeError::new_err("bridge_unavailable"))
}

fn resolve_code_size(
    host_context: Option<&Bound<'_, PyDict>>,
    host_bridge: Option<&Bound<'_, PyAny>>,
    who: U256,
) -> PyResult<U256> {
    if let Some(result) = inline_code_bytes(host_context, who) {
        return result.map(|code| U256::from(code.len()));
    }
    if let Some(result) = hook_code_size(host_context, who) {
        return result;
    }
    if let Some(bridge) = host_bridge {
        return bridge_code_size(bridge, who);
    }
    Err(pyo3::exceptions::PyRuntimeError::new_err("bridge_unavailable"))
}

fn resolve_code_copy(
    host_context: Option<&Bound<'_, PyDict>>,
    host_bridge: Option<&Bound<'_, PyAny>>,
    who: U256,
    code_offset: usize,
    size: usize,
) -> PyResult<Vec<u8>> {
    if let Some(result) = inline_code_bytes(host_context, who) {
        return result.map(|code| {
            let mut out = vec![0u8; size];
            let available = code.len().saturating_sub(code_offset);
            let copy_len = size.min(available);
            if copy_len > 0 {
                out[..copy_len].copy_from_slice(&code[code_offset..code_offset + copy_len]);
            }
            out
        });
    }
    if let Some(result) = hook_code_copy(host_context, who, code_offset, size) {
        return result;
    }
    if let Some(bridge) = host_bridge {
        return bridge_code_copy(bridge, who, code_offset, size);
    }
    Err(pyo3::exceptions::PyRuntimeError::new_err("bridge_unavailable"))
}

fn resolve_block_hash(
    host_context: Option<&Bound<'_, PyDict>>,
    host_bridge: Option<&Bound<'_, PyAny>>,
    block_num: U256,
) -> PyResult<U256> {
    if let Some(result) = inline_block_hash(host_context, block_num) {
        return result;
    }
    if let Some(result) = hook_block_hash(host_context, block_num) {
        return result;
    }
    if let Some(bridge) = host_bridge {
        return bridge_block_hash(bridge, block_num);
    }
    Err(pyo3::exceptions::PyRuntimeError::new_err("bridge_unavailable"))
}

fn resolve_full_code(
    host_context: Option<&Bound<'_, PyDict>>,
    host_bridge: Option<&Bound<'_, PyAny>>,
    who: U256,
) -> PyResult<Vec<u8>> {
    if let Some(result) = inline_code_bytes(host_context, who) {
        return result;
    }
    let size = resolve_code_size(host_context, host_bridge, who)?.as_usize();
    if size == 0 {
        return Ok(Vec::new());
    }
    resolve_code_copy(host_context, host_bridge, who, 0, size)
}

fn resolve_code_hash(
    host_context: Option<&Bound<'_, PyDict>>,
    host_bridge: Option<&Bound<'_, PyAny>>,
    who: U256,
) -> PyResult<U256> {
    let code = resolve_full_code(host_context, host_bridge, who)?;
    if code.is_empty() {
        return Ok(U256::zero());
    }
    Ok(u256_from_be32(keccak256_digest_bytes(&code)))
}

fn evm_u256_div_inner(a: U256, b: U256) -> U256 {
    if b.is_zero() {
        U256::zero()
    } else {
        a / b
    }
}

fn evm_u256_mod_inner(a: U256, b: U256) -> U256 {
    if b.is_zero() {
        U256::zero()
    } else {
        a % b
    }
}

fn evm_u256_bool_word(truthy: bool) -> U256 {
    if truthy {
        U256::one()
    } else {
        U256::zero()
    }
}

fn evm_u256_eq_inner(a: U256, b: U256) -> U256 {
    evm_u256_bool_word(a == b)
}

fn evm_u256_lt_inner(a: U256, b: U256) -> U256 {
    evm_u256_bool_word(a < b)
}

fn evm_u256_gt_inner(a: U256, b: U256) -> U256 {
    evm_u256_bool_word(a > b)
}

fn evm_u256_iszero_inner(v: U256) -> U256 {
    evm_u256_bool_word(v.is_zero())
}

fn evm_u256_byte_inner(index: u32, value: U256) -> U256 {
    if index >= 32 {
        return U256::zero();
    }
    let shift = 8 * (31 - index);
    let byte = if shift >= 256 {
        0
    } else {
        ((value >> shift).low_u32() & 0xff) as u64
    };
    U256::from(byte)
}

fn evm_memory_active_bytes(len: usize) -> usize {
    if len == 0 {
        0
    } else {
        ((len + 31) / 32) * 32
    }
}

fn gas_cost(op: u8) -> u64 {
    match op {
        0x00 => 0,
        0x01 | 0x03 => 3,
        0x02 => 5,
        0x04 | 0x05 | 0x06 | 0x07 => 5,
        0x08 => 8,
        0x09 => 8,
        0x0A => 10,
        0x0B => 5,
        0x10 | 0x11 | 0x12 | 0x14 | 0x15 | 0x16 | 0x17 | 0x18 | 0x19 | 0x1A | 0x1B | 0x1C | 0x1D => 3,
        0x20 => 30,
        0x35 | 0x37 | 0x39 | 0x3E => 3,
        0x36 | 0x3D => 2,
        0x38 => 2,
        0x50 => 2,
        0x51 | 0x52 | 0x53 => 3,
        0x56 => 8,
        0x57 => 10,
        0x5A | 0x5F | 0x58 | 0x59 => 2,
        0x5B => 1,
        0x47 => 5,
        0x48 => 2,
        0x3A | 0x41 | 0x44 => 2,
        0x3F => 700,
        0x30 | 0x32 | 0x33 | 0x34 | 0x42 | 0x43 | 0x45 | 0x46 => 2,
        0x31 => 400,
        0x3B | 0x3C => 700,
        0x40 => 20,
        0x54 => 200,
        0x55 => 5000,
        0x5C | 0x5D => 100,
        0x5E => 3,
        0x49 | 0x4A => 2,
        0xF0 | 0xF5 => 32000,
        0xF1 | 0xF2 | 0xF4 | 0xFA => 700,
        0xFF => 5000,
        0xF3 | 0xFD => 0,
        0xFE => 0,
        _ if (0x60..=0x7F).contains(&op) => 3,
        _ if (0x80..=0x8F).contains(&op) => 3,
        _ if (0x90..=0x9F).contains(&op) => 3,
        _ => 3,
    }
}

fn consume_gas(gas_used: &mut u64, gas_limit: u64, cost: u64) -> Result<(), &'static str> {
    if *gas_used + cost > gas_limit {
        Err("out_of_gas")
    } else {
        *gas_used += cost;
        Ok(())
    }
}

fn mem_extend(memory: &mut Vec<u8>, offset: usize, size: usize) {
    let need = offset.saturating_add(size);
    if need > memory.len() {
        memory.resize(need, 0);
    }
}

fn stack_pop(stack: &mut Vec<U256>) -> PyResult<U256> {
    stack
        .pop()
        .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("stack_underflow"))
}

fn stack_push(stack: &mut Vec<U256>, value: U256) {
    stack.push(value & U256_MASK);
}

fn stack_dup(stack: &mut Vec<U256>, depth: usize) -> PyResult<()> {
    if depth == 0 || depth > stack.len() {
        return Err(pyo3::exceptions::PyRuntimeError::new_err("stack_underflow"));
    }
    stack_push(stack, stack[stack.len() - depth]);
    Ok(())
}

fn stack_swap(stack: &mut Vec<U256>, depth: usize) -> PyResult<()> {
    if depth == 0 || depth >= stack.len() {
        return Err(pyo3::exceptions::PyRuntimeError::new_err("stack_underflow"));
    }
    let top = stack.len() - 1;
    let other = stack.len() - 1 - depth;
    stack.swap(top, other);
    Ok(())
}

fn stack_from_py(list: &Bound<'_, PyList>) -> PyResult<Vec<U256>> {
    let mut stack = Vec::with_capacity(list.len());
    for i in 0..list.len() {
        let item = list.get_item(i)?;
        let bytes_obj = item.call_method1("to_bytes", (32, "big"))?;
        let bytes: Vec<u8> = bytes_obj.extract()?;
        let mut buf = [0u8; 32];
        let start = 32usize.saturating_sub(bytes.len());
        buf[start..].copy_from_slice(&bytes);
        stack.push(U256::from_big_endian(&buf));
    }
    Ok(stack)
}

fn stack_to_pylist<'py>(py: Python<'py>, stack: &[U256]) -> PyResult<Bound<'py, PyList>> {
    let builtins = py.import_bound("builtins")?;
    let int_cls = builtins.getattr("int")?;
    let out = PyList::empty_bound(py);
    for value in stack {
        let bytes = u256_to_be32(*value);
        let obj = int_cls.call_method1("from_bytes", (bytes.as_slice(), "big"))?;
        out.append(obj)?;
    }
    Ok(out)
}

fn write_word(memory: &mut Vec<u8>, offset: usize, value: U256) {
    mem_extend(memory, offset, 32);
    memory[offset..offset + 32].copy_from_slice(&u256_to_be32(value));
}

fn memory_copy(memory: &mut Vec<u8>, dest: usize, src: &[u8], src_offset: usize, size: usize) {
    mem_extend(memory, dest, size);
    for i in 0..size {
        let byte = src.get(src_offset + i).copied().unwrap_or(0);
        memory[dest + i] = byte;
    }
}

fn memory_copy_within(memory: &mut Vec<u8>, dest: usize, src: usize, size: usize) {
    if size == 0 {
        return;
    }
    mem_extend(memory, dest.max(src), size);
    if dest == src {
        return;
    }
    let chunk = memory[src..src + size].to_vec();
    memory[dest..dest + size].copy_from_slice(&chunk);
}

fn result_dict(
    py: Python<'_>,
    pc: usize,
    gas_used: u64,
    running: bool,
    reverted: bool,
    return_data: Vec<u8>,
    stop_reason: &str,
    host_opcode: Option<u8>,
    error: Option<String>,
    steps: usize,
    stack: Bound<'_, PyList>,
    memory: Bound<'_, PyByteArray>,
) -> PyResult<PyObject> {
    let dict = PyDict::new_bound(py);
    dict.set_item("pc", pc)?;
    dict.set_item("gas_used", gas_used)?;
    dict.set_item("running", running)?;
    dict.set_item("reverted", reverted)?;
    dict.set_item("return_data", return_data)?;
    dict.set_item("stop_reason", stop_reason)?;
    dict.set_item("host_opcode", host_opcode)?;
    dict.set_item("error", error)?;
    dict.set_item("steps", steps)?;
    dict.set_item("stack", stack)?;
    dict.set_item("memory", memory)?;
    Ok(dict.into())
}

fn run_pure_segment_inner(
    py: Python<'_>,
    bytecode: &[u8],
    pc: usize,
    gas_limit: u64,
    gas_used: u64,
    stack_py: &Bound<'_, PyList>,
    memory_py: &Bound<'_, PyByteArray>,
    jumpdest_table: &[u8],
    calldata: &[u8],
    return_data_in: &[u8],
    host_context: Option<&Bound<'_, PyDict>>,
    storage: Option<&Bound<'_, PyDict>>,
    host_bridge: Option<&Bound<'_, PyAny>>,
    max_steps: usize,
) -> PyResult<PyObject> {
    if pc >= bytecode.len() {
        let stack = stack_to_pylist(py, &stack_from_py(stack_py)?)?;
        return result_dict(
            py,
            pc,
            gas_used,
            false,
            false,
            Vec::new(),
            "halt",
            None,
            None,
            0,
            stack,
            memory_py.clone(),
        );
    }

    let mut stack = stack_from_py(stack_py)?;
    let mut memory = unsafe { memory_py.as_bytes() }.to_vec();
    let mut pc = pc;
    let mut gas_used = gas_used;
    let mut running = true;
    let mut reverted = false;
    let mut return_data = return_data_in.to_vec();
    let mut steps = 0usize;
    let mut handoff = false;
    let static_ctx = parse_static_context(host_context)?;
    let mut transient: HashMap<U256, U256> = HashMap::new();

    while pc < bytecode.len() && running && steps < max_steps {
        let op = bytecode[pc];
        if opcode_stops_segment(op, host_context, host_bridge) {
            break;
        }

        if (op == 0x54 || op == 0x55) && storage.is_none() {
            handoff = true;
            break;
        }

        let cost = if (0xA0..=0xA4).contains(&op) {
            0
        } else {
            gas_cost(op)
        };
        if cost > 0 {
            if let Err(reason) = consume_gas(&mut gas_used, gas_limit, cost) {
                running = false;
                let stack = stack_to_pylist(py, &stack)?;
                let memory_out = PyByteArray::new_bound(py, &memory);
                return result_dict(
                    py,
                    pc,
                    gas_used,
                    running,
                    reverted,
                    return_data,
                    reason,
                    None,
                    Some(reason.to_string()),
                    steps,
                    stack,
                    memory_out,
                );
            }
        }

        steps += 1;

        let step_result: PyResult<Option<bool>> = (|| -> PyResult<Option<bool>> {
            match op {
                0x00 => {
                    running = false;
                    Ok(Some(false))
                }
                0x01 => {
                    let a = stack_pop(&mut stack)?;
                    let b = stack_pop(&mut stack)?;
                    stack_push(&mut stack, (a.overflowing_add(b).0) & U256_MASK);
                    Ok(Some(false))
                }
                0x02 => {
                    let a = stack_pop(&mut stack)?;
                    let b = stack_pop(&mut stack)?;
                    stack_push(&mut stack, (a.overflowing_mul(b).0) & U256_MASK);
                    Ok(Some(false))
                }
                0x03 => {
                    let a = stack_pop(&mut stack)?;
                    let b = stack_pop(&mut stack)?;
                    stack_push(&mut stack, (a.overflowing_sub(b).0) & U256_MASK);
                    Ok(Some(false))
                }
                0x04 => {
                    let a = stack_pop(&mut stack)?;
                    let b = stack_pop(&mut stack)?;
                    stack_push(&mut stack, evm_u256_div_inner(a, b));
                    Ok(Some(false))
                }
                0x05 => {
                    let a = stack_pop(&mut stack)?;
                    let b = stack_pop(&mut stack)?;
                    stack_push(&mut stack, evm_u256_sdiv_inner(a, b));
                    Ok(Some(false))
                }
                0x06 => {
                    let a = stack_pop(&mut stack)?;
                    let b = stack_pop(&mut stack)?;
                    stack_push(&mut stack, evm_u256_mod_inner(a, b));
                    Ok(Some(false))
                }
                0x07 => {
                    let a = stack_pop(&mut stack)?;
                    let b = stack_pop(&mut stack)?;
                    stack_push(&mut stack, evm_u256_smod_inner(a, b));
                    Ok(Some(false))
                }
                0x08 => {
                    let modulo = stack_pop(&mut stack)?;
                    let b = stack_pop(&mut stack)?;
                    let a = stack_pop(&mut stack)?;
                    stack_push(&mut stack, evm_u256_addmod_inner(a, b, modulo));
                    Ok(Some(false))
                }
                0x09 => {
                    let modulo = stack_pop(&mut stack)?;
                    let b = stack_pop(&mut stack)?;
                    let a = stack_pop(&mut stack)?;
                    stack_push(&mut stack, evm_u256_mulmod_inner(a, b, modulo));
                    Ok(Some(false))
                }
                0x0A => {
                    let exp = stack_pop(&mut stack)?;
                    let base = stack_pop(&mut stack)?;
                    stack_push(&mut stack, evm_u256_exp_inner(base, exp));
                    Ok(Some(false))
                }
                0x0B => {
                    let k = stack_pop(&mut stack)?;
                    let x = stack_pop(&mut stack)?;
                    stack_push(&mut stack, evm_u256_signextend_inner(k.as_u32(), x));
                    Ok(Some(false))
                }
                0x10 => {
                    let a = stack_pop(&mut stack)?;
                    let b = stack_pop(&mut stack)?;
                    stack_push(&mut stack, a & b);
                    Ok(Some(false))
                }
                0x11 => {
                    let a = stack_pop(&mut stack)?;
                    let b = stack_pop(&mut stack)?;
                    stack_push(&mut stack, a | b);
                    Ok(Some(false))
                }
                0x12 => {
                    let a = stack_pop(&mut stack)?;
                    let b = stack_pop(&mut stack)?;
                    stack_push(&mut stack, a ^ b);
                    Ok(Some(false))
                }
                0x13 => {
                    let a = stack_pop(&mut stack)?;
                    let b = stack_pop(&mut stack)?;
                    stack_push(&mut stack, evm_u256_slt_inner(b, a));
                    Ok(Some(false))
                }
                0x14 => {
                    let a = stack_pop(&mut stack)?;
                    let b = stack_pop(&mut stack)?;
                    stack_push(&mut stack, evm_u256_eq_inner(a, b));
                    Ok(Some(false))
                }
                0x15 => {
                    let v = stack_pop(&mut stack)?;
                    stack_push(&mut stack, evm_u256_iszero_inner(v));
                    Ok(Some(false))
                }
                0x16 => {
                    let a = stack_pop(&mut stack)?;
                    let b = stack_pop(&mut stack)?;
                    stack_push(&mut stack, evm_u256_lt_inner(a, b));
                    Ok(Some(false))
                }
                0x17 => {
                    let a = stack_pop(&mut stack)?;
                    let b = stack_pop(&mut stack)?;
                    stack_push(&mut stack, evm_u256_gt_inner(a, b));
                    Ok(Some(false))
                }
                0x18 => {
                    let a = stack_pop(&mut stack)?;
                    let b = stack_pop(&mut stack)?;
                    stack_push(&mut stack, evm_u256_slt_inner(a, b));
                    Ok(Some(false))
                }
                0x19 => {
                    let v = stack_pop(&mut stack)?;
                    stack_push(&mut stack, !v);
                    Ok(Some(false))
                }
                0x1A => {
                    let i = stack_pop(&mut stack)?;
                    let x = stack_pop(&mut stack)?;
                    stack_push(&mut stack, evm_u256_byte_inner(i.as_u32(), x));
                    Ok(Some(false))
                }
                0x1B => {
                    let shift = stack_pop(&mut stack)?;
                    let v = stack_pop(&mut stack)?;
                    stack_push(&mut stack, v << shift.as_u32());
                    Ok(Some(false))
                }
                0x1C => {
                    let shift = stack_pop(&mut stack)?;
                    let v = stack_pop(&mut stack)?;
                    stack_push(&mut stack, v >> shift.as_u32());
                    Ok(Some(false))
                }
                0x1D => {
                    let shift = stack_pop(&mut stack)?;
                    let v = stack_pop(&mut stack)?;
                    stack_push(&mut stack, evm_u256_sar_inner(v, shift.as_u32()));
                    Ok(Some(false))
                }
                0x20 => {
                    let offset = stack_pop(&mut stack)?.as_usize();
                    let size = stack_pop(&mut stack)?.as_usize();
                    mem_extend(&mut memory, offset, size);
                    let digest = evm_keccak256_memory_inner(&memory, offset, size);
                    stack_push(&mut stack, u256_from_be32(digest));
                    Ok(Some(false))
                }
                0x35 => {
                    let offset = stack_pop(&mut stack)?.as_usize();
                    let word = evm_calldataload_inner(calldata, offset);
                    stack_push(&mut stack, u256_from_be32(word));
                    Ok(Some(false))
                }
                0x36 => {
                    stack_push(&mut stack, U256::from(calldata.len()));
                    Ok(Some(false))
                }
                0x37 => {
                    let dest = stack_pop(&mut stack)?.as_usize();
                    let offset = stack_pop(&mut stack)?.as_usize();
                    let size = stack_pop(&mut stack)?.as_usize();
                    memory_copy(&mut memory, dest, calldata, offset, size);
                    Ok(Some(false))
                }
                0x38 => {
                    stack_push(&mut stack, U256::from(bytecode.len()));
                    Ok(Some(false))
                }
                0x39 => {
                    let dest = stack_pop(&mut stack)?.as_usize();
                    let offset = stack_pop(&mut stack)?.as_usize();
                    let size = stack_pop(&mut stack)?.as_usize();
                    memory_copy(&mut memory, dest, bytecode, offset, size);
                    Ok(Some(false))
                }
                0x3D => {
                    stack_push(&mut stack, U256::from(return_data.len()));
                    Ok(Some(false))
                }
                0x3E => {
                    let dest = stack_pop(&mut stack)?.as_usize();
                    let offset = stack_pop(&mut stack)?.as_usize();
                    let size = stack_pop(&mut stack)?.as_usize();
                    memory_copy(&mut memory, dest, return_data_in, offset, size);
                    Ok(Some(false))
                }
                0x30 => {
                    stack_push(&mut stack, static_ctx.address);
                    Ok(Some(false))
                }
                0x32 => {
                    stack_push(&mut stack, static_ctx.origin);
                    Ok(Some(false))
                }
                0x33 => {
                    stack_push(&mut stack, static_ctx.caller);
                    Ok(Some(false))
                }
                0x34 => {
                    stack_push(&mut stack, static_ctx.value);
                    Ok(Some(false))
                }
                0x42 => {
                    stack_push(&mut stack, static_ctx.timestamp);
                    Ok(Some(false))
                }
                0x43 => {
                    stack_push(&mut stack, static_ctx.block_number);
                    Ok(Some(false))
                }
                0x45 => {
                    stack_push(&mut stack, U256::from(gas_limit));
                    Ok(Some(false))
                }
                0x46 => {
                    stack_push(&mut stack, static_ctx.chain_id);
                    Ok(Some(false))
                }
                0x47 => {
                    stack_push(
                        &mut stack,
                        resolve_balance(host_context, host_bridge, static_ctx.address)?,
                    );
                    Ok(Some(false))
                }
                0x48 => {
                    stack_push(&mut stack, static_ctx.base_fee);
                    Ok(Some(false))
                }
                0x49 => {
                    let index = stack_pop(&mut stack)?.as_usize();
                    let val = static_ctx
                        .blob_hashes
                        .get(index)
                        .copied()
                        .unwrap_or(U256::zero());
                    stack_push(&mut stack, val);
                    Ok(Some(false))
                }
                0x4A => {
                    stack_push(&mut stack, static_ctx.blob_base_fee);
                    Ok(Some(false))
                }
                0x3A => {
                    stack_push(&mut stack, static_ctx.gas_price);
                    Ok(Some(false))
                }
                0x41 => {
                    stack_push(&mut stack, static_ctx.coinbase);
                    Ok(Some(false))
                }
                0x44 => {
                    stack_push(&mut stack, static_ctx.difficulty);
                    Ok(Some(false))
                }
                0x31 => {
                    let who = stack_pop(&mut stack)?;
                    stack_push(
                        &mut stack,
                        resolve_balance(host_context, host_bridge, who)?,
                    );
                    Ok(Some(false))
                }
                0x3B => {
                    let who = stack_pop(&mut stack)?;
                    stack_push(
                        &mut stack,
                        resolve_code_size(host_context, host_bridge, who)?,
                    );
                    Ok(Some(false))
                }
                0x3F => {
                    let who = stack_pop(&mut stack)?;
                    stack_push(
                        &mut stack,
                        resolve_code_hash(host_context, host_bridge, who)?,
                    );
                    Ok(Some(false))
                }
                0x3C => {
                    let code_offset = stack_pop(&mut stack)?.as_usize();
                    let mem_offset = stack_pop(&mut stack)?.as_usize();
                    let size = stack_pop(&mut stack)?.as_usize();
                    let who = stack_pop(&mut stack)?;
                    let chunk = resolve_code_copy(
                        host_context,
                        host_bridge,
                        who,
                        code_offset,
                        size,
                    )?;
                    memory_copy(&mut memory, mem_offset, &chunk, 0, size);
                    Ok(Some(false))
                }
                0x40 => {
                    let block_num = stack_pop(&mut stack)?;
                    stack_push(
                        &mut stack,
                        resolve_block_hash(host_context, host_bridge, block_num)?,
                    );
                    Ok(Some(false))
                }
                0x50 => {
                    stack_pop(&mut stack)?;
                    Ok(Some(false))
                }
                0x51 => {
                    let offset = stack_pop(&mut stack)?.as_usize();
                    mem_extend(&mut memory, offset, 32);
                    let word = evm_memory_read_word_inner(&memory, offset);
                    stack_push(&mut stack, u256_from_be32(word));
                    Ok(Some(false))
                }
                0x52 => {
                    let offset = stack_pop(&mut stack)?.as_usize();
                    let value = stack_pop(&mut stack)?;
                    write_word(&mut memory, offset, value);
                    Ok(Some(false))
                }
                0x53 => {
                    let offset = stack_pop(&mut stack)?.as_usize();
                    let value = stack_pop(&mut stack)?;
                    mem_extend(&mut memory, offset, 1);
                    memory[offset] = (value.as_u32() & 0xff) as u8;
                    Ok(Some(false))
                }
                0x54 => {
                    let key = stack_pop(&mut stack)?;
                    stack_push(&mut stack, storage_load(storage, key)?);
                    Ok(Some(false))
                }
                0x55 => {
                    let key = stack_pop(&mut stack)?;
                    let value = stack_pop(&mut stack)?;
                    storage_store(storage, key, value)?;
                    Ok(Some(false))
                }
                0x56 => {
                    let dest = stack_pop(&mut stack)?.as_usize();
                    if !evm_is_jumpdest_inner(jumpdest_table, dest, bytecode.len()) {
                        Err(pyo3::exceptions::PyRuntimeError::new_err("invalid_jump"))
                    } else {
                        pc = dest;
                        Ok(Some(true))
                    }
                }
                0x57 => {
                    let dest = stack_pop(&mut stack)?.as_usize();
                    let cond = stack_pop(&mut stack)?;
                    if !cond.is_zero() {
                        if !evm_is_jumpdest_inner(jumpdest_table, dest, bytecode.len()) {
                            Err(pyo3::exceptions::PyRuntimeError::new_err("invalid_jump"))
                        } else {
                            pc = dest;
                            Ok(Some(true))
                        }
                    } else {
                        Ok(Some(false))
                    }
                }
                0x5A => {
                    stack_push(
                        &mut stack,
                        U256::from(gas_limit.saturating_sub(gas_used)),
                    );
                    Ok(Some(false))
                }
                0x5B => Ok(Some(false)),
                0x5C => {
                    let key = stack_pop(&mut stack)?;
                    let value = transient.get(&key).copied().unwrap_or(U256::zero());
                    stack_push(&mut stack, value);
                    Ok(Some(false))
                }
                0x5D => {
                    let key = stack_pop(&mut stack)?;
                    let value = stack_pop(&mut stack)?;
                    if value.is_zero() {
                        transient.remove(&key);
                    } else {
                        transient.insert(key, value);
                    }
                    Ok(Some(false))
                }
                0x5E => {
                    let length = stack_pop(&mut stack)?.as_usize();
                    let src = stack_pop(&mut stack)?.as_usize();
                    let dest = stack_pop(&mut stack)?.as_usize();
                    let words = ((length + 31) / 32) as u64;
                    if consume_gas(&mut gas_used, gas_limit, 3 * words).is_err() {
                        running = false;
                    } else {
                        memory_copy_within(&mut memory, dest, src, length);
                    }
                    Ok(Some(false))
                }
                0x58 => {
                    stack_push(&mut stack, U256::from(pc));
                    Ok(Some(false))
                }
                0x59 => {
                    stack_push(
                        &mut stack,
                        U256::from(evm_memory_active_bytes(memory.len())),
                    );
                    Ok(Some(false))
                }
                0x5F => {
                    stack_push(&mut stack, U256::zero());
                    Ok(Some(false))
                }
                0xF3 => {
                    let offset = stack_pop(&mut stack)?.as_usize();
                    let size = stack_pop(&mut stack)?.as_usize();
                    return_data = evm_memory_slice_inner(&memory, offset, size);
                    running = false;
                    Ok(Some(false))
                }
                0xFD => {
                    let offset = stack_pop(&mut stack)?.as_usize();
                    let size = stack_pop(&mut stack)?.as_usize();
                    return_data = evm_memory_slice_inner(&memory, offset, size);
                    reverted = true;
                    running = false;
                    Ok(Some(false))
                }
                0xFE => Err(pyo3::exceptions::PyRuntimeError::new_err("invalid_opcode")),
                op if (0x60..=0x7F).contains(&op) => {
                    let n = (op - 0x5F) as usize;
                    let word = evm_read_push_inner(bytecode, pc, n);
                    stack_push(&mut stack, u256_from_be32(word));
                    pc += n;
                    Ok(Some(false))
                }
                op if (0x80..=0x8F).contains(&op) => {
                    stack_dup(&mut stack, (op - 0x7F) as usize)?;
                    Ok(Some(false))
                }
                op if (0x90..=0x9F).contains(&op) => {
                    stack_swap(&mut stack, (op - 0x8F) as usize)?;
                    Ok(Some(false))
                }
                op if (0xA0..=0xA4).contains(&op) => {
                    if let Some(emit_log) = hook_emit_log(host_context) {
                        execute_log_hook(
                            py,
                            &emit_log,
                            op,
                            &mut stack,
                            &mut memory,
                            &mut gas_used,
                            gas_limit,
                        )?;
                        Ok(Some(false))
                    } else if bridge_supports_runtime(host_bridge) {
                        let bridge = host_bridge.ok_or_else(|| {
                            pyo3::exceptions::PyRuntimeError::new_err("host_bridge_unavailable")
                        })?;
                        apply_runtime_host_op(
                            py,
                            bridge,
                            op,
                            &mut stack,
                            &mut memory,
                            gas_limit,
                            &mut gas_used,
                            storage,
                            &mut return_data,
                            &mut running,
                            &mut reverted,
                        )?;
                        Ok(Some(false))
                    } else {
                        handoff = true;
                        Ok(None)
                    }
                }
                op if evm_opcode_is_host(op) => {
                    let bridge = host_bridge.ok_or_else(|| {
                        pyo3::exceptions::PyRuntimeError::new_err("host_bridge_unavailable")
                    })?;
                    apply_runtime_host_op(
                        py,
                        bridge,
                        op,
                        &mut stack,
                        &mut memory,
                        gas_limit,
                        &mut gas_used,
                        storage,
                        &mut return_data,
                        &mut running,
                        &mut reverted,
                    )?;
                    Ok(Some(false))
                }
                _ => Ok(None),
            }
        })();

        match step_result {
            Ok(None) => {
                handoff = true;
                break;
            }
            Ok(Some(true)) => continue,
            Ok(Some(false)) => {}
            Err(err) => {
                let error_msg = err.to_string();
                running = false;
                let stop = if error_msg.contains("out_of_gas") {
                    "out_of_gas"
                } else {
                    "error"
                };
                let stack = stack_to_pylist(py, &stack)?;
                let memory_out = PyByteArray::new_bound(py, &memory);
                return result_dict(
                    py,
                    pc,
                    gas_used,
                    running,
                    reverted,
                    return_data,
                    stop,
                    None,
                    Some(error_msg),
                    steps,
                    stack,
                    memory_out,
                );
            }
        }

        pc += 1;
    }

    let stop_reason = if handoff {
        "handoff"
    } else if steps >= max_steps && running {
        "handoff"
    } else if pc < bytecode.len() && opcode_stops_segment(bytecode[pc], host_context, host_bridge) {
        "host"
    } else if !running {
        if reverted {
            "revert"
        } else if !return_data.is_empty() {
            "return"
        } else {
            "halt"
        }
    } else {
        "halt"
    };

    let host_opcode = if stop_reason == "host" {
        Some(bytecode[pc])
    } else {
        None
    };

    let stack = stack_to_pylist(py, &stack)?;
    let memory_out = PyByteArray::new_bound(py, &memory);
    result_dict(
        py,
        pc,
        gas_used,
        running,
        reverted,
        return_data,
        stop_reason,
        host_opcode,
        None,
        steps,
        stack,
        memory_out,
    )
}

#[pyfunction]
#[pyo3(name = "evm_opcode_is_bridge")]
pub fn evm_opcode_is_bridge_py(op: u8) -> PyResult<bool> {
    Ok(evm_opcode_is_bridge(op))
}

#[pyfunction]
#[pyo3(name = "evm_opcode_is_host")]
pub fn evm_opcode_is_host_py(op: u8) -> PyResult<bool> {
    Ok(evm_opcode_is_host(op))
}

#[pyfunction]
#[pyo3(name = "evm_run_pure_until_host")]
#[pyo3(signature = (bytecode, pc, gas_limit, gas_used, stack, memory, jumpdest_table, calldata, return_data, host_context=None, storage=None, host_bridge=None))]
pub fn evm_run_pure_until_host_py(
    py: Python<'_>,
    bytecode: Vec<u8>,
    pc: usize,
    gas_limit: u64,
    gas_used: u64,
    stack: &Bound<'_, PyList>,
    memory: &Bound<'_, PyByteArray>,
    jumpdest_table: Vec<u8>,
    calldata: Vec<u8>,
    return_data: Vec<u8>,
    host_context: Option<&Bound<'_, PyDict>>,
    storage: Option<&Bound<'_, PyDict>>,
    host_bridge: Option<&Bound<'_, PyAny>>,
) -> PyResult<PyObject> {
    run_pure_segment_inner(
        py,
        &bytecode,
        pc,
        gas_limit,
        gas_used,
        stack,
        memory,
        &jumpdest_table,
        &calldata,
        &return_data,
        host_context,
        storage,
        host_bridge,
        MAX_PURE_STEPS,
    )
}

#[pyfunction]
#[pyo3(name = "evm_run_until_halt")]
#[pyo3(signature = (bytecode, pc, gas_limit, gas_used, stack, memory, jumpdest_table, calldata, return_data, host_context=None, storage=None, host_bridge=None))]
pub fn evm_run_until_halt_py(
    py: Python<'_>,
    bytecode: Vec<u8>,
    pc: usize,
    gas_limit: u64,
    gas_used: u64,
    stack: &Bound<'_, PyList>,
    memory: &Bound<'_, PyByteArray>,
    jumpdest_table: Vec<u8>,
    calldata: Vec<u8>,
    return_data: Vec<u8>,
    host_context: Option<&Bound<'_, PyDict>>,
    storage: Option<&Bound<'_, PyDict>>,
    host_bridge: Option<&Bound<'_, PyAny>>,
) -> PyResult<PyObject> {
    run_pure_segment_inner(
        py,
        &bytecode,
        pc,
        gas_limit,
        gas_used,
        stack,
        memory,
        &jumpdest_table,
        &calldata,
        &return_data,
        host_context,
        storage,
        host_bridge,
        MAX_FULL_STEPS,
    )
}
