"""
general python utils, unrelated to sc2
"""
import typing


def is_number(text: str) -> bool:
    try:
        _ = float(text)
    except ValueError:
        return False
    return True


def as_bool(value: typing.Any) -> bool:
    return str(value).lower() in ['1', 'true']
