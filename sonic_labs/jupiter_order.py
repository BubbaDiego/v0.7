import json
import random
import asyncio
import os

from anchorpy import Provider, Program, Wallet, Context, Idl
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from spl.token.async_client import AsyncToken
from spl.token.instructions import get_associated_token_address, sync_native, close_account, SyncNativeParams
from spl.token.constants import ASSOCIATED_TOKEN_PROGRAM_ID, TOKEN_PROGRAM_ID
from solana.system_program import SYS_PROGRAM_ID, TransferParams, transfer

# Convert standard program IDs to solders Pubkey
SYS_PROGRAM_PUBKEY = Pubkey.from_string(str(SYS_PROGRAM_ID))
TOKEN_PROGRAM_PUBKEY = Pubkey.from_string(str(TOKEN_PROGRAM_ID))
ASSOCIATED_TOKEN_PROGRAM_PUBKEY = Pubkey.from_string(str(ASSOCIATED_TOKEN_PROGRAM_ID))

# Sysvar Rent
SYSVAR_RENT_PUBKEY = Pubkey.from_string("SysvarRent111111111111111111111111111111111")

# Jupiter Perps Event Authority
EVENT_AUTHORITY = Pubkey.from_string("37hJBDnntwqhGbK7L6M1bLyvccj4u55CCUiLPdYkiqBN")

# Referral default
REFERRAL = Pubkey.from_string("11111111111111111111111111111111")

# Program & Pool
PROGRAM_ID = Pubkey.from_string("PERPHjGBqRHArX4DySjwM6UJHiR3sWAatqfdBS2qQJu")
POOL_ACCOUNT = Pubkey.from_string("5BUwFW4nRbftYTDMbgxykoFWqWHPzahFSNAaaaJtVKsq")

# Custody Accounts
CUSTODY_SOL = Pubkey.from_string("7xS2gz2bTp3fwCC7knJvUWTEU9Tycczu6VhJYKgi1wdz")
CUSTODY_WBTC = Pubkey.from_string("5Pv3gM9JrFFH883SWAhvJC9RPYmo8UNxuFtv5bMMALkm")
CUSTODY_WETH = Pubkey.from_string("AQCGyheWPLeo6Qp9WpYS9m3Qj479t7R636N9ey1rEjEn")
CUSTODY_USDC = Pubkey.from_string("G18jKKXQwBbrHeiK3C9MRXhkHsLHf7XgCSisykV46EZa")

# Mints
USDC_MINT = Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
WSOL_MINT = Pubkey.from_string("So11111111111111111111111111111111111111112")

# Market config
MARKET_CONFIG = {
    "SOL": {"custody": CUSTODY_SOL, "collateral_custody": CUSTODY_USDC, "input_mint": USDC_MINT},
    "WBTC": {"custody": CUSTODY_WBTC, "collateral_custody": CUSTODY_USDC, "input_mint": USDC_MINT},
    "WETH": {"custody": CUSTODY_WETH, "collateral_custody": CUSTODY_USDC, "input_mint": USDC_MINT},
}

async def submit_perp_order(market: str, side: str, size_usd: float, collateral_amount: float, slippage_bps: int):
    # RPC client
    client = AsyncClient("https://api.mainnet-beta.solana.com")

    # Load keypair
    keypair_path = r"C:\v0.7\sonic_labs\solana_keypair.json"
    secret = json.load(open(keypair_path))
    sol_keypair = Keypair.from_bytes(bytes(secret))
    wallet = Wallet(sol_keypair)
    provider = Provider(client, wallet)

    # Load IDL
    idl_path = r"C:\v0.7\sonic_labs\jupiter_perps.json"
    if not os.path.exists(idl_path) or os.path.getsize(idl_path) == 0:
        raise FileNotFoundError(f"IDL missing: {idl_path}")
    raw_idl = open(idl_path).read()
    idl = Idl.from_json(raw_idl)
    program = Program(idl, PROGRAM_ID, provider)

    # Validate market
    m = market.upper()
    if m not in MARKET_CONFIG:
        raise ValueError(f"Unsupported market: {market}")
    cfg = MARKET_CONFIG[m]
    custody = cfg["custody"]
    collateral_custody = cfg["collateral_custody"]
    input_mint = cfg["input_mint"]
    owner = wallet.public_key

    # Derive PDAs using solders Pubkey
    perp_pda, _ = Pubkey.find_program_address([b"perpetuals"], PROGRAM_ID)
    seed_byte = b"\x01" if side.lower() == "long" else b"\x02"
    pos_seeds = [b"position", bytes(owner), bytes(POOL_ACCOUNT), bytes(custody), bytes(collateral_custody), seed_byte]
    position_pda, _ = Pubkey.find_program_address(pos_seeds, PROGRAM_ID)
    counter = random.randrange(1 << 32)
    ctr_bytes = counter.to_bytes(8, 'little')
    req_seeds = [b"position_request", bytes(position_pda), ctr_bytes, b"\x01"]
    pos_req_pda, _ = Pubkey.find_program_address(req_seeds, PROGRAM_ID)

    # Derive associated token accounts correctly
    from solana.publickey import PublicKey as SolPub
    owner_sol = SolPub(str(owner))
    mint_sol = SolPub(str(input_mint))
    req_sol = SolPub(str(pos_req_pda))
    funding_pub = get_associated_token_address(owner_sol, mint_sol)
    funding_account = Pubkey.from_string(str(funding_pub))
    req_ata_pub = get_associated_token_address(req_sol, mint_sol)
    pos_req_ata = Pubkey.from_string(str(req_ata_pub))

    # Pre/post instructions for wrapping SOL
    pre_ixs, post_ixs = [], []
    if input_mint == WSOL_MINT:
        pre_ixs.append(AsyncToken.create_associated_token_account(owner, owner, WSOL_MINT))
        lam = int(collateral_amount * 1e9)
        pre_ixs.append(transfer(TransferParams(from_pubkey=owner, to_pubkey=funding_account, lamports=lam)))
        pre_ixs.append(sync_native(SyncNativeParams(account=funding_account)))
        post_ixs.append(close_account(owner, owner, funding_account, owner))

    # Build instruction params
    size_delta = int(size_usd * 1e6)
    coll_delta = int(collateral_amount * 1e6)
    SideType = program.type["Side"]
    side_val = SideType.Long() if side.lower() == "long" else SideType.Short()
    params = {"counter": counter, "collateral_token_delta": coll_delta, "jupiter_minimum_out": None,
              "price_slippage": slippage_bps, "side": side_val, "size_usd_delta": size_delta}

    # Send transaction
    try:
        tx_sig = await program.rpc["create_increase_position_market_request"](
            params,
            ctx=Context(
                accounts={
                    "owner": owner,
                    "funding_account": funding_account,
                    "perpetuals": perp_pda,
                    "pool": POOL_ACCOUNT,
                    "position": position_pda,
                    "position_request": pos_req_pda,
                    "position_request_ata": pos_req_ata,
                    "custody": custody,
                    "collateral_custody": collateral_custody,
                    "input_mint": input_mint,
                    "referral": REFERRAL,
                    "token_program": TOKEN_PROGRAM_PUBKEY,
                    "associated_token_program": ASSOCIATED_TOKEN_PROGRAM_PUBKEY,
                    "system_program": SYS_PROGRAM_PUBKEY,
                    "rent": SYSVAR_RENT_PUBKEY,
                    "event_authority": EVENT_AUTHORITY,
                    "program": PROGRAM_ID
                },
                pre_instructions=pre_ixs,
                post_instructions=post_ixs,
            )
        )
        print(f"✅ {side.upper()} {m} order submitted: {tx_sig}")
    except Exception as err:
        print(f"❌ Order failed: {err}")
        await client.close()
        return

    # Confirm and fetch
    await client.confirm_transaction(tx_sig, commitment="confirmed")
    try:
        pos_data = await program.account["Position"].fetch(position_pda)
        print("Position details:", pos_data)
    except:
        print("Position data unavailable; execution pending.")

    await client.close()

if __name__ == "__main__":
    asyncio.run(submit_perp_order("SOL", "long", 50.0, 10.0, 100))
