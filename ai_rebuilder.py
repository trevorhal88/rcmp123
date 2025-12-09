def rebuild_listing(item):
    if not item.description:
        item.description = "Description unavailable — auto-repaired."
    if not item.title:
        item.title = "Untitled RC Item"
    return item