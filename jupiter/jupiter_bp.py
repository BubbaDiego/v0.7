from flask import Blueprint, render_template, request, jsonify, current_app
from positions.position_service import PositionService
from config.config_constants import DB_PATH

jupiter_bp = Blueprint("jupiter_bp", __name__, template_folder="templates")

@jupiter_bp.route("/", methods=["GET"])
def dashboard():
    """
    Renders the Jupiter Dashboard page, displaying current positions data.
    This page will eventually include a section for TP/SL order generation.
    """
    try:
        # Retrieve positions from the PositionService and fill with latest prices.
        positions = PositionService.get_all_positions(DB_PATH)
        positions = PositionService.fill_positions_with_latest_price(positions)
    except Exception as e:
        current_app.logger.error("Error fetching positions for Jupiter Dash: %s", e)
        positions = []
    return render_template("jupiter_dash.html", positions=positions)


def encode_instruction(trigger_price: int, trigger_above: bool, size_usd_delta: int, order_type: str) -> bytes:
    """
    Encodes the instruction data for a TP or SL order.
    For demonstration, we encode as:
      - 2 bytes: order type ("TP" or "SL")
      - 8 bytes: trigger_price (unsigned, little-endian)
      - 1 byte: trigger_above flag (1 if True, 0 if False)
      - 8 bytes: order size in USD delta (unsigned, little-endian)

    In production, use the proper layout from Jupiter's program specification.
    """
    order_type_bytes = order_type.encode("utf-8")  # Should be exactly 2 bytes.
    return order_type_bytes + struct.pack("<QBQ", trigger_price, int(trigger_above), size_usd_delta)


@jupiter_bp.route('/generate_order', methods=['POST'])
def generate_order():
    """
    Endpoint to create TP/SL orders on Jupiter Perps.
    Expects JSON payload with:
      - positionId: The ID of the selected position.
      - symbol: Trading pair (e.g., "SOL-PERP")
      - currentPrice: Current market price (in USD)
      - takeProfit: Target take profit price (in USD)
      - stopLoss: Target stop loss price (in USD)
    """
    try:
        data = request.get_json()
        position_id = data.get('positionId')
        symbol = data.get('symbol')
        current_price = float(data.get('currentPrice'))
        take_profit = float(data.get('takeProfit'))
        stop_loss = float(data.get('stopLoss'))

        # Convert prices to atomic units (assume 6 decimals, adjust if needed)
        current_price_int = int(current_price * 1_000_000)
        tp_price_int = int(take_profit * 1_000_000)
        sl_price_int = int(stop_loss * 1_000_000)

        # For demonstration, assume full position closure: use a dummy USD size.
        # In reality, this should reflect the actual USD value of the position.
        order_size_usd = 100_000_000  # e.g., $100, represented in atomic units

        # Encode the instructions:
        # For a long position, TP triggers when price is equal or above threshold, SL triggers when equal or below.
        tp_data = encode_instruction(tp_price_int, True, order_size_usd, "TP")
        sl_data = encode_instruction(sl_price_int, False, order_size_usd, "SL")

        # Jupiter Perps program ID (update with the correct mainnet program ID)
        JUP_PERP_PROGRAM_ID = PublicKey("PERPHjGBqRHArX4DySjwM6UJHiR3sWAatqfdBS2qQJu")

        # --- Build the required account metas ---
        # NOTE: In an actual integration, you must supply the full list of accounts required by the instruction.
        # Here we use dummy accounts for illustration.
        dummy_account = PublicKey("11111111111111111111111111111111")
        account_metas = [
            AccountMeta(pubkey=dummy_account, is_signer=False, is_writable=False),
            # Add additional AccountMeta objects as required by the Jupiter Perps program.
        ]

        # Create TransactionInstructions for TP and SL orders.
        tp_instruction = TransactionInstruction(
            keys=account_metas,
            program_id=JUP_PERP_PROGRAM_ID,
            data=tp_data
        )

        sl_instruction = TransactionInstruction(
            keys=account_metas,
            program_id=JUP_PERP_PROGRAM_ID,
            data=sl_data
        )

        # Build the transaction and add both instructions.
        transaction = Transaction()
        transaction.add(tp_instruction)
        transaction.add(sl_instruction)

        # Load the trader's private key from environment variable.
        private_key_str = os.environ.get("JUPITER_PRIVATE_KEY")
        if not private_key_str:
            raise Exception("JUPITER_PRIVATE_KEY is not set in the environment!")
        # Assuming the private key is stored as a hex string.
        trader = Keypair.from_secret_key(bytes.fromhex(private_key_str))

        # Use a Solana RPC endpoint; you can set this via an environment variable.
        rpc_url = os.environ.get("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
        client = Client(rpc_url)

        # Send the transaction.
        result = client.send_transaction(transaction, trader)
        return jsonify({
            "message": f"TP/SL order generated successfully for position {position_id}",
            "result": result
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

