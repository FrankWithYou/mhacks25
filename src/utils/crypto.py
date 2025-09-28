"""
Cryptographic utilities for the marketplace.
Handles message signing and verification for authenticity.
"""

import hashlib
import hmac
from datetime import datetime
from typing import Any, Dict
import json
import logging

logger = logging.getLogger(__name__)


def compute_terms_hash(quote_data: Dict[str, Any]) -> str:
    """
    Compute a deterministic hash of quote terms for integrity verification
    
    Args:
        quote_data: Dictionary containing quote terms
        
    Returns:
        Hex string of the hash
    """
    # Create a canonical representation of the terms
    terms = {
        "task": quote_data.get("task"),
        "payload": quote_data.get("payload"),
        "price": quote_data.get("price"),
        "denom": quote_data.get("denom"),
        "ttl": quote_data.get("ttl"),
        "bond_required": quote_data.get("bond_required")
    }
    
    # Sort keys for deterministic output
    terms_json = json.dumps(terms, sort_keys=True, separators=(',', ':'))
    
    # Compute SHA-256 hash
    return hashlib.sha256(terms_json.encode()).hexdigest()


def sign_message(message: str, private_key: str) -> str:
    """
    Sign a message using HMAC-SHA256 (simplified for MVP)
    
    In production, this would use proper ECDSA signing with the agent's private key
    For the MVP, we use HMAC with a shared secret for simplicity
    
    Args:
        message: Message to sign
        private_key: Private key/secret for signing
        
    Returns:
        Hex-encoded signature
    """
    return hmac.new(
        private_key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()


def verify_signature(message: str, signature: str, public_key: str) -> bool:
    """
    Verify a message signature using HMAC-SHA256 (simplified for MVP)
    
    Args:
        message: Original message
        signature: Signature to verify
        public_key: Public key/secret for verification (same as private key in HMAC)
        
    Returns:
        True if signature is valid
    """
    try:
        expected_signature = sign_message(message, public_key)
        return hmac.compare_digest(signature, expected_signature)
    except Exception as e:
        logger.error(f"Signature verification failed: {e}")
        return False


def create_job_signature(job_id: str, output_ref: str, timestamp: datetime, private_key: str) -> str:
    """
    Create a signature for a job completion receipt
    
    Args:
        job_id: Job identifier
        output_ref: Reference to the output (e.g., URL)
        timestamp: Completion timestamp
        private_key: Agent's private key
        
    Returns:
        Hex-encoded signature
    """
    # Create canonical message for signing
    message = f"{job_id}|{output_ref}|{timestamp.isoformat()}"
    return sign_message(message, private_key)


def verify_job_signature(job_id: str, output_ref: str, timestamp: datetime, 
                        signature: str, public_key: str) -> bool:
    """
    Verify a job completion receipt signature
    
    Args:
        job_id: Job identifier
        output_ref: Reference to the output
        timestamp: Completion timestamp
        signature: Signature to verify
        public_key: Tool agent's public key
        
    Returns:
        True if signature is valid
    """
    message = f"{job_id}|{output_ref}|{timestamp.isoformat()}"
    return verify_signature(message, signature, public_key)


def generate_job_id() -> str:
    """
    Generate a unique job identifier
    
    Returns:
        Unique job ID
    """
    timestamp = datetime.utcnow().isoformat()
    random_bytes = hashlib.sha256(f"{timestamp}|{hash(timestamp)}".encode()).digest()[:8]
    return f"job_{random_bytes.hex()}"


def create_client_signature(job_id: str, terms_hash: str, timestamp: datetime, private_key: str) -> str:
    """
    Create a client signature for job acceptance
    
    Args:
        job_id: Job identifier
        terms_hash: Hash of the accepted terms
        timestamp: Acceptance timestamp
        private_key: Client's private key
        
    Returns:
        Hex-encoded signature
    """
    message = f"{job_id}|{terms_hash}|{timestamp.isoformat()}"
    return sign_message(message, private_key)


def verify_client_signature(job_id: str, terms_hash: str, timestamp: datetime,
                          signature: str, public_key: str) -> bool:
    """
    Verify a client's job acceptance signature
    
    Args:
        job_id: Job identifier
        terms_hash: Hash of the accepted terms
        timestamp: Acceptance timestamp
        signature: Signature to verify
        public_key: Client agent's public key
        
    Returns:
        True if signature is valid
    """
    message = f"{job_id}|{terms_hash}|{timestamp.isoformat()}"
    return verify_signature(message, signature, public_key)