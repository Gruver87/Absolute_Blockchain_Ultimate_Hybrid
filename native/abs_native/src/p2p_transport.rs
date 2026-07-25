//! Native P2P TCP(+TLS) transport (v1.3.90 / v1.3.91).
//!
//! Blocking TcpListener / TcpStream + optional rustls mTLS + NDJSON framer.
//! Python remains the control plane (handshake, dispatch, gossip).
//! Honesty: not libp2p / multiplex; not full async message-loop ownership.

use crate::p2p_frame::P2PLineFramer;
use crate::p2p_wire::{clamp_max_bytes, DEFAULT_MAX_P2P_LINE_BYTES};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};
use rustls::client::danger::{HandshakeSignatureValid, ServerCertVerified, ServerCertVerifier};
use rustls::pki_types::{CertificateDer, PrivateKeyDer, ServerName, UnixTime};
use rustls::server::WebPkiClientVerifier;
use rustls::{
    ClientConfig, ClientConnection, DigitallySignedStruct, Error as TlsError, RootCertStore,
    ServerConfig, ServerConnection, SignatureScheme, StreamOwned,
};
use sha2::{Digest, Sha256};
use std::fs::File;
use std::io::{BufReader, Read, Write};
use std::net::{Shutdown, SocketAddr, TcpListener, TcpStream, ToSocketAddrs};
use std::path::Path;
use std::sync::Arc;
use std::time::Duration;

fn io_err(e: std::io::Error) -> String {
    format!("p2p_transport_io:{e}")
}

fn tls_err(e: impl std::fmt::Display) -> String {
    format!("p2p_transport_tls:{e}")
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

fn load_certs(path: &Path) -> Result<Vec<CertificateDer<'static>>, String> {
    let mut reader = BufReader::new(File::open(path).map_err(io_err)?);
    let certs: Vec<_> = rustls_pemfile::certs(&mut reader)
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| format!("p2p_transport_tls:{e}"))?;
    if certs.is_empty() {
        return Err(format!("p2p_transport_tls:no_certs:{}", path.display()));
    }
    Ok(certs)
}

fn load_private_key(path: &Path) -> Result<PrivateKeyDer<'static>, String> {
    let mut reader = BufReader::new(File::open(path).map_err(io_err)?);
    let mut keys = rustls_pemfile::pkcs8_private_keys(&mut reader)
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| format!("p2p_transport_tls:{e}"))?;
    if let Some(k) = keys.pop() {
        return Ok(PrivateKeyDer::Pkcs8(k));
    }
    let mut reader = BufReader::new(File::open(path).map_err(io_err)?);
    let mut keys = rustls_pemfile::rsa_private_keys(&mut reader)
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| format!("p2p_transport_tls:{e}"))?;
    if let Some(k) = keys.pop() {
        return Ok(PrivateKeyDer::Pkcs1(k));
    }
    Err(format!("p2p_transport_tls:no_private_key:{}", path.display()))
}

fn load_root_store(ca_path: &Path) -> Result<RootCertStore, String> {
    let mut roots = RootCertStore::empty();
    for cert in load_certs(ca_path)? {
        roots
            .add(cert)
            .map_err(|e| tls_err(format!("ca_add:{e}")))?;
    }
    if roots.is_empty() {
        return Err(format!("p2p_transport_tls:empty_ca:{}", ca_path.display()));
    }
    Ok(roots)
}

/// Verify peer cert against CA roots; skip hostname (matches Python check_hostname=False).
#[derive(Debug)]
struct CaOnlyServerVerifier {
    roots: Arc<RootCertStore>,
}

impl ServerCertVerifier for CaOnlyServerVerifier {
    fn verify_server_cert(
        &self,
        end_entity: &CertificateDer<'_>,
        intermediates: &[CertificateDer<'_>],
        _server_name: &ServerName<'_>,
        _ocsp_response: &[u8],
        now: UnixTime,
    ) -> Result<ServerCertVerified, TlsError> {
        let cert = rustls::server::ParsedCertificate::try_from(end_entity)?;
        rustls::client::verify_server_cert_signed_by_trust_anchor(
            &cert,
            &self.roots,
            intermediates,
            now,
            rustls::crypto::ring::default_provider()
                .signature_verification_algorithms
                .all,
        )?;
        Ok(ServerCertVerified::assertion())
    }

    fn verify_tls12_signature(
        &self,
        message: &[u8],
        cert: &CertificateDer<'_>,
        dss: &DigitallySignedStruct,
    ) -> Result<HandshakeSignatureValid, TlsError> {
        rustls::crypto::verify_tls12_signature(
            message,
            cert,
            dss,
            &rustls::crypto::ring::default_provider().signature_verification_algorithms,
        )
    }

    fn verify_tls13_signature(
        &self,
        message: &[u8],
        cert: &CertificateDer<'_>,
        dss: &DigitallySignedStruct,
    ) -> Result<HandshakeSignatureValid, TlsError> {
        rustls::crypto::verify_tls13_signature(
            message,
            cert,
            dss,
            &rustls::crypto::ring::default_provider().signature_verification_algorithms,
        )
    }

    fn supported_verify_schemes(&self) -> Vec<SignatureScheme> {
        rustls::crypto::ring::default_provider()
            .signature_verification_algorithms
            .supported_schemes()
    }
}

fn build_server_config(
    cert_path: &Path,
    key_path: &Path,
    ca_path: &Path,
    require_client_cert: bool,
) -> Result<Arc<ServerConfig>, String> {
    let certs = load_certs(cert_path)?;
    let key = load_private_key(key_path)?;
    let roots = load_root_store(ca_path)?;
    // Industrial default: always require client certs when TLS material is configured
    // (matches Python fail-closed CERT_REQUIRED).
    let _ = require_client_cert;
    let verifier = WebPkiClientVerifier::builder(Arc::new(roots))
        .build()
        .map_err(|e| format!("p2p_transport_tls:{e}"))?;
    let mut cfg = ServerConfig::builder()
        .with_client_cert_verifier(verifier)
        .with_single_cert(certs, key)
        .map_err(|e| format!("p2p_transport_tls:{e}"))?;
    cfg.alpn_protocols.clear();
    Ok(Arc::new(cfg))
}

fn build_client_config(
    cert_path: Option<&Path>,
    key_path: Option<&Path>,
    ca_path: &Path,
) -> Result<Arc<ClientConfig>, String> {
    let roots = Arc::new(load_root_store(ca_path)?);
    let verifier = Arc::new(CaOnlyServerVerifier {
        roots: roots.clone(),
    });
    let builder = ClientConfig::builder().dangerous().with_custom_certificate_verifier(verifier);
    let mut cfg = match (cert_path, key_path) {
        (Some(c), Some(k)) if c.exists() && k.exists() => {
            let certs = load_certs(c)?;
            let key = load_private_key(k)?;
            builder
                .with_client_auth_cert(certs, key)
                .map_err(|e| format!("p2p_transport_tls:{e}"))?
        }
        _ => builder.with_no_client_auth(),
    };
    cfg.alpn_protocols.clear();
    Ok(Arc::new(cfg))
}

enum ConnStream {
    Plain(TcpStream),
    TlsServer(StreamOwned<ServerConnection, TcpStream>),
    TlsClient(StreamOwned<ClientConnection, TcpStream>),
}

impl ConnStream {
    fn tcp_ref(&self) -> &TcpStream {
        match self {
            ConnStream::Plain(s) => s,
            ConnStream::TlsServer(s) => s.get_ref(),
            ConnStream::TlsClient(s) => s.get_ref(),
        }
    }

    fn peer_cert_fingerprint_sha256(&self) -> String {
        let certs = match self {
            ConnStream::Plain(_) => return String::new(),
            ConnStream::TlsServer(s) => s.conn.peer_certificates(),
            ConnStream::TlsClient(s) => s.conn.peer_certificates(),
        };
        let Some(chain) = certs else {
            return String::new();
        };
        let Some(first) = chain.first() else {
            return String::new();
        };
        hex::encode(Sha256::digest(first.as_ref()))
    }

    fn shutdown(&mut self) {
        match self {
            ConnStream::Plain(s) => {
                let _ = s.shutdown(Shutdown::Both);
            }
            ConnStream::TlsServer(s) => {
                let _ = s.flush();
                let _ = s.get_ref().shutdown(Shutdown::Both);
            }
            ConnStream::TlsClient(s) => {
                let _ = s.flush();
                let _ = s.get_ref().shutdown(Shutdown::Both);
            }
        }
    }
}

impl Read for ConnStream {
    fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
        match self {
            ConnStream::Plain(s) => s.read(buf),
            ConnStream::TlsServer(s) => s.read(buf),
            ConnStream::TlsClient(s) => s.read(buf),
        }
    }
}

impl Write for ConnStream {
    fn write(&mut self, buf: &[u8]) -> std::io::Result<usize> {
        match self {
            ConnStream::Plain(s) => s.write(buf),
            ConnStream::TlsServer(s) => s.write(buf),
            ConnStream::TlsClient(s) => s.write(buf),
        }
    }

    fn flush(&mut self) -> std::io::Result<()> {
        match self {
            ConnStream::Plain(s) => s.flush(),
            ConnStream::TlsServer(s) => s.flush(),
            ConnStream::TlsClient(s) => s.flush(),
        }
    }
}

/// One TCP(+TLS) peer connection with fail-closed NDJSON framing.
#[pyclass]
pub struct P2PNativeConn {
    stream: ConnStream,
    framer: P2PLineFramer,
    pending: Vec<Vec<u8>>,
    max_bytes: usize,
    peer_host: String,
    peer_port: u16,
    bytes_read: u64,
    bytes_written: u64,
    lines_read: u64,
    closed: bool,
    tls: bool,
}

impl P2PNativeConn {
    fn from_stream(stream: ConnStream, max_bytes: usize, tls: bool) -> Self {
        let peer = peer_addr_string(stream.tcp_ref());
        let (host, port) = split_host_port(&peer);
        Self {
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
            tls,
        }
    }

    fn from_plain(stream: TcpStream, max_bytes: usize, timeout_ms: u64) -> Result<Self, String> {
        set_timeouts(&stream, timeout_ms)?;
        Ok(Self::from_stream(ConnStream::Plain(stream), max_bytes, false))
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
    /// Outbound connect (plain TCP or rustls TLS when paths set).
    #[staticmethod]
    #[pyo3(signature = (
        host,
        port,
        max_bytes=DEFAULT_MAX_P2P_LINE_BYTES,
        timeout_ms=10_000,
        cert_path=None,
        key_path=None,
        ca_path=None
    ))]
    fn connect(
        py: Python<'_>,
        host: &str,
        port: u16,
        max_bytes: usize,
        timeout_ms: u64,
        cert_path: Option<String>,
        key_path: Option<String>,
        ca_path: Option<String>,
    ) -> PyResult<Self> {
        let addr = format!("{host}:{port}");
        let timeout = Duration::from_millis(timeout_ms.max(1));
        let use_tls = ca_path.as_ref().map(|p| !p.is_empty()).unwrap_or(false);
        let host_owned = host.to_string();
        let cert_path = cert_path.filter(|s| !s.is_empty());
        let key_path = key_path.filter(|s| !s.is_empty());
        let ca_path = ca_path.filter(|s| !s.is_empty());

        py.allow_threads(|| {
            let sock_addr = addr
                .to_socket_addrs()
                .map_err(|e| e.to_string())?
                .next()
                .ok_or_else(|| "p2p_transport_resolve_failed".to_string())?;
            let tcp = TcpStream::connect_timeout(&sock_addr, timeout).map_err(|e| e.to_string())?;
            set_timeouts(&tcp, timeout_ms)?;
            if !use_tls {
                return P2PNativeConn::from_plain(tcp, max_bytes, timeout_ms);
            }
            let ca = Path::new(ca_path.as_ref().unwrap());
            let cfg = build_client_config(
                cert_path.as_ref().map(Path::new),
                key_path.as_ref().map(Path::new),
                ca,
            )?;
            // SNI placeholder — hostname verification disabled (CaOnlyServerVerifier).
            let server_name = ServerName::try_from(host_owned.as_str())
                .or_else(|_| ServerName::try_from("localhost"))
                .map_err(|e| format!("p2p_transport_tls:{e}"))?
                .to_owned();
            let conn = ClientConnection::new(cfg, server_name).map_err(|e| format!("p2p_transport_tls:{e}"))?;
            let mut tls = StreamOwned::new(conn, tcp);
            // Complete handshake eagerly.
            while tls.conn.is_handshaking() {
                tls.conn
                    .complete_io(&mut tls.sock)
                    .map_err(|e| format!("p2p_transport_tls:{e}"))?;
            }
            Ok(P2PNativeConn::from_stream(
                ConnStream::TlsClient(tls),
                max_bytes,
                true,
            ))
        })
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

    #[getter]
    fn tls(&self) -> bool {
        self.tls
    }

    #[getter]
    fn peer_cert_sha256(&self) -> String {
        self.stream.peer_cert_fingerprint_sha256()
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
        set_timeouts(self.stream.tcp_ref(), timeout_ms).map_err(pyo3::exceptions::PyOSError::new_err)
    }

    fn shutdown(&mut self) {
        self.stream.shutdown();
        self.closed = true;
    }

    fn close(&mut self) {
        self.shutdown();
    }
}

/// TCP listener with optional rustls server config (v1.3.91).
#[pyclass]
pub struct P2PNativeListener {
    listener: TcpListener,
    max_bytes: usize,
    timeout_ms: u64,
    accepts: u64,
    accept_timeouts: u64,
    accept_errors: u64,
    tls_config: Option<Arc<ServerConfig>>,
}

#[pymethods]
impl P2PNativeListener {
    #[new]
    #[pyo3(signature = (
        host="0.0.0.0",
        port=5000,
        max_bytes=DEFAULT_MAX_P2P_LINE_BYTES,
        timeout_ms=1000,
        cert_path=None,
        key_path=None,
        ca_path=None,
        require_client_cert=true
    ))]
    fn new(
        host: &str,
        port: u16,
        max_bytes: usize,
        timeout_ms: u64,
        cert_path: Option<String>,
        key_path: Option<String>,
        ca_path: Option<String>,
        require_client_cert: bool,
    ) -> PyResult<Self> {
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

        let tls_config = match (cert_path, key_path, ca_path) {
            (Some(c), Some(k), Some(ca))
                if !c.is_empty() && !k.is_empty() && !ca.is_empty() =>
            {
                Some(
                    build_server_config(
                        Path::new(&c),
                        Path::new(&k),
                        Path::new(&ca),
                        require_client_cert,
                    )
                    .map_err(pyo3::exceptions::PyOSError::new_err)?,
                )
            }
            _ => None,
        };

        Ok(Self {
            listener,
            max_bytes: clamp_max_bytes(max_bytes),
            timeout_ms: timeout_ms.max(1),
            accepts: 0,
            accept_timeouts: 0,
            accept_errors: 0,
            tls_config,
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

    #[getter]
    fn tls(&self) -> bool {
        self.tls_config.is_some()
    }

    /// `{ok:true, conn:P2PNativeConn|None}` — None means timed out with no connection.
    fn accept(&mut self, py: Python<'_>) -> PyResult<PyObject> {
        let result = py.allow_threads(|| self.listener.accept());
        match result {
            Ok((tcp, _addr)) => {
                let built = py.allow_threads(|| -> Result<P2PNativeConn, String> {
                    set_timeouts(&tcp, 30_000)?;
                    if let Some(cfg) = &self.tls_config {
                        let conn =
                            ServerConnection::new(cfg.clone()).map_err(|e| format!("p2p_transport_tls:{e}"))?;
                        let mut tls = StreamOwned::new(conn, tcp);
                        while tls.conn.is_handshaking() {
                            tls.conn
                                .complete_io(&mut tls.sock)
                                .map_err(|e| format!("p2p_transport_tls:{e}"))?;
                        }
                        Ok(P2PNativeConn::from_stream(
                            ConnStream::TlsServer(tls),
                            self.max_bytes,
                            true,
                        ))
                    } else {
                        P2PNativeConn::from_plain(tcp, self.max_bytes, 30_000)
                    }
                });
                match built {
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
                }
            }
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

    fn close(&mut self) {}
}

#[pyfunction]
fn p2p_native_transport_available() -> bool {
    true
}

#[pyfunction]
fn p2p_native_tls_available() -> bool {
    true
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<P2PNativeConn>()?;
    m.add_class::<P2PNativeListener>()?;
    m.add_function(wrap_pyfunction!(p2p_native_transport_available, m)?)?;
    m.add_function(wrap_pyfunction!(p2p_native_tls_available, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::thread;

    #[test]
    fn framed_roundtrip_local_plain() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = listener.local_addr().unwrap();
        let handle = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            stream
                .write_all(b"{\"type\":\"ping\",\"data\":null}\n")
                .unwrap();
            let mut buf = [0u8; 64];
            let n = stream.read(&mut buf).unwrap();
            assert!(n > 0);
        });
        let client = TcpStream::connect(addr).unwrap();
        let mut conn = P2PNativeConn::from_plain(client, 1024 * 1024, 5_000).unwrap();
        let line = conn.read_line_inner(4096).unwrap().unwrap();
        assert!(line.starts_with(b"{\"type\":\"ping\""));
        conn.write_inner(b"{\"type\":\"pong\",\"data\":null}\n").unwrap();
        handle.join().unwrap();
    }
}
