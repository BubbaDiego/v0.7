# aave_bp.py
from flask import Blueprint, render_template, request
# from web3 import Web3  # No longer using checksum conversion
import config.config_constants as config
from aave import aave_api

aave_bp = Blueprint("aave", __name__,  template_folder='.')

# Default public wallet address (lower-case version as provided)
DEFAULT_PUBLIC_ADDRESS = "0x2B763E2eDcFC40A03646B073B81A5C889cf1a8fe"


@aave_bp.route("/", methods=["GET", "POST"])
def aave_dashboard():
    # Get the address from query parameters or use the default lower-case address.
    address = request.args.get("address") or DEFAULT_PUBLIC_ADDRESS

    # Optionally, you can add your own basic validation here instead of checksum conversion.
    # For example, you could check if it starts with '0x' and is 42 characters long.
    if not (address.startswith("0x") and len(address) == 42):
        return f"Invalid address format: {address}", 400

    # Fetch public wallet data using our aave_api module (which returns dummy data for now).
    assets, position = aave_api.get_user_data(address)

    # Render the aave.html template with the retrieved data.
    return render_template("aave.html", address=address, assets=assets, position=position)
