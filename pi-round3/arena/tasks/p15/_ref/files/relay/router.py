class Router:
    """Topic subscriptions."""

    def __init__(self):
        self._subs = {}

    def subscribe(self, topic, who):
        self._subs.setdefault(topic, set()).add(who)

    def unsubscribe(self, topic, who):
        self._subs.get(topic, set()).discard(who)

    def recipients(self, topic):
        return sorted(self._subs.get(topic, ()))

    def topics(self):
        return list(self._subs)
