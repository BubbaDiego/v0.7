import json
import random
import asyncio

from anchorpy import Provider, Program, Wallet, Context, Idl
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey

# File paths
KEYPAIR_PATH = r"C:\v0.7\sonic_labs\solana_keypair.json"
IDL_PATH = r"C:\v0.7\sonic_labs\jupiter_perps.json"

# Program & Pool
PROGRAM_ID = Pubkey.from_string("PERPHjGBqRHArX4DySjwM6UJHiR3sWAatqfdBS2qQJu")
POOL_ACCOUNT = Pubkey.from_string("5BUwFW4nRbftYTDMbgxykoFWqWHPzahFSNAaaaJtVKsq")

# Custodies & Mints
CUSTODY_SOL = Pubkey.from_string("7xS2gz2bTp3fwCC7knJvUWTEU9Tycczu6VhJYKgi1wdz")
CUSTODY_USDC = Pubkey.from_string("G18jKKXQwBbrHeiK3C9MRXhkHsLHf7XgCSisykV46EZa")
USDC_MINT = Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
WSOL_MINT = Pubkey.from_string("So11111111111111111111111111111111111111112")

# Static PDAs & Programs
REFERRAL = Pubkey.from_string("11111111111111111111111111111111")
EVENT_AUTHORITY = Pubkey.from_string("37hJBDnntwqhGbK7L6M1bLyvccj4u55CCUiLPdYkiqBN")
SYSVAR_RENT = Pubkey.from_string("SysvarRent111111111111111111111111111111111")
SYS_PROGRAM = Pubkey.from_string("11111111111111111111111111111111")
TOKEN_PROGRAM = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ASSOCIATED_TOKEN_PROGRAM = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")

async def submit_perp_order(
    market: str,
    side: str,
    size_usd: float,
    collateral_usdc: float,
    slippage_bps: int,
):
    # 1. RPC and Provider
    client = AsyncClient("https://api.mainnet-beta.solana.com")
    secret = json.load(open(KEYPAIR_PATH))
    kp = Keypair.from_bytes(bytes(secret))
    wallet = Wallet(kp)
    provider = Provider(client, wallet)

    # 2. Load IDL and Program
    idl = Idl.from_json(open(IDL_PATH).read())
    program = Program(idl, PROGRAM_ID, provider)

    # 3. Resolve accounts
    owner = wallet.public_key
    custody = CUSTODY_SOL if market.upper() == "SOL" else None
    collateral_custody = CUSTODY_USDC
    input_mint = USDC_MINT

    # 4. Derive PDAs
    perp_pda, _ = Pubkey.find_program_address([b"perpetuals"], PROGRAM_ID)
    seed = b"\x01" if side.lower() == "long" else b"\x02"
    position_pda, _ = Pubkey.find_program_address(
        [b"position", bytes(owner), bytes(POOL_ACCOUNT), bytes(custody), bytes(collateral_custody), seed],
        PROGRAM_ID,
    )
    counter = random.getrandbits(32)
    ctr = counter.to_bytes(8, "little")
    pos_req_pda, _ = Pubkey.find_program_address(
        [b"position_request", bytes(position_pda), ctr, b"\x01"],
        PROGRAM_ID,
    )

    # 5. Derive Associated Token Accounts via solders
    funding_ata, _ = Pubkey.find_program_address(
        [bytes(owner), bytes(TOKEN_PROGRAM), bytes(input_mint)],
        ASSOCIATED_TOKEN_PROGRAM,
    )
    pos_req_ata, _ = Pubkey.find_program_address(
        [bytes(pos_req_pda), bytes(TOKEN_PROGRAM), bytes(input_mint)],
        ASSOCIATED_TOKEN_PROGRAM,
    )

    # 6. Build params
    side_enum = program.type["Side"].Long() if side.lower() == "long" else program.type["Side"].Short()
    params = {
        "counter": counter,
        "collateral_token_delta": int(collateral_usdc * 1e6),
        "jupiter_minimum_out": None,
        "price_slippage": slippage_bps,
        "side": side_enum,
        "size_usd_delta": int(size_usd * 1e6),
    }

    # 7. Prepare accounts context
    accounts = {
        "owner": owner,
        "funding_account": funding_ata,
        "perpetuals": perp_pda,
        "pool": POOL_ACCOUNT,
        "position": position_pda,
        "position_request": pos_req_pda,
        "position_request_ata": pos_req_ata,
        "custody": custody,
        "collateral_custody": collateral_custody,
        "input_mint": input_mint,
        "referral": REFERRAL,
        "token_program": TOKEN_PROGRAM,
        "associated_token_program": ASSOCIATED_TOKEN_PROGRAM,
        "system_program": SYS_PROGRAM,
        "rent": SYSVAR_RENT,
        "event_authority": EVENT_AUTHORITY,
        "program": PROGRAM_ID,
    }

    # 8. Send transaction via RPC
    try:
        tx_sig = await program.rpc["create_increase_position_market_request"](
            params,
            ctx=Context(accounts=accounts),
        )
        print(f"✅ Order submitted; tx signature: {tx_sig}")
    except Exception as e:
        print(f"❌ Order failed: {e}")

    await client.close()

if __name__ == "__main__":
    asyncio.run(submit_perp_order("SOL", "short", 110.0, 11.0, 100))
