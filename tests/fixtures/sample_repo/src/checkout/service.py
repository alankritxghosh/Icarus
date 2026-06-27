class CheckoutService:
    def __init__(self, repository, event_bus):
        self.repository = repository
        self.event_bus = event_bus

    def create(self, payload: dict) -> str:
        order_id = self.repository.save(payload)
        self.event_bus.publish("order.created", {"order_id": order_id})
        return order_id

