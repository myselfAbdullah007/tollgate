-- Atomic admission across customer and tenant; rejection consumes no capacity.
local now = tonumber(ARGV[1])
for i, key in ipairs(KEYS) do
 redis.call('ZREMRANGEBYSCORE', key, '-inf', now - 60)
 if redis.call('ZCARD', key) >= tonumber(ARGV[i + 2]) then return 0 end
end
for _, key in ipairs(KEYS) do
 redis.call('ZADD', key, now, ARGV[2])
 redis.call('EXPIRE', key, 61)
end
return 1
