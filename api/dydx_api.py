import requests
import logging


class DydxAPI:
    """
    A simple client for interacting with the dYdX API.
    Provides methods to retrieve subaccounts (or a specific subaccount) and perpetual positions.
    """

    def __init__(self, base_url=None):
        # Use the testnet URL by default; this can be overridden via configuration.
        self.base_url = base_url or "https://indexer.dydx.trade/v4"
        self.headers = {"Accept": "application/json"}
        self.logger = logging.getLogger(__name__)

    def get_subaccounts(self, wallet_address):
        """
        Retrieves subaccounts for the given wallet address.
        Endpoint: GET /addresses/{address}
        """
        try:
            url = f"{self.base_url}/addresses/{wallet_address}"
            self.logger.debug("Requesting subaccounts with URL: %s", url)
            response = requests.get(url, headers=self.headers)
            self.logger.debug("Response status: %s", response.status_code)
            self.logger.debug("Raw response text: %s", response.text)
            response.raise_for_status()
            json_data = response.json()
            self.logger.debug("Parsed subaccounts response: %s", json_data)
            subaccounts = json_data.get("subaccounts", [])
            if not subaccounts:
                self.logger.debug("No subaccounts found in the response.")
            return subaccounts
        except Exception as e:
            self.logger.error("Error fetching subaccounts: %s", e, exc_info=True)
            return []

    def get_subaccount(self, wallet_address, subaccount_number=0):
        """
        Retrieves details for a specific subaccount.
        Endpoint: GET /addresses/{address}/subaccountNumber/{subaccountNumber}
        """
        try:
            url = f"{self.base_url}/addresses/{wallet_address}/subaccountNumber/{subaccount_number}"
            self.logger.debug("Requesting specific subaccount with URL: %s", url)
            response = requests.get(url, headers=self.headers)
            self.logger.debug("Response status: %s", response.status_code)
            self.logger.debug("Raw response text: %s", response.text)
            response.raise_for_status()
            json_data = response.json()
            self.logger.debug("Parsed subaccount response: %s", json_data)
            subaccount = json_data.get("subaccount", {})
            return subaccount
        except Exception as e:
            self.logger.error("Error fetching subaccount: %s", e, exc_info=True)
            return {}

    def get_perpetual_positions(self, wallet_address, subaccount_number):
        """
        Retrieves perpetual positions for the given wallet address and subaccount number.
        Endpoint: GET /perpetualPositions
        """
        try:
            url = f"{self.base_url}/perpetualPositions"
            params = {"address": wallet_address, "subaccountNumber": subaccount_number}
            self.logger.debug("Requesting perpetual positions with URL: %s and params: %s", url, params)
            response = requests.get(url, headers=self.headers, params=params)
            self.logger.debug("Response status: %s", response.status_code)
            self.logger.debug("Raw response text: %s", response.text)
            response.raise_for_status()
            json_data = response.json()
            self.logger.debug("Parsed perpetual positions response: %s", json_data)
            positions = json_data.get("positions", [])
            if not positions:
                self.logger.debug("No perpetual positions found in the response.")
            return positions
        except Exception as e:
            self.logger.error("Error fetching perpetual positions: %s", e, exc_info=True)
            return []
