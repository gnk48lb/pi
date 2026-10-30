def unique(items):
    """Remove duplicates from `items`, keeping the first appearance of each."""
    return list(dict.fromkeys(items))
