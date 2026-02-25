def compute_carry_score(funding_rate: float, annualization_factor: int = 365 * 3) -> float:
    return funding_rate * annualization_factor
