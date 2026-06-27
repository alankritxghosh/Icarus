class CheckoutCache:
    def __init__(self, redis_client):
        self.redis = redis_client

    def get(self, key: str):
        return self.redis.get(key)

