from datetime import datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_timestamp(dt: datetime) -> float:
    return dt.timestamp()


def from_timestamp(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


_WINDOW_MULTIPLIERS = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "w": 604800,
}


def window_to_seconds(window: str) -> int:
    if not window:
        return 3600
    window = window.strip().lower()
    for suffix, multiplier in _WINDOW_MULTIPLIERS.items():
        if window.endswith(suffix):
            num_str = window[: -len(suffix)].strip()
            if not num_str:
                num_str = "1"
            try:
                return int(float(num_str) * multiplier)
            except ValueError:
                return 3600
    try:
        return int(window)
    except ValueError:
        return 3600
