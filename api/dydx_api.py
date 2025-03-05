import requests
import logging

class DydxAPI:
    """
    A simple client for interacting with the dYdX API.
    Provides methods to retrieve subaccounts and perpetual positions.
    """
    def __init__(self, base_url=None):
        # Use testnet URL by default; can be overridden via configuration.
        self.base_url = base_url or "https://dydx-testnet.imperator.co/v4"
        self.headers = {
            "Accept": "application/json"
        }
        self.logger = logging.getLogger(__name__)
    
    def get_subaccounts(self, wallet_address):
        """
        Retrieves subaccounts for the given wallet address.
        Endpoint: GET /addresses/{address}
        
        Parameters:
            wallet_address (str): The wallet address on dYdX Chain.
        
        Returns:
            list: A list of subaccount dictionaries, or an empty list if an error occurs.
        """
        try:
            url = f"{self.base_url}/addresses/{wallet_address}"
            self.logger.debug("Requesting subaccounts with URL: %s", url)
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            subaccounts = data.get("subaccounts", [])
            return subaccounts
        except Exception as e:
            self.logger.error("Error fetching subaccounts: %s", e, exc_info=True)
            return []
    
    def get_perpetual_positions(self, wallet_address, subaccount_number):
        """
        Retrieves perpetual positions for the given wallet address and subaccount number.
        Endpoint: GET /perpetualPositions
        
        Parameters:
            wallet_address (str): The wallet address on dYdX Chain.
            subaccount_number (int or float): The subaccount number.
        
        Returns:
            list: A list of perpetual position dictionaries, or an empty list if an error occurs.
        """
        try:
            url = f"{self.base_url}/perpetualPositions"
            params = {
                "address": wallet_address,
                "subaccountNumber": subaccount_number
            }
            self.logger.debug("Requesting perpetual positions with URL: %s and params: %s", url, params)
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            positions = data.get("positions", [])
            return positions
        except Exception as e:
            self.logger.error("Error fetching perpetual positions: %s", e, exc_info=True)
            return []
