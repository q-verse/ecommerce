""" Tests of the Paystack Payment Views. """
import responses
from django.urls import reverse
from mock import MagicMock, patch
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.processors.paystack import Paystack
from ecommerce.extensions.payment.tests.mixins import PaymentEventsMixin
from ecommerce.extensions.payment.views.paystack import PaystackExecutionView
from ecommerce.extensions.test.paystack_utils import get_error_response, get_transaction_verify_response
from ecommerce.tests.testcases import TestCase

Order = get_model('order', 'Order')
PaymentEvent = get_model('order', 'PaymentEvent')
Source = get_model('payment', 'Source')
Product = get_model('catalogue', 'Product')


class PaystackExecutionViewTests(PaymentEventsMixin, TestCase):
    """
    Test handling of users redirected by Paystack after approving payment.
    """
    path = reverse('paystack:execute')

    def setUp(self):
        super(PaystackExecutionViewTests, self).setUp()
        self.user = self.create_user()
        self.course = CourseFactory(partner=self.partner)
        self.view = PaystackExecutionView()
        self.view.request = MagicMock()
        self.view.request.site = self.site
        self.processor = Paystack(self.site)
        self.reference_number = 'abcdedgh'
        self.tarnsaction_id = '1111111111'

    def create_basket_with_product(self):
        """
        creates a basket for testing.
        """
        product = self.course.create_or_update_seat('verified', True, 100)
        basket = factories.BasketFactory(owner=self.user, site=self.site)
        basket.add_product(product, 1)
        basket.freeze()
        return basket

    def assert_order_created(self, basket, card_type, label):
        """
        Verify order placement and payment event.
        """
        order = Order.objects.get(number=basket.order_number, total_incl_tax=basket.total_incl_tax)
        total = order.total_incl_tax
        order.payment_events.get(event_type__code='paid', amount=total)
        Source.objects.get(
            source_type__name=self.processor.NAME,
            currency=order.currency,
            amount_allocated=total,
            amount_debited=total,
            card_type=card_type,
            label=label
        )
        PaymentEvent.objects.get(
            event_type__name=PaymentEventTypeName.PAID,
            amount=total,
            processor_name=self.processor.NAME
        )

    def test_get_basket(self):
        """
        Verifies that basket has been retrieved properly.
        """
        expected_basket = self.create_basket_with_product()
        actual_basket = self.view.get_basket(expected_basket.id)
        self.assertEqual(actual_basket, expected_basket)

    def test_get_basket_for_invalid_id(self):
        """
        Verifies that function return None if there is no basket
        """
        expected_basket = None
        actual_basket = self.view.get_basket("invalid_basket_id")
        self.assertEqual(actual_basket, expected_basket)

    def test_call_handle_order_placement(self):
        """
        Verifies that processor is placing order properly.
        """
        basket = self.create_basket_with_product()
        self.view.call_handle_order_placement(basket, self.client)
        Order.objects.get(number=basket.order_number, total_incl_tax=basket.total_incl_tax)

    @responses.activate
    def test_payment_execution(self):
        """
        Verifies that a user who has approved payment is redirected to the configured receipt page after
        a successful payment execution.
        """
        basket = self.create_basket_with_product()
        base_url = self.processor.configuration['base_url']
        verify_tarnsaction_url = '{}/transaction/verify/{}'.format(base_url, self.reference_number)

        expected_response_data = get_transaction_verify_response(self.reference_number, self.tarnsaction_id, basket)
        responses.add(responses.GET, verify_tarnsaction_url, json=expected_response_data, status=200)
        authorization = expected_response_data.get('data').get('authorization')

        expected_receipt_url = get_receipt_page_url(
            order_number=basket.order_number,
            site_configuration=basket.site.siteconfiguration
        )

        with patch('ecommerce.extensions.payment.views.paystack.logger') as mock_logger:
            response = self.client.get('{}?reference={}'.format(self.path, self.reference_number))
            mock_logger.info.assert_called_once_with(
                "Received Paystack payment notification for transaction: %s, associated with basket: %d.",
                self.tarnsaction_id,
                basket.id
            )
            self.assert_processor_response_recorded(
                self.processor.NAME,
                self.reference_number,
                expected_response_data,
                basket=basket
            )
            self.assert_order_created(basket, authorization.get('card_type'), authorization.get('last4'))
            self.assertRedirects(
                response, expected_receipt_url, fetch_redirect_response=False)

    @responses.activate
    def test_payment_execution_for_fetch_transaction_failure(self):
        """
        Verifies that order placement fails if the processor is unable to verify transaction from Paystack.
        """
        reference_number = 'invalid_reference_number'
        basket = self.create_basket_with_product()
        base_url = self.processor.configuration['base_url']
        verify_tarnsaction_url = '{}/transaction/verify/{}'.format(base_url, reference_number)
        responses.add(responses.GET, verify_tarnsaction_url, json=get_error_response(), status=400)

        with patch('ecommerce.extensions.payment.views.paystack.logger') as mock_logger:
            response = self.client.get('{}?reference={}'.format(self.path, reference_number))
            mock_logger.error.assert_called_once_with(
                "Unable to process Paystack transaction with reference: %s.", reference_number
            )
            self.assertFalse(
                Order.objects.filter(number=basket.order_number, total_incl_tax=basket.total_incl_tax).exists())
            self.assertRedirects(
                response, self.processor.error_url, fetch_redirect_response=False)

    @responses.activate
    def test_payment_execution_for_invalid_basket_error(self):
        """
        Verifies that order placement fails if the processor receives invalid basket id in Paystack response.
        """
        basket = self.create_basket_with_product()
        base_url = self.processor.configuration['base_url']
        verify_tarnsaction_url = '{}/transaction/verify/{}'.format(base_url, self.reference_number)
        expected_response_data = get_transaction_verify_response(
            self.reference_number, self.tarnsaction_id, basket, True)
        expected_basket_id = expected_response_data.get('data').get('metadata').get('basket_id')
        responses.add(responses.GET, verify_tarnsaction_url, json=expected_response_data, status=200)
        with patch('ecommerce.extensions.payment.views.paystack.logger') as mock_logger:
            get_url = '{}?reference={}'.format(self.path, self.reference_number)
            self.assertRaises(Exception, self.client.get, get_url)
            mock_logger.error.assert_called_once_with(
                "Received Paystack response for non-existent basket: %d.", expected_basket_id
            )

    @responses.activate
    @patch('ecommerce.extensions.payment.processors.paystack.Paystack.handle_processor_response')
    def test_payment_execution_for_exception(self, mocked_handle_processor_response):
        """
        Verifies that order placement fails gracefully if it gets any exception during payment execution.
        """
        mocked_handle_processor_response.side_effect = Exception()
        basket = self.create_basket_with_product()
        base_url = self.processor.configuration['base_url']
        verify_tarnsaction_url = '{}/transaction/verify/{}'.format(base_url, self.reference_number)

        expected_response_data = get_transaction_verify_response(self.reference_number, self.tarnsaction_id, basket)
        responses.add(responses.GET, verify_tarnsaction_url, json=expected_response_data, status=200)

        with patch('ecommerce.extensions.payment.views.paystack.logger') as mock_logger:
            response = self.client.get('{}?reference={}'.format(self.path, self.reference_number))
            mock_logger.error.assert_called_once_with(
                "Unable to process Paystack transaction with reference: %s.", self.reference_number
            )
            self.assertRedirects(
                response, self.processor.error_url, fetch_redirect_response=False)
