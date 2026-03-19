from django.conf import settings
import requests
from requests import RequestException

class Paystack:
    PAYSTACK_SK = settings.PAYSTACK_SECRET_KEY
    base_url = "https://api.paystack.co/"

    def verify_payment(self, ref, *args, **kwargs):
        path = f'transaction/verify/{ref}'
        headers = {
            "Authorization": f"Bearer {self.PAYSTACK_SK}",
            "Content-Type": "application/json",
        }
        url = self.base_url + path
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response_data = response.json()
        except (RequestException, ValueError):
            return False, "Unable to verify payment right now."

        if response.status_code == 200 and response_data.get('status'):
            return True, response_data.get('data', {})

        return False, response_data.get('message', "Unable to verify payment.")
