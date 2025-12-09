def autoprice(title: str, description: str):
    # Placeholder intelligent rule
    base = 100
    if "brushless" in description.lower(): base += 50
    if "4wd" in description.lower(): base += 30
    return base