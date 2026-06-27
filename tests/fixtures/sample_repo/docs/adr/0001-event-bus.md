# ADR 0001: Use an in-process event bus

Status: Accepted

## Context

Checkout previously called notification handlers directly. A notification
failure could therefore fail an otherwise valid order.

## Decision

Use an in-process event bus after the order transaction commits. This keeps
notification failures outside the purchase path while retaining a simple
single-process deployment.

## Consequences

The service gains failure isolation without introducing a network broker.
Events are not durable, so a process crash can lose a notification.

## Rejected alternative

RabbitMQ was rejected for the first release because the team did not want to
operate another production service before notification volume justified it.

