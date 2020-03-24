""" View for interacting with the Paystack payment processor. """

from __future__ import unicode_literals

import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.generic import View
from oscar.apps.partner import strategy
from oscar.core.loading import get_class, get_model

from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.payment.exceptions import InvalidBasketError
from ecommerce.extensions.payment.processors.paystack import Paystack
from ecommerce.qverse_features.paystack.constants import VERIFY_TRANSACTION_CODE

logger = logging.getLogger(__name__)

Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')


class PaystackExecutionView(EdxOrderPlacementMixin, View):
    @property
    def payment_processor(self):
        return Paystack(self.request.site)

    @method_decorator(transaction.non_atomic_requests)
    def dispatch(self, request, *args, **kwargs):
        return super(PaystackExecutionView, self).dispatch(request, *args, **kwargs)

    def get_basket(self, basket_id):
        """
        Returns a basket from basket_id.
        """
        if not basket_id:
            return None

        try:
            basket_id = int(basket_id)
            basket = Basket.objects.get(id=basket_id)
            basket.strategy = strategy.Default()
            Applicator().apply(basket, basket.owner, self.request)
            return basket
        except (ValueError, ObjectDoesNotExist):
            return None

    def call_handle_order_placement(self, basket, request):
        """
        Handles an order placement for approved transactions.
        """
        order_number = basket.order_number

        shipping_method = NoShippingRequired()
        shipping_charge = shipping_method.calculate(basket)
        order_total = OrderTotalCalculator().calculate(basket, shipping_charge)

        user = basket.owner
        order = self.handle_order_placement(
            order_number=order_number,
            user=user,
            basket=basket,
            shipping_address=None,
            shipping_method=shipping_method,
            shipping_charge=shipping_charge,
            billing_address=None,
            order_total=order_total,
            request=request
        )
        self.handle_post_order(order)

    def get(self, request):
        """
        Handles an incoming user returned to us by Paystack after approving payment.
        It redirects user to order receipt page after completing all payment flow
        of a successfull Paystack transaction.
        """
        reference = request.GET.get('reference')
        success, response = self.payment_processor.paystack_client.handler(
            VERIFY_TRANSACTION_CODE, reference
        )

        if success:
            data = response.get('data')
            metadata = data.get('metadata')

            order_number = metadata.get('order_number')
            basket_id = metadata.get('basket_id')
            transaction_id = data.get('id')
            logger.info(
                "Received Paystack payment notification for transaction: %s, associated with basket: %d.",
                transaction_id,
                int(basket_id)
            )

            basket = self.get_basket(basket_id)
            if not basket:
                logger.error("Received Paystack response for non-existent basket: %d.", basket_id)
                raise InvalidBasketError
            if basket.status != Basket.FROZEN:
                logger.info(
                    "Received Paystack response for basket [%d] which is in a non-frozen state, [%s].",
                    basket.id, basket.status
                )

            self.payment_processor.record_processor_response(
                response, transaction_id=reference, basket=basket
            )

            receipt_url = get_receipt_page_url(
                order_number=order_number,
                site_configuration=basket.site.siteconfiguration
            )

            try:
                with transaction.atomic():
                    self.handle_payment(data, basket)
                    self.call_handle_order_placement(basket, request)

            except Exception:  # pylint: disable=broad-except
                logger.exception("Attempts to handle payment for basket [%d] failed.", basket.id)
                self.log_order_placement_exception(order_number, basket.id)
            else:
                return redirect(receipt_url)

        logger.error("Unable to process Paystack transaction with reference: %s.", reference)
        return redirect(self.payment_processor.error_url)
