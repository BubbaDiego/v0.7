#!/usr/bin/env python3
import os
import sys

# 1. Make sure your project root is on the path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, PROJECT_ROOT)

# 2. Import DataLocker
from data.data_locker import DataLocker

# 3. Define your wallets list exactly as given
wallets = [
    {
        "name": "R2Vault",
        "public_address": "Gwk8DdAZPyonAcxfJDs7fZazC2bDKmpASWsBEbtxvAY6",
        "private_address": "",
        "image_path": "\\static\\images\\r2vault.jpg",
        "balance": 1.23
    },
    {
        "name": "LandoVault",
        "public_address": "6vMjsGU63evYuwwGsDHBRnKs1stALR7SYN5V57VZLXca",
        "private_address": "6vMjsGU63evYuwwGsDHBRnKs1stALR7SYN5V57VZLXca",
        "image_path": "1.23",
        "balance": 1.23
    }
]

def main():
    # Initialize the singleton DataLocker
    dl = DataLocker.get_instance()

    for w in wallets:
        try:
            dl.create_wallet(w)
            print(f"✅ Inserted wallet: {w['name']}")
        except Exception as e:
            print(f"❌ Failed to insert {w['name']}: {e}")

if __name__ == "__main__":
    main()
