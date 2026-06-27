from checkout.service import CheckoutService


def create_order(service: CheckoutService, payload: dict) -> str:
    return service.create(payload)

