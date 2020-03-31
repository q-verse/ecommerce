def get_initliaze_payment_response(payment_url, token, reference_number):
    return {
        'status': True,
        'message': 'Authorization URL created',
        'data': {
            'authorization_url': payment_url,
            'access_code': token,
            'reference': reference_number
        }
    }


def get_transaction_verify_response(reference_number, tarnsaction_id, basket, invalid_basket=False):
    basket_id = 000000000 if invalid_basket else basket.id
    return {
        'status': True,
        'message': 'Verification successful',
        'data': {
            'id': tarnsaction_id,
            'currency': basket.currency,
            'reference': reference_number,
            'amount': int(basket.total_incl_tax),
            'metadata': {
                'basket_id': basket_id,
                'order_number': basket.order_number
            },
            'authorization': {
                'last4': '1111',
                'card_type': 'TEST'
            }
        }
    }


def get_transaction_response(transaction_id):
    return {
        'id': transaction_id,
        'amount': '100',
        'currency': 'fake_currency',
        'authorization': {
            'last4': '1111',
            'card_type': 'test_type',
        }
    }


def get_error_response():
    return {
        'status': False,
        'message': 'some error message'
    }


def get_refund_create_response(refund_id, transaction_id, reference_number):
    return {
        'status': True,
        'message': "Refund has been queued for processing",
        'data': {
            'transaction': {
                'id': transaction_id,
                'reference': reference_number,
            },
            'status': 'pending',
            'id': refund_id,
        }
    }


def get_refund_fetch_response(refund_status):
    return {
        'data': {
            'status': refund_status
        }
    }
