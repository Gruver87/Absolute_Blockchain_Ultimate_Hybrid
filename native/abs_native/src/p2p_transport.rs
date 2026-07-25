//! Native P2P TCP transport slice (v1.3.90).
//!
//! Blocking TcpListener / TcpStream + NDJSON line framer.
//! Python remains the control plane (handshake, dispatch, gossip).
//! Honesty: not TLS, not full async message loop, not libp2p.

use crate::p2p_frame::P2PLineFramer;
use crate::p2p_wire::{clamp_max_bytes, DEFAULT_MAX_P2P_LINE_BYTES};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream, ToSocketAddrs};
use std::time::Duration;

fn io_err(e: std::io::Error) -> String {
    format!("p2p_transport_io:{e}")
}

fn set_timeouts(stream: &TcpStream, timeout_ms: u64) -> Result<(), String> {
    let dur = if timeout_ms == 0 {
        None
    } else {
        Some(Duration::from_millis(timeout_ms))
    };
    stream.set_read_timeout(dur).map_err(io_err)?;
    stream.set_write_timeout(dur).map_err(io_err)?;
    Ok(())
}

fn peer_addr_string(stream: &TcpStream) -> String {
    stream
        .peer_addr()
        .map(|a| a.to_string())
        .unwrap_or_default()
}

fn split_host_port(addr: &str) -> (String, u16) {
    if let Ok(sa) = addr.parse::<SocketAddr>() {
        return (sa.ip().to_string(), sa.port());
    }
    if let Some((h, p)) = addr.rsplit_once(':') {
        if let Ok(port) = p.parse::<u16>() {
            return (h.trim_matches(|c| c == '[' || c == ']').to_string(), port);
        }
    }
    (addr.to_string(), 0)
}

/// One TCP peer connection with fail-closed NDJSON framing.
#[pyclass]
pub struct P2PNativeConn {
    stream: TcpStream,
    framer: P2PLineFramer,
    pending: Vec<Vec<u8>>,
    max_bytes: usize,
    peer_host: String,
    peer_port: u16,
    bytes_read: u64,
    bytes_written: u64,
    lines_read: u64,
    closed: bool,
}

impl P2PNativeConn {
    fn from_stream(stream: TcpStream, max_bytes: usize, timeout_ms: u64) -> Result<Self, String> {
        set_timeouts(&stream, timeout_ms)?;
        let peer = peer_addr_string(&stream);
        let (host, port) = split_host_port(&peer);
        Ok(Self {
            stream,
            framer: P2PLineFramer::rust_new(max_bytes),
            pending: Vec::new(),
            max_bytes: clamp_max_bytes(max_bytes),
            peer_host: host,
            peer_port: port,
            bytes_read: 0,
            bytes_written: 0,
            lines_read: 0,
            closed: false,
        })
    }

    fn read_line_inner(&mut self, chunk_sz: usize) -> Result<Option<Vec<u8>>, String> {
        if self.closed {
            return Ok(None);
        }
            if let Some(line) = self.pending.first().cloned() {
                self.pending.remove(0);
                return Ok(Some(line));
            }
        let mut buf = vec![0u8; chunk_sz.max(1024)];
        loop {
            match self.stream.read(&mut buf) {
                Ok(0) => {
                    if self.framer.pending_len_rust() > 0 {
                        self.framer.clear_rust();
                        return Err("p2p_line_incomplete".to_string());
                    }
                    self.closed = true;
                    return Ok(None);
                }
                Ok(n) => {
                    self.bytes_read = self.bytes_read.saturating_add(n as u64);
                    match self.framer.rust_feed(&buf[..n]) {
                        Ok(lines) => {
                            if lines.is_empty() {
                                continue;
                            }
                            let mut iter = lines.into_iter();
                            let first = iter.next().unwrap();
                            self.pending.extend(iter);
                            self.lines_read = self.lines_read.saturating_add(1);
                            return Ok(Some(first));
                        }
                        Err(reason) => return Err(reason),
                    }
                }
                Err(e)
                    if e.kind() == std::io::ErrorKind::WouldBlock
                        || e.kind() == std::io::ErrorKind::TimedOut =>
                {
                    return Err("p2p_transport_timeout".to_string());
                }
                Err(e) => {
                    self.closed = true;
                    return Err(io_err(e));
                }
            }
        }
    }

    fn write_inner(&mut self, data: &[u8]) -> Result<usize, String> {
        if self.closed {
            return Err("p2p_transport_closed".to_string());
        }
        match self.stream.write_all(data) {
            Ok(()) => {
                self.bytes_written = self.bytes_written.saturating_add(data.len() as u64);
                let _ = self.stream.flush();
                Ok(data.len())
            }
            Err(e)
                if e.kind() == std::io::ErrorKind::WouldBlock
                    || e.kind() == std::io::ErrorKind::TimedOut =>
            {
                Err("p2p_transport_timeout".to_string())
            }
            Err(e) => {
                self.closed = true;
                Err(io_err(e))
            }
        }
    }
}

#[pymethods]
impl P2PNativeConn {
    /// Outbound connect (plain TCP).
    #[staticmethod]
    #[pyo3(signature = (host, port, max_bytes=DEFAULT_MAX_P2P_LINE_BYTES, timeout_ms=10_000))]
    fn connect(
        py: Python<'_>,
        host: &str,
        port: u16,
        max_bytes: usize,
        timeout_ms: u64,
    ) -> PyResult<Self> {
        let addr = format!("{host}:{port}");
        let timeout = Duration::from_millis(timeout_ms.max(1));
        let stream = py.allow_threads(|| {
            let sock_addr = addr
                .to_socket_addrs()
                .map_err(|e| e.to_string())?
                .next()
                .ok_or_else(|| "p2p_transport_resolve_failed".to_string())?;
            TcpStream::connect_timeout(&sock_addr, timeout).map_err(|e| e.to_string())
        })
        .map_err(pyo3::exceptions::PyOSError::new_err)?;
        Self::from_stream(stream, max_bytes, timeout_ms)
            .map_err(pyo3::exceptions::PyOSError::new_err)
    }

    #[getter]
    fn peer_host(&self) -> &str {
        &self.peer_host
    }

    #[getter]
    fn peer_port(&self) -> u16 {
        self.peer_port
    }

    #[getter]
    fn max_bytes(&self) -> usize {
        self.max_bytes
    }

    #[getter]
    fn bytes_read(&self) -> u64 {
        self.bytes_read
    }

    #[getter]
    fn bytes_written(&self) -> u64 {
        self.bytes_written
    }

    #[getter]
    fn lines_read(&self) -> u64 {
        self.lines_read
    }

    #[getter]
    fn closed(&self) -> bool {
        self.closed
    }

    /// `{ok:true, line:bytes|None}` or `{ok:false, reason}`. None line = EOF.
    #[pyo3(signature = (chunk_sz=65536))]
    fn read_line(&mut self, py: Python<'_>, chunk_sz: usize) -> PyResult<PyObject> {
        let result = py.allow_threads(|| self.read_line_inner(chunk_sz));
        match result {
            Ok(Some(line)) => {
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", true)?;
                dict.set_item("line", PyBytes::new_bound(py, &line))?;
                dict.set_item("eof", false)?;
                Ok(dict.into_any().unbind())
            }
            Ok(None) => {
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", true)?;
                dict.set_item("line", py.None())?;
                dict.set_item("eof", true)?;
                Ok(dict.into_any().unbind())
            }
            Err(reason) => {
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", false)?;
                dict.set_item("reason", reason)?;
                dict.set_item("line", py.None())?;
                dict.set_item("eof", false)?;
                Ok(dict.into_any().unbind())
            }
        }
    }

    fn write(&mut self, py: Python<'_>, data: &[u8]) -> PyResult<usize> {
        let data = data.to_vec();
        py.allow_threads(|| self.write_inner(&data))
            .map_err(pyo3::exceptions::PyOSError::new_err)
    }

    fn set_timeout_ms(&mut self, timeout_ms: u64) -> PyResult<()> {
        set_timeouts(&self.stream, timeout_ms).map_err(pyo3::exceptions::PyOSError::new_err)
    }

    fn shutdown(&mut self) {
        let _ = self.stream.shutdown(std::net::Shutdown::Both);
        self.closed = true;
    }

    fn close(&mut self) {
        self.shutdown();
    }
}

/// Plain TCP listener (accept with timeout via socket2).
#[pyclass]
pub struct P2PNativeListener {
    listener: TcpListener,
    max_bytes: usize,
    timeout_ms: u64,
    accepts: u64,
    accept_timeouts: u64,
    accept_errors: u64,
}

#[pymethods]
impl P2PNativeListener {
    #[new]
    #[pyo3(signature = (host="0.0.0.0", port=5000, max_bytes=DEFAULT_MAX_P2P_LINE_BYTES, timeout_ms=1000))]
    fn new(host: &str, port: u16, max_bytes: usize, timeout_ms: u64) -> PyResult<Self> {
        use socket2::{Domain, Protocol, Socket, Type};
        let addr: SocketAddr = format!("{host}:{port}")
            .parse()
            .or_else(|_| {
                format!("{host}:{port}")
                    .to_socket_addrs()
                    .ok()
                    .and_then(|mut i| i.next())
                    .ok_or(())
            })
            .map_err(|_| {
                pyo3::exceptions::PyOSError::new_err(format!("bad bind addr {host}:{port}"))
            })?;
        let domain = if addr.is_ipv4() {
            Domain::IPV4
        } else {
            Domain::IPV6
        };
        let socket = Socket::new(domain, Type::STREAM, Some(Protocol::TCP))
            .map_err(|e| pyo3::exceptions::PyOSError::new_err(e.to_string()))?;
        socket
            .set_reuse_address(true)
            .map_err(|e| pyo3::exceptions::PyOSError::new_err(e.to_string()))?;
        socket
            .bind(&addr.into())
            .map_err(|e| pyo3::exceptions::PyOSError::new_err(format!("bind {addr}: {e}")))?;
        socket
            .listen(128)
            .map_err(|e| pyo3::exceptions::PyOSError::new_err(e.to_string()))?;
        let timeout = Duration::from_millis(timeout_ms.max(1));
        socket
            .set_read_timeout(Some(timeout))
            .map_err(|e| pyo3::exceptions::PyOSError::new_err(e.to_string()))?;
        let listener: TcpListener = socket.into();
        Ok(Self {
            listener,
            max_bytes: clamp_max_bytes(max_bytes),
            timeout_ms: timeout_ms.max(1),
            accepts: 0,
            accept_timeouts: 0,
            accept_errors: 0,
        })
    }

    #[getter]
    fn local_addr(&self) -> String {
        self.listener
            .local_addr()
            .map(|a| a.to_string())
            .unwrap_or_default()
    }

    #[getter]
    fn timeout_ms(&self) -> u64 {
        self.timeout_ms
    }

    #[getter]
    fn accepts(&self) -> u64 {
        self.accepts
    }

    #[getter]
    fn accept_timeouts(&self) -> u64 {
        self.accept_timeouts
    }

    #[getter]
    fn accept_errors(&self) -> u64 {
        self.accept_errors
    }

    /// `{ok:true, conn:P2PNativeConn|None}` — None means timed out with no connection.
    /// `{ok:false, reason}` on hard error.
    fn accept(&mut self, py: Python<'_>) -> PyResult<PyObject> {
        let result = py.allow_threads(|| self.listener.accept());
        match result {
            Ok((stream, _addr)) => match P2PNativeConn::from_stream(stream, self.max_bytes, 30_000)
            {
                Ok(conn) => {
                    self.accepts = self.accepts.saturating_add(1);
                    let dict = PyDict::new_bound(py);
                    dict.set_item("ok", true)?;
                    dict.set_item("conn", Py::new(py, conn)?)?;
                    Ok(dict.into_any().unbind())
                }
                Err(reason) => {
                    self.accept_errors = self.accept_errors.saturating_add(1);
                    let dict = PyDict::new_bound(py);
                    dict.set_item("ok", false)?;
                    dict.set_item("reason", reason)?;
                    Ok(dict.into_any().unbind())
                }
            },
            Err(e)
                if e.kind() == std::io::ErrorKind::WouldBlock
                    || e.kind() == std::io::ErrorKind::TimedOut =>
            {
                self.accept_timeouts = self.accept_timeouts.saturating_add(1);
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", true)?;
                dict.set_item("conn", py.None())?;
                Ok(dict.into_any().unbind())
            }
            Err(e) => {
                self.accept_errors = self.accept_errors.saturating_add(1);
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", false)?;
                dict.set_item("reason", io_err(e))?;
                Ok(dict.into_any().unbind())
            }
        }
    }

    fn close(&mut self) {
        // Dropping listener closes the fd; keep method for Python symmetry.
    }
}

/// Marker for status / needles (v1.3.90).
#[pyfunction]
fn p2p_native_transport_available() -> bool {
    true
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<P2PNativeConn>()?;
    m.add_class::<P2PNativeListener>()?;
    m.add_function(wrap_pyfunction!(p2p_native_transport_available, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use std::net::TcpStream;
    use std::thread;

    #[test]
    fn framed_roundtrip_local() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = listener.local_addr().unwrap();
        let handle = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            stream.write_all(b"{\"type\":\"ping\",\"data\":null}\n").unwrap();
            let mut buf = [0u8; 64];
            let n = stream.read(&mut buf).unwrap();
            assert!(n > 0);
        });
        let client = TcpStream::connect(addr).unwrap();
        let mut conn = P2PNativeConn::from_stream(client, 1024 * 1024, 5_000).unwrap();
        let line = conn.read_line_inner(4096).unwrap().unwrap();
        assert!(line.starts_with(b"{\"type\":\"ping\""));
        conn.write_inner(b"{\"type\":\"pong\",\"data\":null}\n").unwrap();
        handle.join().unwrap();
    }
}
