import heapq


class CycleError(Exception):
    """The dependencies of the channels contain a cycle."""


def delivery_order(deps):
    """Order the channels so that every channel comes after the channels it depends on.

    Among the channels that are ready, the alphabetically smallest one is delivered first.
    """
    remaining = {}
    for channel, before in deps.items():
        remaining.setdefault(channel, set()).update(before)
        for dep in remaining[channel]:
            remaining.setdefault(dep, set())

    ready = [channel for channel, needs in remaining.items() if not needs]
    heapq.heapify(ready)
    order = []
    while ready:
        channel = heapq.heappop(ready)
        order.append(channel)
        for other, needs in remaining.items():
            if channel in needs:
                needs.discard(channel)
                if not needs:
                    heapq.heappush(ready, other)

    if len(order) != len(remaining):
        stuck = sorted(set(remaining) - set(order))
        raise CycleError("dependency cycle among: " + ", ".join(stuck))
    return order
