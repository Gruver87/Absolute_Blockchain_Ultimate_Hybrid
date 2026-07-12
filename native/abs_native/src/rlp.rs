//! Ethereum RLP encode/decode (Yellow Paper rules).

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyList};

#[derive(Debug, Clone)]
enum RlpItem {
    Bytes(Vec<u8>),
    List(Vec<RlpItem>),
}

fn int_to_bytes(value: u64) -> Vec<u8> {
    if value == 0 {
        return Vec::new();
    }
    let bits = 64 - value.leading_zeros() as usize;
    let len = (bits + 7) / 8;
    value.to_be_bytes()[8 - len..].to_vec()
}

fn bytes_to_usize(buf: &[u8]) -> Result<usize, String> {
    if buf.len() > std::mem::size_of::<usize>() {
        return Err("rlp_truncated".into());
    }
    let mut out = [0u8; std::mem::size_of::<usize>()];
    out[std::mem::size_of::<usize>() - buf.len()..].copy_from_slice(buf);
    Ok(usize::from_be_bytes(out))
}

fn py_integer_to_bytes(value: &Bound<'_, PyAny>) -> PyResult<Vec<u8>> {
    if value.eq(0i64)? {
        return Ok(Vec::new());
    }
    let bit_length: usize = value.call_method0("bit_length")?.extract()?;
    let length = (bit_length + 7) / 8;
    let bytes: Vec<u8> = value.call_method1("to_bytes", (length, "big"))?.extract()?;
    Ok(bytes)
}

fn py_to_rlp_item(value: &Bound<'_, PyAny>) -> PyResult<RlpItem> {
    if let Ok(list) = value.downcast::<PyList>() {
        let mut children = Vec::with_capacity(list.len());
        for item in list.iter() {
            children.push(py_to_rlp_item(&item)?);
        }
        return Ok(RlpItem::List(children));
    }
    if let Ok(raw) = value.extract::<Vec<u8>>() {
        return Ok(RlpItem::Bytes(raw));
    }
    if let Ok(raw) = value.extract::<&[u8]>() {
        return Ok(RlpItem::Bytes(raw.to_vec()));
    }
    if let Ok(num) = value.extract::<i64>() {
        return Ok(RlpItem::Bytes(int_to_bytes(num as u64)));
    }
    if value.is_instance_of::<PyBytes>() {
        let raw: &Bound<'_, PyBytes> = value.downcast()?;
        return Ok(RlpItem::Bytes(raw.as_bytes().to_vec()));
    }
    if let Ok(num) = value.extract::<u64>() {
        return Ok(RlpItem::Bytes(int_to_bytes(num)));
    }
    if value.call_method0("bit_length").is_ok() {
        return Ok(RlpItem::Bytes(py_integer_to_bytes(value)?));
    }
    Err(PyValueError::new_err("unsupported_rlp_item"))
}

fn normalize_scalar(data: &[u8]) -> Vec<u8> {
    if data.len() == 1 && data[0] <= 0x7F {
        return data.to_vec();
    }
    if data.is_empty() {
        return vec![0x80];
    }
    if data.len() == 1 && data[0] < 0x80 {
        return data.to_vec();
    }
    let mut out = Vec::with_capacity(1 + data.len());
    out.push(0x80 + data.len() as u8);
    out.extend_from_slice(data);
    out
}

fn encode_item(item: &RlpItem) -> Vec<u8> {
    match item {
        RlpItem::Bytes(data) => normalize_scalar(data),
        RlpItem::List(children) => {
            let payload: Vec<u8> = children.iter().flat_map(encode_item).collect();
            if payload.len() <= 55 {
                let mut out = Vec::with_capacity(1 + payload.len());
                out.push(0xC0 + payload.len() as u8);
                out.extend_from_slice(&payload);
                return out;
            }
            let len_bytes = int_to_bytes(payload.len() as u64);
            let mut out = Vec::with_capacity(1 + len_bytes.len() + payload.len());
            out.push(0xF7 + len_bytes.len() as u8);
            out.extend_from_slice(&len_bytes);
            out.extend_from_slice(&payload);
            out
        }
    }
}

fn decode_length(data: &[u8], pos: usize, offset: u8) -> Result<(usize, usize), String> {
    if pos >= data.len() {
        return Err("rlp_truncated".into());
    }
    let prefix = data[pos];
    if prefix < offset + 0x37 {
        return Ok(((prefix - offset) as usize, pos + 1));
    }
    let len_of_len = (prefix - (offset + 0x37)) as usize;
    let start = pos + 1;
    let end = start + len_of_len;
    if end > data.len() {
        return Err("rlp_truncated".into());
    }
    let length = bytes_to_usize(&data[start..end])?;
    Ok((length, end))
}

fn decode_at(data: &[u8], pos: usize) -> Result<(RlpItem, usize), String> {
    if pos >= data.len() {
        return Err("rlp_truncated".into());
    }
    let prefix = data[pos];
    if prefix <= 0x7F {
        return Ok((RlpItem::Bytes(vec![prefix]), pos + 1));
    }
    if prefix <= 0xB7 {
        let length = (prefix - 0x80) as usize;
        if length == 0 {
            return Ok((RlpItem::Bytes(Vec::new()), pos + 1));
        }
        let start = pos + 1;
        let end = start + length;
        if end > data.len() {
            return Err("rlp_truncated".into());
        }
        return Ok((RlpItem::Bytes(data[start..end].to_vec()), end));
    }
    if prefix <= 0xBF {
        let (length, next_pos) = decode_length(data, pos, 0x80)?;
        let start = next_pos;
        let end = start + length;
        if end > data.len() {
            return Err("rlp_truncated".into());
        }
        return Ok((RlpItem::Bytes(data[start..end].to_vec()), end));
    }
    if prefix <= 0xF7 {
        let length = (prefix - 0xC0) as usize;
        let start = pos + 1;
        let end = start + length;
        if end > data.len() {
            return Err("rlp_truncated".into());
        }
        let mut items = Vec::new();
        let mut cursor = start;
        while cursor < end {
            let (child, next) = decode_at(data, cursor)?;
            items.push(child);
            cursor = next;
        }
        if cursor != end {
            return Err("rlp_invalid_list".into());
        }
        return Ok((RlpItem::List(items), end));
    }
    let (length, next_pos) = decode_length(data, pos, 0xC0)?;
    let start = next_pos;
    let end = start + length;
    if end > data.len() {
        return Err("rlp_truncated".into());
    }
    let mut items = Vec::new();
    let mut cursor = start;
    while cursor < end {
        let (child, next) = decode_at(data, cursor)?;
        items.push(child);
        cursor = next;
    }
    if cursor != end {
        return Err("rlp_invalid_list".into());
    }
    Ok((RlpItem::List(items), end))
}

fn rlp_item_to_py(py: Python<'_>, item: &RlpItem) -> PyObject {
    match item {
        RlpItem::Bytes(data) => PyBytes::new_bound(py, data).to_object(py),
        RlpItem::List(items) => {
            let list = PyList::empty_bound(py);
            for child in items {
                list.append(rlp_item_to_py(py, child)).expect("append");
            }
            list.to_object(py)
        }
    }
}

#[pyfunction]
pub fn rlp_encode(item: Bound<'_, PyAny>) -> PyResult<Vec<u8>> {
    let rlp = py_to_rlp_item(&item)?;
    Ok(encode_item(&rlp))
}

#[pyfunction]
#[pyo3(signature = (data, pos = 0))]
pub fn rlp_decode(py: Python<'_>, data: &[u8], pos: usize) -> PyResult<(PyObject, usize)> {
    let (item, end) = decode_at(data, pos).map_err(PyValueError::new_err)?;
    Ok((rlp_item_to_py(py, &item), end))
}

#[pyfunction]
pub fn rlp_decode_single(py: Python<'_>, data: &[u8]) -> PyResult<PyObject> {
    let (item, end) = decode_at(data, 0).map_err(PyValueError::new_err)?;
    if end != data.len() {
        return Err(PyValueError::new_err("rlp_trailing_bytes"));
    }
    Ok(rlp_item_to_py(py, &item))
}
