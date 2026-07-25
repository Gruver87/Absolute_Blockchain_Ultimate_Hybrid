//! Fail-closed NDJSON line framer for P2P ingress (v1.3.86).
//! Extracts complete newline-terminated frames from a byte stream without
//! relying on asyncio `readline` (still not a Rust TCP transport).

use crate::p2p_wire::{clamp_max_bytes, DEFAULT_MAX_P2P_LINE_BYTES};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList};

/// Buffered NDJSON framer: push chunks → complete lines (incl. trailing `\n`).
#[pyclass]
pub struct P2PLineFramer {
    buf: Vec<u8>,
    max_bytes: usize,
    /// Discard until next `\n` after an oversize reject (resync).
    skip_until_newline: bool,
    oversize_rejects: u64,
}

impl P2PLineFramer {
    /// Pure-Rust constructor for fuzz / unit tests (same clamp as PyO3 `new`).
    pub fn rust_new(max_bytes: usize) -> Self {
        Self {
            buf: Vec::new(),
            max_bytes: clamp_max_bytes(max_bytes),
            skip_until_newline: false,
            oversize_rejects: 0,
        }
    }

    /// Pure-Rust feed for fuzz harnesses.
    pub fn rust_feed(&mut self, chunk: &[u8]) -> Result<Vec<Vec<u8>>, String> {
        self.feed_inner(chunk)
    }

    fn feed_inner(&mut self, chunk: &[u8]) -> Result<Vec<Vec<u8>>, String> {
        let mut out: Vec<Vec<u8>> = Vec::new();
        let mut i = 0usize;
        while i < chunk.len() {
            if self.skip_until_newline {
                if let Some(rel) = chunk[i..].iter().position(|&b| b == b'\n') {
                    i = i + rel + 1;
                    self.skip_until_newline = false;
                    self.buf.clear();
                    continue;
                }
                // Entire remainder discarded until a future newline.
                return Ok(out);
            }

            if let Some(rel) = chunk[i..].iter().position(|&b| b == b'\n') {
                let end = i + rel + 1; // include `\n`
                let piece = &chunk[i..end];
                if self.buf.len().saturating_add(piece.len()) > self.max_bytes {
                    // Complete-but-oversize line: drop it (v1.3.86 fail-closed).
                    self.oversize_rejects = self.oversize_rejects.saturating_add(1);
                    self.buf.clear();
                    return Err("p2p_line_too_large".to_string());
                }
                self.buf.extend_from_slice(piece);
                out.push(std::mem::take(&mut self.buf));
                i = end;
                continue;
            }

            // No newline in remainder — append and check pending size.
            let rest = &chunk[i..];
            if self.buf.len().saturating_add(rest.len()) > self.max_bytes {
                self.oversize_rejects = self.oversize_rejects.saturating_add(1);
                self.buf.clear();
                self.skip_until_newline = true;
                return Err("p2p_line_too_large".to_string());
            }
            self.buf.extend_from_slice(rest);
            break;
        }
        Ok(out)
    }
}

#[pymethods]
impl P2PLineFramer {
    #[new]
    #[pyo3(signature = (max_bytes=DEFAULT_MAX_P2P_LINE_BYTES))]
    fn new(max_bytes: usize) -> Self {
        Self {
            buf: Vec::new(),
            max_bytes: clamp_max_bytes(max_bytes),
            skip_until_newline: false,
            oversize_rejects: 0,
        }
    }

    #[getter]
    fn max_bytes(&self) -> usize {
        self.max_bytes
    }

    #[getter]
    fn pending_len(&self) -> usize {
        self.buf.len()
    }

    #[getter]
    fn oversize_rejects(&self) -> u64 {
        self.oversize_rejects
    }

    #[getter]
    fn skipping(&self) -> bool {
        self.skip_until_newline
    }

    /// Reset buffer and resync state.
    fn clear(&mut self) {
        self.buf.clear();
        self.skip_until_newline = false;
    }

    /// Feed bytes. Returns `{ok:true, lines:[bytes...]}` or `{ok:false, reason}`.
    /// v1.3.86: fail-closed when a line would exceed `max_bytes` before `\n`.
    fn feed(&mut self, py: Python<'_>, chunk: &[u8]) -> PyResult<PyObject> {
        match self.feed_inner(chunk) {
            Ok(lines) => {
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", true)?;
                let list = PyList::empty_bound(py);
                for line in lines {
                    list.append(PyBytes::new_bound(py, &line))?;
                }
                dict.set_item("lines", list)?;
                Ok(dict.into_any().unbind())
            }
            Err(reason) => {
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", false)?;
                dict.set_item("reason", reason)?;
                dict.set_item("lines", PyList::empty_bound(py))?;
                Ok(dict.into_any().unbind())
            }
        }
    }
}

/// One-shot helper: feed chunk into a temporary framer (tests / scripting).
#[pyfunction]
#[pyo3(signature = (chunk, max_bytes=DEFAULT_MAX_P2P_LINE_BYTES))]
fn p2p_frame_feed_once(
    py: Python<'_>,
    chunk: &[u8],
    max_bytes: usize,
) -> PyResult<PyObject> {
    let mut framer = P2PLineFramer::new(max_bytes);
    framer.feed(py, chunk)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<P2PLineFramer>()?;
    m.add_function(wrap_pyfunction!(p2p_frame_feed_once, m)?)?;
    Ok(())
}
