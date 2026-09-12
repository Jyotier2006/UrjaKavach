"""R1/R6: largest-triangle-three-buckets preserves visual extrema in bounded views."""
import math


def lttb(rows: list[dict], maximum: int, key: str) -> list[dict]:
    if maximum < 3:
        raise ValueError('max_points must be at least 3')
    if len(rows) <= maximum:
        return rows
    def y(i):
        value = rows[i].get(key, 0)
        return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else 0
    size = (len(rows) - 2) / (maximum - 2)
    result, a = [rows[0]], 0
    for i in range(maximum - 2):
        lo = min(math.floor((i + 1) * size) + 1, len(rows) - 1)
        hi = min(math.floor((i + 2) * size) + 1, len(rows))
        points = range(lo, max(lo + 1, hi))
        avg_x = sum(points) / len(points)
        avg_y = sum(y(j) for j in points) / len(points)
        start = math.floor(i * size) + 1
        end = min(math.floor((i + 1) * size) + 1, len(rows) - 1)
        selected = max(range(start, max(start + 1, end)), key=lambda j: abs((a - avg_x) * (y(j) - y(a)) - (a - j) * (avg_y - y(a))))
        result.append(rows[selected]); a = selected
    return result + [rows[-1]]

