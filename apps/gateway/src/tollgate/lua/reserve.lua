if redis.call('EXISTS', 'tollgate:reconcile-lock') == 1 then return {-2, 0, 0} end
-- KEYS: settled spend, reservation costs, reservation deadlines
-- ARGV: now, id, budget, thresholds, estimates, allow_degrade, policy, overage_cap
local expired = redis.call('ZRANGEBYSCORE', KEYS[3], '-inf', ARGV[1])
for _, id in ipairs(expired) do redis.call('HDEL', KEYS[2], id) end
redis.call('ZREMRANGEBYSCORE', KEYS[3], '-inf', ARGV[1])
local used = tonumber(redis.call('GET', KEYS[1]) or '0')
for _, value in ipairs(redis.call('HVALS', KEYS[2])) do used = used + tonumber(value) end
local budget = tonumber(ARGV[3])
local tier = 0
if ARGV[6] == 'true' then
  for _, step in ipairs(cjson.decode(ARGV[4])) do
    if budget == 0 or used >= budget * step.at then tier = math.max(tier, step.tier) end
  end
end
local estimates = cjson.decode(ARGV[5])
tier = math.min(tier, #estimates - 1)
local estimate = estimates[tier + 1]
local cap = budget
if ARGV[7] == 'allow_overage' then cap = cap + tonumber(ARGV[8]) end
if used + estimate > cap then return {-1, used, 0} end
redis.call('HSET', KEYS[2], ARGV[2], estimate)
redis.call('ZADD', KEYS[3], tonumber(ARGV[1]) + 180, ARGV[2])
redis.call('EXPIRE', KEYS[2], 600)
redis.call('EXPIRE', KEYS[3], 600)
return {tier, used, estimate}
