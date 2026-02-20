"""Basic connection example.
"""

import redis

r = redis.Redis(
    host='redis-16059.c212.ap-south-1-1.ec2.cloud.redislabs.com',
    port=16059,
    decode_responses=True,
    username="default",
    password="7k1w5RZ2ohelIlbUREFjd45Ae7rVwuq4",
)

success = r.set('foo', 'bar')
# True

result = r.get('foo')
print(result)
# >>> bar

