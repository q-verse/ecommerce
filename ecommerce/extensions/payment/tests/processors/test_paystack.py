""" Unit tests of Paystack payment processor implementation. """
import responses
from mock import patch
from oscar.apps.payment.exceptions import GatewayError

from ecommerce.extensions.payment.exceptions import RefundError
from ecommerce.extensions.payment.processors.paystack import Paystack
from ecommerce.extensions.payment.tests.processors.mixins import PaymentProcessorTestCaseMixin
from ecommerce.extensions.test.paystack_utils import (
    get_error_response,
    get_initliaze_payment_response,
    get_refund_create_response,
    get_refund_fetch_response,
    get_transaction_response
)
from ecommerce.tests.testcases import TestCase


class PaystackTests(PaymentProcessorTestCaseMixin, TestCase):
    """
    Tests for the Paystack payment processor.
    """
    processor_class = Paystack
    processor_name = 'paystack'

    def setUp(self):
        super(PaystackTests, self).setUp()
        self.base_url = self.processor.configuration['base_url']
        self.reference_number = 'abcdefghi'
        self.transaction_id = '111111111111'
        self.refund_id = '22222222222'

    @responses.activate
    def test_get_transaction_parameters(self):
        """
        Verifies that the processor return appropriate payment url.
        """
        token = 'fake_token'
        expected_payment_url = '{}/{}'.format(self.base_url, token)

        response_data = get_initliaze_payment_response(expected_payment_url, token, self.reference_number)
        url = '{}/transaction/initialize'.format(self.base_url)
        responses.add(responses.POST, url, json=response_data, status=200)

        with patch('ecommerce.extensions.payment.processors.paystack.logger') as mock_logger:
            actual_payment_url = self.processor.get_transaction_parameters(self.basket).get('payment_page_url')
            mock_logger.info.assert_called_once_with(
                "Successfully got hosted Paystack payment page for basket: %d.", self.basket.id)
            self.assertEqual(actual_payment_url, expected_payment_url)

    @responses.activate
    def test_get_transaction_parameters_error(self):
        """
        Verifies that the processor raise GatewayError if it is unable to get payment URL from Paystack.
        """
        response_data = get_error_response()
        url = '{}/transaction/initialize'.format(self.base_url)
        responses.add(responses.POST, url, json=response_data, status=400)

        with patch('ecommerce.extensions.payment.processors.paystack.logger') as mock_logger:
            self.assertRaises(GatewayError, self.processor.get_transaction_parameters, self.basket)
            mock_logger.error.assert_called_once_with(
                "Failed to get Paystack payment form for basket: %d.", self.basket.id)

    def test_handle_processor_response(self):
        """
        Verifies that the processor create proper payment event.
        """
        transaction_response = get_transaction_response(self.transaction_id)
        expected_authorization_data = transaction_response.get('authorization')
        actual_handled_response = self.processor.handle_processor_response(transaction_response, basket=self.basket)

        self.assertEqual(actual_handled_response.currency, transaction_response.get('currency'))
        self.assertEqual(actual_handled_response.total, float(transaction_response.get('amount')))
        self.assertEqual(actual_handled_response.transaction_id, self.transaction_id)
        self.assertEqual(actual_handled_response.card_type, expected_authorization_data.get('card_type'))
        self.assertEqual(actual_handled_response.card_number, expected_authorization_data.get('last4'))

        self.assert_processor_response_recorded(
            self.processor_name, self.transaction_id, expected_authorization_data, basket=self.basket)

    @responses.activate
    def test_get_refund_status(self):
        """
        Verifies that the processor return `True` and log proper info message for refund that has been
        fully processed by Paystack.
        """
        expected_refund_status = 'processed'
        response_data = get_refund_fetch_response(expected_refund_status)
        url = '{}/refund/{}'.format(self.base_url, self.refund_id)
        responses.add(responses.GET, url, json=response_data, status=200)

        with patch('ecommerce.extensions.payment.processors.paystack.logger') as mock_logger:
            actual_status = self.processor.get_refund_status(self.refund_id)
            mock_logger.info.assert_called_with(
                "Paystack refund has been fetched with status: %s.", expected_refund_status
            )
            self.assertTrue(actual_status)

    @responses.activate
    def test_get_refund_status_error(self):
        """
        Verifies that the processor return `None` and log proper error message on refund fetch error response.
        """
        url = '{}/refund/{}'.format(self.base_url, self.refund_id)
        responses.add(responses.GET, url, json=get_error_response(), status=400)

        with patch('ecommerce.extensions.payment.processors.paystack.logger') as mock_logger:
            self.processor.get_refund_status(self.refund_id)
            mock_logger.error.assert_called_once_with(
                "Unable to fetch refund object from paystack for refund_id: %s.", self.refund_id
            )

    @responses.activate
    def test_get_refund_status_for_unprocessed_status(self):
        """
        Verifies that the processor return `None` and log proper error message for getting response
        of unprocessed refund (containing status other than processed).
        """
        expected_refund_status = 'pending'
        response_data = get_refund_fetch_response(expected_refund_status)
        url = '{}/refund/{}'.format(self.base_url, self.refund_id)
        responses.add(responses.GET, url, json=response_data, status=200)

        with patch('ecommerce.extensions.payment.processors.paystack.logger') as mock_logger:
            self.processor.get_refund_status(self.refund_id)
            mock_logger.error.assert_called_once_with(
                "Unable to fetch refund object from paystack for refund_id: %s.", self.refund_id
            )

    @responses.activate
    def test_issue_credit(self):
        """
        Verifies that the processor return reference_number on successfull refund flow.
        """
        expected_id = self.reference_number
        expected_refund_status = 'processed'

        response_data = get_refund_create_response(self.refund_id, self.transaction_id, self.reference_number)
        url = "{}/refund".format(self.base_url)
        responses.add(responses.POST, url, json=response_data, status=200)

        response_data = get_refund_fetch_response(expected_refund_status)
        url = '{}/refund/{}'.format(self.base_url, self.refund_id)
        responses.add(responses.GET, url, json=response_data, status=200)

        with patch('ecommerce.extensions.payment.processors.paystack.logger') as mock_logger:
            actual_id = self.processor.issue_credit(
                self.basket.order_number, self.basket, self.reference_number,
                self.basket.total_incl_tax, self.basket.currency
            )

            mock_logger.info.assert_called_with(
                "Paystack refund has been fetched with status: %s.", expected_refund_status
            )

            self.assertEqual(actual_id, expected_id)

    @responses.activate
    def test_issue_credit_error(self):
        """
        Verifies that the processor raises a  RefundError on refund flow failure.
        """
        url = '{}/refund'.format(self.base_url)
        responses.add(responses.POST, url, json=get_error_response(), status=400)

        self.assertRaises(
            RefundError, self.processor.issue_credit, self.basket.order_number, self.basket,
            self.reference_number, self.basket.total_incl_tax, self.basket.currency
        )
