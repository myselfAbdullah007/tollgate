"""Bounded, process-local metrics; no customer IDs or request content as labels."""


class Metrics:
    bounds = (0.1, 0.5, 1, 5, 15, 30, 60, 120, float("inf"))

    def __init__(self):
        self.buckets = [0] * len(self.bounds)
        self.duration_sum = 0.0
        self.counters = {
            "fallback_attempts": 0,
            "uncertain_requests": 0,
            "uncertain_micro_usd": 0,
            "accounting_recoveries": 0,
            "accounting_failures": 0,
            "cache_write_failures": 0,
        }

    def observe(self, duration):
        self.duration_sum += duration
        for i, bound in enumerate(self.bounds):
            self.buckets[i] += int(duration <= bound)

    def render(self):
        lines = []
        for name, value in self.counters.items():
            lines.extend([f"# TYPE tollgate_{name}_total counter", f"tollgate_{name}_total {value}"])
        name = "tollgate_request_duration_seconds"
        lines.append(f"# TYPE {name} histogram")
        for bound, count in zip(self.bounds, self.buckets):
            label = "+Inf" if bound == float("inf") else str(bound)
            lines.append(f'{name}_bucket{{le="{label}"}} {count}')
        lines.extend([f"{name}_sum {self.duration_sum}", f"{name}_count {self.buckets[-1]}"])
        return "\n".join(lines) + "\n"
