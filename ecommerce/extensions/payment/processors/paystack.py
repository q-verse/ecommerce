""" Paystack payment processor. """
from __future__ import absolute_import, unicode_literals

import logging

from django.urls import reverse
from django.utils.functional import cached_property
from oscar.apps.payment.exceptions import GatewayError

from ecommerce.core.url_utils import get_ecommerce_url
from ecommerce.extensions.payment.exceptions import RefundError
from ecommerce.extensions.payment.processors import BaseClientSidePaymentProcessor, HandledProcessorResponse
from ecommerce.qverse_features.paystack.client import PaystackClient
from ecommerce.qverse_features.paystack.constants import (
    CREATE_REFUND_CODE,
    FETCH_REFUND_CODE,
    INITIALIZE_TRANSACTION_CODE
)

logger = logging.getLogger(__name__)


class Paystack(BaseClientSidePaymentProcessor):
    NAME = 'paystack'

    def __init__(self, site):
        """
        Constructs a new instance of the Paystack processor.

        Raises:
            KeyError: If no settings are configured for this payment processor.
        """
        super(Paystack, self).__init__(site)
        self.public_key = self.configuration['public_key']
        self.secret_key = self.configuration['secret_key']

    @cached_property
    def paystack_client(self):
        """
        Returns a paystack client instance with appropriate configuration.
        """
        return PaystackClient(self.configuration['base_url'], self.secret_key)

    @property
    def cancel_url(self):
        return get_ecommerce_url(self.configuration['cancel_checkout_path'])

    @property
    def error_url(self):
        return get_ecommerce_url(self.configuration['error_path'])

    @property
    def return_url(self):
        redirect_url = reverse('paystack:execute')
        ecommerce_base_url = get_ecommerce_url()
        return "{}{}".format(ecommerce_base_url, redirect_url)

    def get_basket_amount(self, basket):
        """
        Multiplies the price of course with 100 to get the right amount for a transaction.
        """
        # According to Paystack documentation "The amount passed is in Kobo (A positive integer in the
        # smallest currency unit), so you'd have to multiply the Naira amount by 100 to get the Kobo value.
        # Eg NGN 100 should be passed as 10000."
        return str((basket.total_incl_tax * 100).to_integral_value())

    def get_paystack_custom_fields_data(self, basket):
        """
        Returns Paystack Custom fields.
        """
        product = basket.all_lines()[0].product
        return [
            {
                'display_name': 'Order Number',
                'variable_name': 'order_number',
                'value': basket.order_number
            },
            {
                'display_name': 'Course Id',
                'variable_name': 'course_id',
                'value': product.course_id
            },
            {
                'display_name': 'Course Name',
                'variable_name': 'course_title',
                'value': product.course.name
            }
        ]

    def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=True, **kwargs):
        """
        Creates Payment form URL from paystack.

        Arguments:
            basket (Basket): The basket of products being purchased.
            request (Request, optional): A Request object which is used to construct Paystack's `return_url`.
            use_client_side_checkout (bool, optional): This value is not used.
            **kwargs: Additional parameters; not used by this method.

        Returns:
            dict: paystack-specific parameters required to complete a transaction. Must contain a URL
                of payment form to which users can be directed in order to approve a newly created payment.

        Raises:
            GatewayError: Indicates a general error or unexpected behavior on the part of PayPal which prevented
            a payment from being created.
        """
        data = {
            'amount': self.get_basket_amount(basket),
            'email': basket.owner.email,
            'callback_url': self.return_url,
            'metadata': {
                'cancel_action:': self.cancel_url,
                'order_number': basket.order_number,
                'basket_id': basket.id,
                'custom_fields': self.get_paystack_custom_fields_data(basket)
            },
        }

        success, response = self.paystack_client.handler(INITIALIZE_TRANSACTION_CODE, data)

        if success:
            logger.info("Successfully got hosted Paystack payment page for basket: %d.", basket.id)
            data = response.get('data')
            if data:
                return {'payment_page_url': data.get('authorization_url')}

        logger.error("Failed to get Paystack payment form for basket: %d.", basket.id)
        raise GatewayError("Paystack payment creation failure: unable to get Paystack form token.")

    def handle_processor_response(self, response, basket=None):
        """
        Executes an approved Paystack transaction. This method will record payment processor
        response for future usage.

        Arguments:
            response: Transaction response received from Paystack after successfull payment.
            basket (Basket): Basket being purchased via the payment processor.

        Returns:
            HandledProcessorResponse
        """
        authorization = response.get('authorization')
        transaction_id = response.get('id')

        self.record_processor_response(authorization, transaction_id=transaction_id, basket=basket)
        logger.info("Successfully executed Paystack payment [%s] for basket: %d.", transaction_id, basket.id)

        currency = response.get('currency')
        total = basket.total_incl_tax

        return HandledProcessorResponse(
            transaction_id=transaction_id,
            total=total,
            currency=currency,
            card_number=authorization.get('last4'),
            card_type=authorization.get('card_type')
        )

    def get_refund_status(self, refund_id):
        """
        Returns a boolean value indicating refund object status after verification from Paystack.
        """
        success, response = self.paystack_client.handler(FETCH_REFUND_CODE, refund_id)
        if success:
            data = response.get('data')
            refund_status = data.get('status')
            logger.info("Paystack refund has been fetched with status: %s.", refund_status)

            if refund_status == 'processed':
                return True

        logger.error("Unable to fetch refund object from paystack for refund_id: %s.", refund_id)

    def issue_credit(self, order_number, basket, reference_number, amount, currency):
        """
        Executes Paystack refund flow. First we need to create refund object at paystack then need to verify
        it's status to complete all process.

        Raises:
            RefundError: indicating general refund error.
        """
        try:
            success, response = self.paystack_client.handler(CREATE_REFUND_CODE, reference_number)

            if success:
                data = response.get('data')
                refund_id = data.get('id')
                if data:
                    logger.info(
                        "Successfully created  Paystack refund request for transaction: %s, and got refund_id: %s.",
                        reference_number,
                        refund_id
                    )
                is_verified_refund = self.get_refund_status(refund_id)
                if is_verified_refund:
                    self.record_processor_response(response, transaction_id=refund_id, basket=basket)
                    return reference_number

            elif response.get('message') == "Transaction has been fully reversed":
                # there is no way that we can extract refund_id for already processed transaction
                # so we have to return reference_number instead of refund_id to update records
                return reference_number
        except Exception:  # pylint: disable=broad-except
            logger.exception("Unable to create a Paystack refund request.")

        msg = "An error occurred while attempting Paystack issue a credit for order:{}.".format(order_number)
        raise RefundError(msg)
