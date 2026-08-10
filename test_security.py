import os
from cryptography.fernet import Fernet
os.environ["LOOKOUT_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
from lookout.security import encrypt_secret, decrypt_secret

def test_roundtrip():
    value="secret-token"
    assert decrypt_secret(encrypt_secret(value)) == value
