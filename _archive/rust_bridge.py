# rust_bridge.py - Python bindings for Rust blockchain components
import ctypes
import os
import json
from typing import Optional, Dict, Any

class RustBlockchain:
    """Python wrapper for Rust blockchain components"""
    
    def __init__(self):
        self.lib = None
        self._load_library()
    
    def _load_library(self):
        """Load Rust dynamic library"""
        lib_paths = [
            "rust_blockchain/target/release/absolute_blockchain.dll",
            "rust_blockchain/target/release/libabsolute_blockchain.so",
            "rust_blockchain/target/release/libabsolute_blockchain.dylib"
        ]
        
        for path in lib_paths:
            if os.path.exists(path):
                self.lib = ctypes.CDLL(path)
                break
        
        if self.lib:
            # Define function signatures
            self.lib.rust_mining_ffi.argtypes = [ctypes.c_uint64]
            self.lib.rust_mining_ffi.restype = ctypes.c_char_p
            
            self.lib.rust_validate_transaction_ffi.argtypes = [ctypes.c_char_p]
            self.lib.rust_validate_transaction_ffi.restype = ctypes.c_int
    
    def mining_ready(self, difficulty: int) -> str:
        """Check if Rust mining engine is ready"""
        if self.lib:
            result = self.lib.rust_mining_ffi(difficulty)
            return result.decode('utf-8') if result else "Error"
        return "Rust library not loaded"
    
    def validate_transaction(self, tx_data: str) -> bool:
        """Validate transaction using Rust"""
        if self.lib:
            result = self.lib.rust_validate_transaction_ffi(tx_data.encode())
            return result == 1
        return False
    
    def is_available(self) -> bool:
        """Check if Rust component is available"""
        return self.lib is not None

# Create global instance
rust_blockchain = RustBlockchain()

if rust_blockchain.is_available():
    print("🦀 Rust blockchain component loaded!")
    print(f"   Mining engine: {rust_blockchain.mining_ready(4)}")
else:
    print("⚠️ Rust component not available. Run 'cd rust_blockchain && cargo build --release'")
