class CycleError(Exception):
    """The dependencies of the channels contain a cycle."""


def delivery_order(deps):
    """Order the channels so that every channel comes after the channels it depends on."""
    remaining = {}
    for channel, before in deps.items():
        remaining.setdefault(channel, set()).update(before)
        for dep in remaining[channel]:
            remaining.setdefault(dep, set())

    ready = {channel for channel, needs in remaining.items() if not needs}
    order = []
    while ready:
        channel = ready.pop()
        order.append(channel)
        for other, needs in remaining.items():
            if channel in needs:
                needs.discard(channel)
                if not needs:
                    ready.add(other)

    if len(order) != len(remaining):
        stuck = set(remaining) - set(order)
        raise CycleError("dependency cycle among: " + ", ".join(stuck))
    return order
