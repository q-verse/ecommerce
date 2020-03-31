class InvalidClientArgument(Exception):
    """ Raised when authorization key or base_url is missing """
    pass


class InvalidRequestMethod(Exception):
    """
    Invalid or unimplemented HTTP request method
    """
    pass


class InvalidPaystackClientMethod(Exception):
    """
    Invalid or unimplemented Pasystack client method
    """
    pass
