"""Explicit stocked-shop fixture for trading and expedition scenarios."""
from game import CATALOG

def stock_shop(game):
    # Trading-rule fixtures represent an already-created character at base stats.
    game.state["creation"] = {"completed": True, "points": 0, "allocated": {}}
    defaults = ["greatsword", "longsword", "shield", "staff"]
    game.state["shelves"] = defaults[:]
    for item, template in zip(game.state["stock"], CATALOG):
        displayed = min(3, template["quantity"]) if item["id"] in defaults else 0
        item["quantity"] = displayed
        game.state["warehouse"][item["id"]] = template["quantity"] - displayed
