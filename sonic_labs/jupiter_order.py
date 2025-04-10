import json
import asyncio
from anchorpy import Provider, Program, Wallet, Context
from solana.rpc.async_api import AsyncClient
from solana.keypair import Keypair
from solana.publickey import PublicKey


async def main():
    # Load your wallet keypair from the Windows folder
    with open(r"C:\v0.7\sonic_labs\solana_keypair.json", "r") as f:
        secret = json.load(f)
    wallet = Wallet(Keypair.from_secret_key(bytes(secret)))

    # Connect to Solana mainnet using the official RPC endpoint
    connection = AsyncClient("https://api.mainnet-beta.solana.com")
    provider = Provider(connection, wallet)

    # Load the Jupiter Perps IDL from the file in the Windows folder
    with open(r"C:\v0.7\sonic_labs\jupiter_perps.json", "r") as f:
        idl = json.load(f)

    # Set the unofficial Jupiter Perps program ID
    program_id = PublicKey("PERPHjGBqRHArX4DySjwM6UJHiR3sWAatqfdBS2qQJu")

    # Create the program instance using AnchorPy
    program = Program(idl, program_id, provider)

    # Prepare the parameters for a new position request
    side = 0  # 0 for long; 1 for short
    size_usd_delta = 100  # Position size in USD (example)
    collateral_token_delta = 10  # Collateral amount (example, such as USDC)
    price_slippage = 1  # Acceptable slippage (example)
    jupiter_minimum_out = 0  # Optional; can be 0 if not specified

    # Prepare the required accounts with placeholder values.
    # Replace these placeholders with the actual public keys from community or documentation.
    accounts = {
        "owner": wallet.public_key,
        "pool": PublicKey("5BUwFW4nRbftYTDMbgxykoFWqWHPzahFSNAaaaJtVKsq"),  # Jupiter Liquidity Pool Account
        "custody": PublicKey("7xS2gz2bTp3fwCC7knJvUWTEU9Tycczu6VhJYKgi1wdz"),  # SOL custody account
        "collateralCustody": PublicKey("G18jKKXQwBbrHeiK3C9MRXhkHsLHf7XgCSisykV46EZa"),  # USDC collateral custody
        "fundingAccount": PublicKey("<USER_COLLATERAL_ACCOUNT>"),  # Your associated token account for USDC
        "inputMint": PublicKey("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"),  # USDC Mint on Mainnet
        "perpetuals": PublicKey("<PERPETUALS_PDA>")  # Global PDA for Jupiter Perps (derive via seed if needed)
    }

    try:
        tx = await program.rpc["create_increase_position_market_request"](
            side,
            size_usd_delta,
            collateral_token_delta,
            price_slippage,
            jupiter_minimum_out,
            ctx=Context(accounts=accounts, signers=[])
        )
        print("Transaction successful! Signature:", tx)
    except Exception as e:
        print("Error creating position request:", e)

    await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
