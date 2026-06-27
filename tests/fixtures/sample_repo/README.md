# Checkout Service

The checkout service accepts purchase requests and persists orders.

Requests enter through `checkout.api`, which delegates order creation to
`checkout.service`. Notifications are published through an in-process event
bus after an order is committed.

Architecture decisions are recorded under `docs/adr`.

