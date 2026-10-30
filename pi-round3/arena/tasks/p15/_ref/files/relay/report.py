def summary(events):
    """One line per region (in order of first appearance): how many events it had and their mean duration."""
    times_by_region = {}
    for event in events:
        times_by_region.setdefault(event["region"], []).append(event["ms"])
    if not times_by_region:
        return "no events"
    return "\n".join(
        f"{region}: {len(times)} events, avg {sum(times) / len(times):.1f} ms"
        for region, times in times_by_region.items()
    )
