import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class MockKMS:
    def __init__(self):
        # Generate a 256-bit (32-byte) KEK
        self.kek = os.urandom(32)

    def generate_dek(self):
        # Generate a 256-bit (32-byte) DEK
        return os.urandom(32)

    def encrypt_dek(self, dek):
        # AES-GCM requires a 96-bit (12-byte) IV
        iv = os.urandom(12)
        aesgcm = AESGCM(self.kek)
        # Encrypt the DEK
        ciphertext = aesgcm.encrypt(iv, dek, None)
        return iv, ciphertext

    def decrypt_dek(self, iv, encrypted_dek):
        aesgcm = AESGCM(self.kek)
        # Decrypt the DEK
        return aesgcm.decrypt(iv, encrypted_dek, None)

class VectorDBStorage:
    def encrypt_data(self, dek, plaintext):
        iv = os.urandom(12)
        aesgcm = AESGCM(dek)
        # cryptography library returns ciphertext + 16-byte auth tag together
        encrypted = aesgcm.encrypt(iv, plaintext, None)
        ciphertext = encrypted[:-16]
        tag = encrypted[-16:]
        return iv, tag, ciphertext

    def decrypt_data(self, dek, iv, tag, ciphertext):
        aesgcm = AESGCM(dek)
        # Re-append the 16-byte tag to the ciphertext for decrypting
        encrypted = ciphertext + tag
        return aesgcm.decrypt(iv, encrypted, None)

def main():
    print("=== Envelope Encryption Proof of Concept ===")
    
    csv_filename = 'pii_dataset.csv'
    try:
        with open(csv_filename, 'rb') as f:
            plaintext_data = f.read()
            print(f"Read '{csv_filename}' ({len(plaintext_data)} bytes).")
    except FileNotFoundError:
        print(f"File '{csv_filename}' not found. Creating dummy data...")
        plaintext_data = b"id,name,email,ssn\n1,Alice,alice@example.com,000-00-1111\n"
        with open(csv_filename, 'wb') as f:
            f.write(plaintext_data)
        print(f"Created a dummy '{csv_filename}'.")

    # 1. KMS generates KEK, DEK, and encrypts DEK
    kms = MockKMS()
    dek = kms.generate_dek()
    dek_iv, encrypted_dek = kms.encrypt_dek(dek)
    print("\n[MockKMS] Generated a 256-bit KEK inside MockKMS.")
    print("[MockKMS] Generated a 256-bit DEK.")
    print("[MockKMS] Encrypted DEK with KEK via AES-GCM.")

    # 2. VectorDB Storage encrypts data
    storage = VectorDBStorage()
    data_iv, data_tag, encrypted_data = storage.encrypt_data(dek, plaintext_data)
    print("\n[VectorDBStorage] Encrypted the CSV data safely using the given DEK via AES-GCM.")

    # 3. Save to disk
    with open('encrypted_database.bin', 'wb') as f:
        f.write(data_iv + data_tag + encrypted_data)
    print("\n[Disk] Saved the encrypted data (IV + Tag + Ciphertext) to 'encrypted_database.bin'.")

    with open('encrypted_dek.bin', 'wb') as f:
        f.write(dek_iv + encrypted_dek)
    print("[Disk] Saved the encrypted DEK (IV + encrypted DEK blob) to 'encrypted_dek.bin'.")

    # 4. Decrypt demonstration
    print("\n=== Simulating Decryption Request ===")
    
    # Read files
    with open('encrypted_dek.bin', 'rb') as f:
        read_encrypted_dek = f.read()
        read_dek_iv = read_encrypted_dek[:12]
        read_encrypted_dek_blob = read_encrypted_dek[12:]
    print("[Disk] Loaded 'encrypted_dek.bin'.")

    with open('encrypted_database.bin', 'rb') as f:
        read_encrypted_db = f.read()
        read_data_iv = read_encrypted_db[:12]
        read_data_tag = read_encrypted_db[12:28]
        read_data_ciphertext = read_encrypted_db[28:]
    print("[Disk] Loaded 'encrypted_database.bin'.")

    # KMS decrypts the DEK
    decrypted_dek = kms.decrypt_dek(read_dek_iv, read_encrypted_dek_blob)
    print("\n[MockKMS] Decrypted the DEK using the KEK successfully.")

    # Storage decrypts the database
    decrypted_data = storage.decrypt_data(decrypted_dek, read_data_iv, read_data_tag, read_data_ciphertext)
    print("[VectorDBStorage] Decrypted the data payload using the plaintext DEK.\n")

    if decrypted_data == plaintext_data:
        print("Success! The decrypted payload exactly matches the original plaintext CSV.")
    else:
        print("Error: The decrypted payload does not match the plaintext CSV.")

if __name__ == '__main__':
    main()
