def summary(events):
    """One line per region: how many events it had and their mean duration."""
    events = list(events)
    if not events:
        return "no events"
    lines = []
    for region in set(e["region"] for e in events):
        times = [e["ms"] for e in events if e["region"] == region]
        lines.append(f"{region}: {len(times)} events, avg {sum(times) / len(times):.1f} ms")
    return "\n".join(lines)
