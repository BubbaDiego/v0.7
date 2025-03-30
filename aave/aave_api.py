# aave_api.py
import requests
import config.config_constants as config


def get_user_data(address):
    """
    Fetches Aave public wallet data for the given user address using TheGraph.
    The address should be provided as either a lower-case or checksummed address.
    """
    address_lower = address.lower()
    query = """
    {
      user(id: "%s") {
        id
        healthFactor
        totalCollateralUSD
        totalDebtUSD
        reserves {
          reserve {
            symbol
          }
          currentATokenBalance
          stableDebt
          variableDebt
        }
      }
    }
    """ % address_lower
    url = "https://api.thegraph.com/subgraphs/name/aave/protocol-v3-polygon"
    response = requests.post(url, json={'query': query})

    if response.status_code == 200:
        data = response.json()
        user_data = data.get("data", {}).get("user")
        if not user_data:
            # Return empty data with health_factor set to 0.0 to avoid template errors.
            return [], {"health_factor": 0.0, "total_supplied": 0, "total_debt": 0}
        # Parse the values from the subgraph.
        # Default health_factor to 0.0 if it's missing or None.
        health_factor = float(user_data["healthFactor"]) if user_data["healthFactor"] is not None else 0.0
        total_supplied = float(user_data["totalCollateralUSD"]) if user_data["totalCollateralUSD"] else 0
        total_debt = float(user_data["totalDebtUSD"]) if user_data["totalDebtUSD"] else 0
        assets = []
        for res in user_data.get("reserves", []):
            symbol = res["reserve"]["symbol"]
            a_token = float(res["currentATokenBalance"]) if res["currentATokenBalance"] else 0
            stable_debt = float(res["stableDebt"]) if res["stableDebt"] else 0
            variable_debt = float(res["variableDebt"]) if res["variableDebt"] else 0
            assets.append({
                "asset": symbol,
                "supplied": a_token,
                "debt": stable_debt + variable_debt
            })
        position = {
            "health_factor": health_factor,
            "total_supplied": total_supplied,
            "total_debt": total_debt
        }
        return assets, position
    else:
        # In case of an error, return empty data with default health_factor.
        return [], {"health_factor": 0.0, "total_supplied": 0, "total_debt": 0}


def supply(asset, amount, user_address, private_key):
    """Placeholder for the supply function."""
    raise NotImplementedError("Supply function is not implemented yet.")
