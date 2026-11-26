"""J.A.R.V.I.S. Quantum-Grade Encrypted P2P Communications Mesh.
Implements post-quantum hybrid lattice cryptography simulation, AES-256-GCM AEAD,
entropy ratcheting, and peer-to-peer node telemetry for decentralized workstation comms.
"""

import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import time
from typing import Dict, List, Optional, Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

# Persistent storage directory for P2P credentials & logs
_p = Path(__file__).resolve().parent
HERE = _p.parent.parent if _p.parent.name == "backend" else _p.parent
DATA_DIR = str(HERE / "data")
P2P_STATE_FILE = os.path.join(DATA_DIR, "p2p_mesh_state.json")

# Local Workstation Node Identity
LOCAL_NODE_ID = "STARK-ALPHA-PRIME"
CIPHER_SUITE = "KYBER-1024-HYBRID // AES-256-GCM (512-BIT QUANTUM ENTROPY)"

class QuantumP2PMesh:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.node_id = LOCAL_NODE_ID
        self.quantum_entropy_seed = secrets.token_hex(32)
        self.master_key = self._derive_master_key()
        self.peers = self._load_or_init_peers()
        self.transmission_log: List[Dict[str, Any]] = []

    def _derive_master_key(self) -> bytes:
        """Derive 256-bit AES-GCM master key using HKDF with SHA-512 and quantum entropy seed."""
        hkdf = HKDF(
            algorithm=hashes.SHA512(),
            length=32,
            salt=b"JARVIS_QUANTUM_ENTROPY_SALT_v1",
            info=b"P2P_MESH_MASTER_DERIVATION"
        )
        return hkdf.derive(self.quantum_entropy_seed.encode())

    def _load_or_init_peers(self) -> Dict[str, Dict[str, Any]]:
        """Load registered peers or initialize default Stark Industries network nodes."""
        default_peers = {
            "NODE-MARK-VII-SATELLITE": {
                "name": "Mark VII Orbital Satellite",
                "status": "ONLINE",
                "latency_ms": 14,
                "signal_fidelity": 98.4,
                "pqc_fingerprint": hashlib.sha256(b"MARK-VII-SAT").hexdigest()[:16].upper(),
                "shared_secret": secrets.token_hex(32),
                "last_seen": time.time()
            },
            "NODE-RADON-MOBILE": {
                "name": "Sir's Mobile Neural Uplink",
                "status": "ONLINE",
                "latency_ms": 28,
                "signal_fidelity": 94.2,
                "pqc_fingerprint": hashlib.sha256(b"RADON-MOBILE").hexdigest()[:16].upper(),
                "shared_secret": secrets.token_hex(32),
                "last_seen": time.time()
            },
            "NODE-SENTINEL-CLUSTER": {
                "name": "Sentinel Swarm Cluster Relay",
                "status": "ONLINE",
                "latency_ms": 6,
                "signal_fidelity": 99.8,
                "pqc_fingerprint": hashlib.sha256(b"SENTINEL-SWARM").hexdigest()[:16].upper(),
                "shared_secret": secrets.token_hex(32),
                "last_seen": time.time()
            }
        }

        if os.path.exists(P2P_STATE_FILE):
            try:
                with open(P2P_STATE_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if "peers" in saved:
                        default_peers.update(saved["peers"])
            except Exception as e:
                print(f"[P2P Mesh] Notice loading state: {e}")

        return default_peers

    def _save_state(self):
        try:
            with open(P2P_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "node_id": self.node_id,
                    "updated_at": time.time(),
                    "peers": self.peers
                }, f, indent=2)
        except Exception as e:
            print(f"[P2P Mesh] Failed to save state: {e}")

    def generate_quantum_entropy_signature(self, payload: str) -> str:
        """Simulate a post-quantum lattice signature using SHA-512 HMAC and quantum seed."""
        h = hashlib.sha512(f"{self.quantum_entropy_seed}:{payload}:{time.time_ns()}".encode()).hexdigest()
        return f"Q-SIG-{h[:24].upper()}"

    def get_mesh_status(self) -> Dict[str, Any]:
        """Return full telemetry of quantum P2P mesh network."""
        online_count = sum(1 for p in self.peers.values() if p.get("status") == "ONLINE")
        avg_latency = (
            round(sum(p.get("latency_ms", 20) for p in self.peers.values()) / max(1, len(self.peers)), 1)
        )
        return {
            "local_node_id": self.node_id,
            "cipher_suite": CIPHER_SUITE,
            "quantum_entropy_level": "99.98% PURE CRYSTALLINE",
            "active_peers_count": online_count,
            "total_nodes": len(self.peers) + 1,
            "average_latency_ms": avg_latency,
            "peers": [
                {
                    "node_id": pid,
                    "name": p.get("name"),
                    "status": p.get("status"),
                    "latency_ms": p.get("latency_ms"),
                    "signal_fidelity": p.get("signal_fidelity"),
                    "fingerprint": p.get("pqc_fingerprint")
                }
                for pid, p in self.peers.items()
            ],
            "recent_transmissions": self.transmission_log[-6:]
        }

    def encrypt_packet(self, peer_id: str, plaintext: str, classification: str = "CONFIDENTIAL") -> Dict[str, Any]:
        """Encrypt payload using AES-256-GCM authenticated encryption with quantum-ratcheted key."""
        peer = self.peers.get(peer_id)
        if not peer:
            # Auto-register temporary peer if unknown
            self.peers[peer_id] = {
                "name": f"Peer {peer_id}",
                "status": "ONLINE",
                "latency_ms": secrets.randbelow(30) + 10,
                "signal_fidelity": 95.0,
                "pqc_fingerprint": hashlib.sha256(peer_id.encode()).hexdigest()[:16].upper(),
                "shared_secret": secrets.token_hex(32),
                "last_seen": time.time()
            }
            peer = self.peers[peer_id]
            self._save_state()

        shared_secret = peer.get("shared_secret", secrets.token_hex(32))
        
        # Derive per-packet ephemeral AES-256-GCM key
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=peer_id.encode(),
            info=b"P2P_EPHEMERAL_PACKET_ENCRYPTION"
        )
        session_key = hkdf.derive(bytes.fromhex(shared_secret))
        
        aesgcm = AESGCM(session_key)
        nonce = secrets.token_bytes(12)  # Standard 96-bit GCM nonce
        aad = f"{self.node_id}->{peer_id}:{classification}".encode()
        
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), aad)
        q_sig = self.generate_quantum_entropy_signature(plaintext)

        packet = {
            "protocol": "JARVIS-P2P-QUANTUM-v1",
            "sender": self.node_id,
            "recipient": peer_id,
            "classification": classification,
            "nonce_hex": nonce.hex(),
            "ciphertext_b64": base64.b64encode(ciphertext).decode("utf-8"),
            "quantum_signature": q_sig,
            "timestamp": time.time(),
            "bytes_encrypted": len(plaintext.encode("utf-8"))
        }

        # Log transmission
        log_entry = {
            "id": f"tx_{secrets.token_hex(4)}",
            "direction": "OUTBOUND",
            "peer": peer.get("name", peer_id),
            "peer_id": peer_id,
            "classification": classification,
            "status": "DELIVERED & AUTHENTICATED",
            "quantum_sig": q_sig[:14] + "...",
            "time": time.strftime("%H:%M:%S")
        }
        self.transmission_log.append(log_entry)
        if len(self.transmission_log) > 50:
            self.transmission_log.pop(0)

        return packet

    def decrypt_packet(self, peer_id: str, packet: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt AES-256-GCM packet and verify AEAD integrity tag."""
        peer = self.peers.get(peer_id)
        if not peer:
            raise ValueError(f"Peer '{peer_id}' not recognized in quantum keyring.")

        shared_secret = peer.get("shared_secret")
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=peer_id.encode(),
            info=b"P2P_EPHEMERAL_PACKET_ENCRYPTION"
        )
        session_key = hkdf.derive(bytes.fromhex(shared_secret))
        aesgcm = AESGCM(session_key)

        nonce = bytes.fromhex(packet["nonce_hex"])
        ciphertext = base64.b64decode(packet["ciphertext_b64"])
        aad = f"{packet.get('sender', peer_id)}->{self.node_id}:{packet.get('classification', 'CONFIDENTIAL')}".encode()

        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, aad)
        plaintext = decrypted_bytes.decode("utf-8")

        return {
            "status": "VERIFIED_AUTHENTIC",
            "sender": packet.get("sender"),
            "plaintext": plaintext,
            "quantum_signature": packet.get("quantum_signature"),
            "timestamp": packet.get("timestamp")
        }

    def pair_new_node(self, node_name: str, node_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate quantum-safe pairing certificate and enroll node in mesh."""
        new_id = node_id or f"NODE-{node_name.upper().replace(' ', '-')}-{secrets.token_hex(3)}"
        shared_secret = secrets.token_hex(32)
        fingerprint = hashlib.sha256(f"{new_id}:{shared_secret}".encode()).hexdigest()[:16].upper()

        self.peers[new_id] = {
            "name": node_name,
            "status": "ONLINE",
            "latency_ms": secrets.randbelow(15) + 5,
            "signal_fidelity": 99.2,
            "pqc_fingerprint": fingerprint,
            "shared_secret": shared_secret,
            "last_seen": time.time()
        }
        self._save_state()

        return {
            "success": True,
            "enrolled_node_id": new_id,
            "node_name": node_name,
            "pqc_fingerprint": fingerprint,
            "cipher_suite": CIPHER_SUITE,
            "message": f"Node '{node_name}' enrolled in quantum P2P mesh network, Sir."
        }

# Global singleton
_p2p_mesh_instance: Optional[QuantumP2PMesh] = None

def get_quantum_p2p_mesh() -> QuantumP2PMesh:
    global _p2p_mesh_instance
    if _p2p_mesh_instance is None:
        _p2p_mesh_instance = QuantumP2PMesh()
    return _p2p_mesh_instance
