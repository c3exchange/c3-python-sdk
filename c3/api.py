from typing import Any

from requests import Session

from c3.utils.constants import MainnetConstants


class ApiClient:
    def __init__(
        self,
        base_url=MainnetConstants.API_URL,
    ) -> None:
        self.base_url = base_url

        self.session = Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
            }
        )

    def get(self, url_path: str, params: Any = None) -> Any:
        url = self.base_url + url_path

        response = self.session.get(
            url,
            params=params,
        )
        response.raise_for_status()

        try:
            return response.json()
        except ValueError:
            return {"error": f"Could not parse JSON: {response.text}"}

    def post(self, url_path: str, payload: Any = {}) -> Any:
        url = self.base_url + url_path

        response = self.session.post(url, json=payload)
        response.raise_for_status()

        try:
            return response.json()
        except ValueError:
            return {"error": f"Could not parse JSON: {response.text}"}