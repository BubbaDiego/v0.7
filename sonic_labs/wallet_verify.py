import asyncio
import json
import os

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TokenAccountOpts

# Constants
KEYPAIR_PATH = r"C:\v0.7\sonic_labs\solana_keypair.json"  # Path to your local keypair JSON
USDC_MINT = Pubkey.from_string(
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
)  # USDC mint on Solana mainnet-beta

async def verify_wallet():
    # Load local keypair
    try:
        with open(KEYPAIR_PATH, 'r') as f:
            secret = json.load(f)
        sol_keypair = Keypair.from_bytes(bytes(secret))
        owner = sol_keypair.pubkey()  # solders Pubkey
    except Exception as e:
        print(f"❌ Failed to load keypair: {e}")
        return

    print(f"🔑 Wallet public key: {owner}")

    # Connect to Solana mainnet-beta
    client = AsyncClient("https://api.mainnet-beta.solana.com")

    # Check SOL balance
    sol_resp = await client.get_balance(owner, commitment=Confirmed)
    lamports = sol_resp.value  # use .value for solders GetBalanceResp
    sol_amt = lamports / 1e9
    print(f"☀️ SOL balance: {sol_amt:.9f} SOL ({lamports} lamports)")

    # Check USDC associated token accounts
    token_resp = await client.get_token_accounts_by_owner(
        owner,
        TokenAccountOpts(mint=USDC_MINT),  # use solders Pubkey directly
        commitment=Confirmed,
    )
    accounts = token_resp.value  # list of TokenAccount objects
    if not accounts:
        print("❌ No USDC associated token account found.")
    else:
        for acct in accounts:
            ata_pub = acct.pubkey  # solders Pubkey already
            bal_resp = await client.get_token_account_balance(ata_pub, commitment=Confirmed)
            ui_amt = bal_resp.value.ui_amount
            print(f"💵 USDC ATA: {ata_pub} -> {ui_amt} USDC")

    await client.close()

if __name__ == '__main__':
    asyncio.run(verify_wallet())
