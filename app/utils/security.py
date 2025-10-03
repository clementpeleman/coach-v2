"""Security utilities for password encryption and decryption."""
import os
from cryptography.fernet import Fernet
import base64
import hashlib


def get_encryption_key() -> bytes:
    """Get or generate encryption key from environment variable.

    The key should be stored in ENCRYPTION_KEY environment variable.
    If not present, this will raise an error.

    Returns:
        Encryption key as bytes
    """
    key_string = os.getenv("ENCRYPTION_KEY")
    if not key_string:
        raise ValueError(
            "ENCRYPTION_KEY not found in environment variables. "
            "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )

    # Ensure the key is properly formatted
    try:
        return key_string.encode()
    except Exception as e:
        raise ValueError(f"Invalid encryption key format: {e}")


def encrypt_password(password: str) -> str:
    """Encrypt a password using Fernet symmetric encryption.

    Args:
        password: Plain text password to encrypt

    Returns:
        Encrypted password as a string
    """
    key = get_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(password.encode('utf-8'))
    return encrypted.decode('utf-8')


def decrypt_password(encrypted_password: str) -> str:
    """Decrypt an encrypted password.

    Args:
        encrypted_password: Encrypted password to decrypt

    Returns:
        Decrypted password as plain text
    """
    key = get_encryption_key()
    f = Fernet(key)
    decrypted = f.decrypt(encrypted_password.encode('utf-8'))
    return decrypted.decode('utf-8')
