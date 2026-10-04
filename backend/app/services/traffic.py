def classify_activity(avg):
    """Descriptive demo thresholds, NOT safety thresholds: quiet <2, steady 2-8, busy >8."""
    if avg is None: return "unknown"
    return "quiet" if avg < 2 else ("steady" if avg <= 8 else "busy")
