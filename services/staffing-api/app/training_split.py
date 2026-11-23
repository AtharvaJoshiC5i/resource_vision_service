def split_training_buffer(total_days: int, ratio: float = 0.85) -> tuple[int, int]:
    """Handoff §11.1 — 85% training, 15% buffer (calendar days, round training)."""
    training = round(total_days * ratio)
    buffer = total_days - training
    return training, buffer