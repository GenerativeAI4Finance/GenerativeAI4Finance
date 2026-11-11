"""Synthetic macroeconomic and sector-event sequence generator."""


def generate_dataset(*args, **kwargs):
    from .macro_generator import generate_dataset as implementation

    return implementation(*args, **kwargs)


def write_dataset(*args, **kwargs):
    from .macro_generator import write_dataset as implementation

    return implementation(*args, **kwargs)


__all__ = ["generate_dataset", "write_dataset"]
