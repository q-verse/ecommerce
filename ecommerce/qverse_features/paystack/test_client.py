
""" Tests for Paystack Client. """
import json

import requests
import responses
from ddt import data, ddt, unpack
from mock import MagicMock, patch

from ecommerce.extensions.test.paystack_utils import get_error_response, get_transaction_response
from ecommerce.qverse_features.paystack.client import PaystackClient
from ecommerce.qverse_features.paystack.exceptions import (
    InvalidClientArgument,
    InvalidPaystackClientMethod,
    InvalidRequestMethod
)
from ecommerce.tests.testcases import TestCase


@ddt
class PaystackClientTests(TestCase):
    """
    Tests for the Paystack Client.
    """

    TEST_DATA = 'some data'

    def setUp(self):
        super(PaystackClientTests, self).setUp()
        self.base_url = 'http://fake_base_url'
        self.auth_key = 'fake_auth_key'
        self.client = PaystackClient(self.base_url, self.auth_key)

        patcher = patch('ecommerce.qverse_features.paystack.client.logger')
        self.mock_logger = patcher.start()
        self.addCleanup(patcher.stop)

    def create_response(self, json_data, status):
        """
        Returns a mocked response.
        """
        response = MagicMock()
        response.json.return_value = json_data
        response.status_code = status
        return response

    @unpack
    @data(
        {'base_url': None, 'auth_key': None, 'msg': 'Authorization key and Base Url'},
        {'base_url': None, 'auth_key': "fake_key", 'msg': 'Base Url'},
        {'base_url': 'fake_url', 'auth_key': None, 'msg': 'Authorization key'},
    )
    def test_init_error(self, base_url, auth_key, msg):
        """
        Verifies that proper error is raised on missing configurations.
        """
        self.assertRaises(InvalidClientArgument, PaystackClient, base_url, auth_key)
        msg = "Missing {} argument.".format(msg)
        self.mock_logger.error.assert_called_once_with(msg)

    def test_url(self):
        """
        Verifies that function return proper url.
        """
        path = '/fake_path'
        expected_url = self.base_url + path
        actual_url = self.client.get_url(path)
        self.assertEqual(actual_url, expected_url)

    def test_url_for_no_path(self):
        """
        Verifies that function return base url if no path is given.
        """
        expected_url = self.base_url
        actual_url = self.client.get_url(path=None)
        self.assertEqual(actual_url, expected_url)

    def test_headers(self):
        """
        Verifies that function return required headers data.
        """
        actual_headers = self.client.get_headers()
        expected_headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer {}'.format(self.auth_key)
        }
        self.assertDictEqual(actual_headers, expected_headers)

    def test_parse_response_for_error_response(self):
        """
        Verifies that client log error message and return false if it gets error response from Paystack API.
        """
        expected_data = get_error_response()
        expected_status_code = 400
        response = self.create_response(expected_data, expected_status_code)
        actual_result, actual_data = self.client.parse_response(response)
        self.assertDictEqual(actual_data, expected_data)
        self.assertEqual(actual_result, False)
        self.mock_logger.info.assert_called_once_with(
            "\nPaystack status: %s, \n Paystack message:%s.", expected_data.get('status'), expected_data.get('message')
        )
        self.mock_logger.error.assert_called_with(
            "Paystack API return Error response: %s.", json.dumps(expected_data)
        )

    def test_parse_response_for_success_response(self):
        """
        Verifies that client log message and return True if it gets success response from Paystack API.
        """
        expected_data = get_transaction_response('fake_transaction_id')
        expected_status_code = 200
        response = self.create_response(expected_data, expected_status_code)
        actual_result, actual_data = self.client.parse_response(response)
        self.assertDictEqual(actual_data, expected_data)
        self.assertEqual(actual_result, True)
        self.mock_logger.info.assert_called_with(
            "Paystack API returned success response: %s.", json.dumps(expected_data)
        )

    @responses.activate
    def test_parse_response_for_value_error(self):
        """
        Verifies that client log error message and return False it is unable to retrieved JSON response.
        """
        expected_data = 'null'
        responses.add(responses.GET, self.base_url, status=404, json=None)
        response = requests.get(self.base_url)
        actual_result, actual_data = self.client.parse_response(response)
        self.assertEqual(actual_data, None)
        self.assertEqual(actual_result, False)
        self.mock_logger.error.assert_called_with(
            "Paystack API return Error response: %s.", expected_data
        )

    def test_handle_request(self):
        """
        Verifies that client send API request with correct parameters.
        """
        path = '/fake_path'
        expected_headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer {}'.format(self.auth_key)
        }
        expected_data = {'test_data': 'some fake test data'}
        expected_url = self.base_url + path
        request_data = {
            'data': expected_data,
            'method': 'GET',
            'path': path
        }
        response = self.create_response(expected_data, 200)

        with patch('ecommerce.qverse_features.paystack.client.requests.get') as mock_request:
            mock_request.return_value = response
            actual_result, actual_data = self.client.handle_request(request_data)
            self.mock_logger.info.assert_called_with(
                'Paystack API returned success response: %s.', json.dumps(expected_data))
            mock_request.assert_called_once_with(
                url=expected_url, headers=expected_headers, data=json.dumps(expected_data))
            self.assertEqual(actual_data, expected_data)
            self.assertEqual(actual_result, True)

    def test_handle_request_for_invalid_request_method(self):
        """
        Verifies that client raises an exception for invalid request method.
        """
        request_data = {
            'data': 'some fake data',
            'method': 'invalid method',
            'path': 'fake_path'
        }
        self.assertRaises(InvalidRequestMethod, self.client.handle_request, request_data)

    def test_initialize_transaction(self):
        """
        Verifies that client returns required data to send Paystack initialize transcation request.
        """
        expected_return_dict = {
            'method': 'POST',
            'path': '/transaction/initialize',
            'data': self.TEST_DATA
        }
        actual_return_dict = self.client.initialize_transaction(self.TEST_DATA)
        self.assertDictEqual(actual_return_dict, expected_return_dict)

    def test_verify_transaction(self):
        """
        Verifies that client returns required data to send Paystack verify transcation request.
        """
        reference = 'fake_reference'
        expected_return_dict = {
            'method': 'GET',
            'path': '/transaction/verify/{}'.format(reference)
        }
        actual_return_dict = self.client.verify_transaction(reference)
        self.assertDictEqual(actual_return_dict, expected_return_dict)

    def test_create_refund(self):
        """
        Verifies that client returns required data to send Paystack create refund request.
        """
        expected_return_dict = {
            'method': 'POST',
            'data': {
                'transaction': self.TEST_DATA
            },
            'path': '/refund'
        }
        actual_return_dict = self.client.create_refund(self.TEST_DATA)
        self.assertDictEqual(actual_return_dict, expected_return_dict)

    def test_fetch_refund(self):
        """
        Verifies that client returns required data to send Paystack fetch refund request.
        """
        refund_id = 'fake_id'
        expected_return_dict = {
            'method': 'GET',
            'path': '/refund/{}'.format(refund_id)
        }
        actual_return_dict = self.client.fetch_refund(refund_id)
        self.assertDictEqual(actual_return_dict, expected_return_dict)

    @patch('ecommerce.qverse_features.paystack.client.PaystackClient.handle_request')
    def test_handler_for_verify_tarsanction(self, mock_handle_request):
        """
        Verifies that function calls correct client method to handle verify tarnsaction request.
        """
        expected_code = 'VERIFY_TRANSACTION'
        expected_transaction_object = self.client.verify_transaction(self.TEST_DATA)
        self.client.handler(expected_code, self.TEST_DATA)
        mock_handle_request.assert_called_once_with(expected_transaction_object)

    @patch('ecommerce.qverse_features.paystack.client.PaystackClient.handle_request')
    def test_handler_for_initialize_tarsanction(self, mock_handle_request):
        """
        Verifies that function calls correct client method to handle initailize tarnsaction request.
        """
        expected_code = 'INITIALIZE_TRANSACTION'
        expected_transaction_object = self.client.initialize_transaction(self.TEST_DATA)
        self.client.handler(expected_code, self.TEST_DATA)
        mock_handle_request.assert_called_once_with(expected_transaction_object)

    @patch('ecommerce.qverse_features.paystack.client.PaystackClient.handle_request')
    def test_handler_for_fetch_refund(self, mock_handle_request):
        """
        Verifies that function calls correct client method to handle fetch refund request.
        """
        expected_code = 'FETCH_REFUND'
        expected_transaction_object = self.client.fetch_refund(self.TEST_DATA)
        self.client.handler(expected_code, self.TEST_DATA)
        mock_handle_request.assert_called_once_with(expected_transaction_object)

    @patch('ecommerce.qverse_features.paystack.client.PaystackClient.handle_request')
    def test_handler_for_create_refund(self, mock_handle_request):
        """
        Verifies that function calls correct client method to handle create refund request.
        """
        expected_code = 'CREATE_REFUND'
        expected_transaction_object = self.client.create_refund(self.TEST_DATA)
        self.client.handler(expected_code, self.TEST_DATA)
        mock_handle_request.assert_called_once_with(expected_transaction_object)

    def test_handler_for_invalid_code(self):
        """
        Verifies that function raises an exception for invalid code.
        """
        expected_code = 'INVALID_CODE'
        self.assertRaises(InvalidPaystackClientMethod, self.client.handler, expected_code, self.TEST_DATA)
