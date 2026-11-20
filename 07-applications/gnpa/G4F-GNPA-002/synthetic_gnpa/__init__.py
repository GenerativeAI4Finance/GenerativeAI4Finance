"""Lazy public API imports keep `python -m synthetic_gnpa.generator` clean."""

__all__ = [
    "generate_synthetic_history",
    "label_observations",
    "validate_history",
    "validate_labeled_observations",
]


def __getattr__(name):
    if name == "generate_synthetic_history":
        from .generator import generate_synthetic_history
        return generate_synthetic_history
    if name == "label_observations":
        from .labels import label_observations
        return label_observations
    if name in {"validate_history", "validate_labeled_observations"}:
        from . import validation
        return getattr(validation, name)
    raise AttributeError(name)
