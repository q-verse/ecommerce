import json
import logging

import requests

from ecommerce.qverse_features.paystack import constants as paystack_const
from ecommerce.qverse_features.paystack.exceptions import (
    InvalidClientArgument,
    InvalidPaystackClientMethod,
    InvalidRequestMethod,
)

logger = logging.getLogger(__name__)


class PaystackClient(object):
    """
    Client for Paystack API requests.
    """
    _POST_METHOD = 'POST'
    _GET_METHOD = 'GET'
    _CONTENT_TYPE = 'application/json'

    def __init__(self, base_url, authorization_key=None):
        """
        Constructs a new instance of the Paystack client.

        Raises:
            InvalidClientArgument: If required Auth key or Base url are missing.
        """
        if base_url and authorization_key:
            self._BASE_END_POINT = base_url
            self._AUTHORIZATION_KEY = authorization_key
        else:
            if not authorization_key and not base_url:
                msg = "Authorization key and Base Url"
            else:
                msg = "Authorization key" if not authorization_key else "Base Url"
            raise InvalidClientArgument("Missing {} argument.".format(msg))

    def _url(self, path):
        """
        Creates a request URL by appending path with base end point.
        """
        url = self._BASE_END_POINT
        if path:
            url += path
        return url

    def _headers(self):
        """
        Returns Request Header required to send Paystack API.
        """
        return {
            "Content-Type": self._CONTENT_TYPE,
            "Authorization": "Bearer " + self._AUTHORIZATION_KEY
        }

    def _parse_response(self, response):
        """
        Parses and return the response.
        """
        try:
            data = response.json()
            logger.info(
                "\nPaystack status: %s, \n Paystack message:%s.", data.get('status'), data.get('message')
            )
        except ValueError:
            data = None

        if response.status_code in [200, 201]:
            logger.info("Paystack API returned success response: %s.", data)
            return True, data

        else:
            logger.error("Paystack API return response with status code: %s.", response.status_code)
            logger.error("Paystack API return Error response: %s.", json.dumps(data))
            return False, data

    def _handle_request(self, request_data):
        """
        Handles all Paystack API calls.
        """
        method = request_data.get('method')
        path = request_data.get('path')
        data = request_data.get('data')

        method_map = {
            self._GET_METHOD: requests.get,
            self._POST_METHOD: requests.post,
        }
        request = method_map.get(method)
        payload = json.dumps(data) if data else data
        url = self._url(path)

        if not request:
            raise InvalidRequestMethod("Request method not recognised or implemented.")

        logger.info("Sending paystack %s request on URL: %s.", method, url)
        response = request(url=url, headers=self._headers(), data=payload)
        return self._parse_response(response)

    def _initialize_transaction(self, data):
        """
        Returns request data required for Paystack initialize transaction API request.
        Visit https://developers.paystack.co/reference#paystack-standard-xd for API reference.
        """
        return {
            'method': self._POST_METHOD,
            'path': '/transaction/initialize',
            'data': data
        }

    def _verify_transaction(self, reference):
        """
        Returns request data required for Paystack verify transaction API request.
        Visit https://developers.paystack.co/reference#verify-transaction for API reference.
        """
        return {
            'method': self._GET_METHOD,
            'path': '/transaction/verify/{}'.format(reference),
        }

    def _create_refund(self, transaction_id):
        """
        Returns request data required for Paystack create refund API request.
        Visit https://developers.paystack.co/reference#create-refund for API reference.
        """
        return {
            'data': {
                'transaction': transaction_id
            },
            'method': self._POST_METHOD,
            'path': '/refund'
        }

    def _fetch_refund(self, refund_id):
        """
        Returns request data required for Paystack fetch refund API request.
        Visit https://developers.paystack.co/reference#fetch-refund for API reference.
        """
        return {
            'method': self._GET_METHOD,
            'path': '/refund/{}'.format(refund_id)
        }

    def handler(self, code, data):
        """
        Calls relevant client method to send Paystack requests.
        """
        method_map = {
            paystack_const.VERIFY_TRANSACTION_CODE: self._verify_transaction,
            paystack_const.INITIALIZE_TRANSACTION_CODE: self._initialize_transaction,
            paystack_const.CREATE_REFUND_CODE: self._create_refund,
            paystack_const.FETCH_REFUND_CODE: self._fetch_refund
        }
        transaction_handler = method_map.get(code)

        if not transaction_handler:
            raise InvalidPaystackClientMethod("Invalid Code: Unable to map it with paystack client method.")

        transaction_object = transaction_handler(data)
        return self._handle_request(transaction_object)
