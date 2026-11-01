"""Python rules and JSON persistence for Dungeon Merchant's trading prototype."""

import copy
import json
import math
from pathlib import Path
import random
import uuid

from commissions import CommissionMixin
from skills import SkillMixin
from equipment import EquipmentMixin, ACCESSORIES
from combat import CombatMixin
from final_boss import FinaleMixin
from pricing import PricingMixin


CATALOG = [
    {"id": "greatsword", "name": "Steel Greatsword", "mode": "bargain", "cost": 60, "price": 140, "quantity": 10},
    {"id": "longsword", "name": "Iron Longsword", "mode": "bargain", "cost": 35, "price": 80, "quantity": 12},
    {"id": "shield", "name": "Oak Shield", "mode": "fixed", "cost": 24, "price": 55, "quantity": 12},
    {"id": "hammer", "name": "Warhammer", "mode": "bargain", "cost": 42, "price": 95, "quantity": 10},
    {"id": "staff", "name": "Ashwood Staff", "mode": "bargain", "cost": 30, "price": 70, "quantity": 12},
    {"id": "book", "name": "Prayer Book", "mode": "fixed", "cost": 18, "price": 45, "quantity": 12},
    {"id": "bow", "name": "Hunter's Bow", "mode": "fixed", "cost": 32, "price": 75, "quantity": 12},
    {"id": "leather_armour", "name": "Leather Armour", "mode": "fixed", "cost": 28, "price": 60, "quantity": 6, "category": "armour"},
    {"id": "chainmail", "name": "Chainmail", "mode": "bargain", "cost": 48, "price": 105, "quantity": 6, "category": "armour"},
    {"id": "plate_armour", "name": "Plate Armour", "mode": "bargain", "cost": 80, "price": 180, "quantity": 6, "category": "armour"},
    {"id": "mage_robes", "name": "Mage Robes", "mode": "bargain", "cost": 36, "price": 80, "quantity": 6, "category": "armour"},
    {"id": "cleric_robes", "name": "Cleric Robes", "mode": "fixed", "cost": 32, "price": 70, "quantity": 6, "category": "armour"},
]
CATALOG += ACCESSORIES
CATALOG.append({"id":"life_potion","name":"Life Potion","category":"consumable","mode":"fixed","cost":20,"price":23,"quantity":6,"healing":40})
MOODS = ["Angry", "Displeased", "Neutral", "Pleased", "Happy"]
# These are starting-offer preferences, not revealed customer price limits.
OPENING_PRICE_MODES = {"patient": 0.90, "proud": 1.08, "impatient": 1.02}
DAYS_PER_MONTH = 28
DAYS_PER_YEAR = 336
CUSTOMERS_PER_DAY = 10
SHELF_CAPACITY = 4
UNITS_PER_SHELF = 20
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def calendar_date(day):
    offset = day - 1
    return {"day": day, "year": offset // DAYS_PER_YEAR + 1,
            "week": offset % DAYS_PER_YEAR // 7 + 1,
            "weekday": WEEKDAYS[offset % 7],
            "month": offset % DAYS_PER_YEAR // DAYS_PER_MONTH + 1,
            "day_of_month": offset % DAYS_PER_MONTH + 1}


def new_daily():
    return {"admitted": 0, "served": 0, "revenue": 0, "sales": 0, "closed": False}


STARTING_GOLD = 1000
TOTAL_DEBT = 20000
MONTHLY_REPAYMENT = 1000
ECONOMY_VERSION = 3

def new_loan():
    return {"original": TOTAL_DEBT, "balance": TOTAL_DEBT, "principal_per_month": MONTHLY_REPAYMENT,
            "rate_percent": 0, "interest_arrears": 0, "principal_arrears": 0,
            "principal_paid": 0, "interest_paid": 0, "payments": []}
EQUIPMENT = {
    "greatsword": "armour and a two-handed sword strapped across the back",
    "sword": "armour and a single-handed sword",
    "hammer_shield": "heavy armour, a warhammer and a shield",
    "staff": "loose robes and a wooden staff",
    "prayer_book": "clerical robes and an open prayer book",
    "bow": "leather armour, a bow and a quiver of arrows",
}
NAMES = {
    "male": ["Rowan", "Darian", "Finn", "Orin", "Tarin", "Bram", "Nolan", "Silas", "Aren", "Garrick"],
    "female": ["Elin", "Lyra", "Mira", "Brakka", "Vera", "Tessa", "Neris", "Iona", "Rhea", "Sable"],
}
SURNAMES = ["Ashford", "Reed", "Vale", "Thorn", "Stone", "Hollow", "Moss", "Ember", "Grey", "Brook"]


def positive_int(value, label="Price"):
    """Reject booleans, fractional values and unreasonable transaction amounts."""
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 99999:
        raise ValueError(f"{label} must be a whole number from 1 to 99,999.")
    return value


class Game(FinaleMixin, CommissionMixin, SkillMixin, EquipmentMixin, CombatMixin, PricingMixin):
    def __init__(self, asset_root, save_path, rng=None, load_existing=True):
        """Load or create a campaign, then migrate older saves without granting free stock."""
        self.asset_root = Path(asset_root)
        self.save_path = Path(save_path)
        self.rng = rng or random.Random()
        self.portraits = json.loads((Path(asset_root) / "characters/manifest.json").read_text(encoding="utf-8"))["characters"]
        self.professions = json.loads((Path(asset_root) / "professions.json").read_text(encoding="utf-8"))
        for role in self.professions.values():
            role["preferred_items"] += [item["id"] for item in ACCESSORIES if item["id"] not in role["preferred_items"]]
        for role in self.professions.values():
            role["preferred_items"].append("life_potion")
        self.state = {
            "version": 1, "economy_version": ECONOMY_VERSION, "gold": STARTING_GOLD, "player": {"eloquence": 3, "wisdom": 2, "luck": 1},
            "stock": [dict(copy.deepcopy(item), quantity=0) for item in CATALOG], "customers": {}, "current_id": None,
            "deal": None, "last_roll": None, "total_visits": 0,
            "message": "The shop is quiet. Ring for the next customer.",
            "day": 1, "daily": new_daily(), "day_summary": None,
            "day_history": [], "loan": new_loan(),
            "creation": {"completed": False, "points": 5, "allocated": {}},
        }
        if load_existing and self.save_path.exists():
            try:
                loaded = json.loads(self.save_path.read_text(encoding="utf-8"))
                self._validate_save(loaded)
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError(f"Cannot read save file {self.save_path}. Original file preserved: {exc}") from exc
            self.state = loaded
            self._upgrade_professions()
            self._upgrade_time()
        self._upgrade_economy()
        self._upgrade_inventory()
        self._upgrade_commissions()
        self._upgrade_skills()
        self._upgrade_equipment()
        self.state.setdefault("arrival_history", [])
        if not self.state["arrival_history"] and self.state.get("current_id") and not self.customer().get("final_boss"):
            self.state["arrival_history"].append({"customer_id":self.customer()["id"],"portrait":self.customer()["portrait"]})
        if self.state.get("combat") and self.state["combat"]["status"] == "active":
            import time
            self.state["combat"]["last_tick"] = time.time()
            for side in ("player", "enemy"):
                self.state["combat"][side+"_next"] = time.time()+self.state["combat"][side+"_interval"]
        self.state.setdefault("creation", {"completed": True, "points": 0, "allocated": {}})
        self.state.setdefault("intro_seen", self.has_progress())
        self.normalize_sale_prices()
        self._repair_initial_fixed_offer()
        self.check_ending()
        if self.state["current_id"] and not self.state["deal"] and not self.customer().get("final_boss"):
            c = self.customer()
            if c["wants"] not in self._displayed_preferences(c):
                c["wants"] = self.rng.choice(self._displayed_preferences(c)) if self._displayed_preferences(c) else None
                self.state["message"] = self._request_message(c)

    def _upgrade_economy(self):
        """Apply new debt terms once; retain past principal payments and receipts."""
        if self.state.get("economy_version", 0) < ECONOMY_VERSION:
            loan = self.state["loan"]
            loan.update(original=TOTAL_DEBT, balance=max(0, TOTAL_DEBT - loan["principal_paid"]),
                        principal_per_month=MONTHLY_REPAYMENT, rate_percent=0, interest_arrears=0)
            loan["principal_arrears"] = min(loan.get("principal_arrears",0),loan["balance"])
            if self.state.get("ending"):
                self.state["ending"]["repaid"] = TOTAL_DEBT
            self.state["economy_version"] = ECONOMY_VERSION
        self.state.setdefault("rent", {"weekly": 200, "arrears": 0, "paid": 0, "payments": []})

    def check_ending(self):
        self.prepare_finale()

    def repay_early(self, amount):
        self.require_peace()
        if self.state["current_id"] is not None:
            raise ValueError("See your customer out before repaying the loan.")
        amount=positive_int(amount,"Repayment")
        loan=self.state["loan"];due=loan["balance"]+loan["interest_arrears"]
        if amount>min(self.state["gold"],due):
            raise ValueError("Choose an amount within your cash and remaining debt.")
        interest=min(amount,loan["interest_arrears"]);principal=amount-interest
        self.state["gold"]-=amount;loan["balance"]-=principal
        loan["interest_arrears"]-=interest;loan["interest_paid"]+=interest;loan["principal_paid"]+=principal
        loan["principal_arrears"]=min(loan["balance"],max(0,loan["principal_arrears"]-principal))
        loan["payments"].append({"day":self.state["day"],"early":True,"principal_due":principal,"interest_due":interest,"new_interest":0,"principal_paid":principal,"interest_paid":interest,"paid":amount,"shortfall":0,"balance":loan["balance"],"paid_off":loan["balance"]==0 and loan["interest_arrears"]==0})
        self.state["message"]="Repaid "+str(amount)+" gold."

    def _settle_rent(self):
        rent = self.state["rent"]
        due = rent["weekly"] + rent["arrears"]
        paid = min(self.state["gold"], due)
        self.state["gold"] -= paid
        rent["arrears"] = due - paid
        rent["paid"] += paid
        receipt = {"day": self.state["day"], "due": due, "paid": paid, "shortfall": due - paid}
        rent["payments"].append(receipt)
        return receipt

    def _repair_initial_fixed_offer(self):
        """Honor the entry-price promise for an already admitted legacy shopper."""
        deal = self.state.get("deal")
        if not self.state["current_id"] or not deal or deal.get("status") != "agreed" or deal.get("sale_allowed") is not False:
            return
        c = self.customer()
        item = self.item(deal["item_id"])
        if (item["mode"] == "fixed" and c["wants"] == item["id"] and
                item["id"] in self.state["shelves"] and item["quantity"] > 0 and
                deal.get("agreed") == item["price"] and c["budget"] >= item["price"]):
            c["willingness"][item["id"]] = max(item["price"], c["willingness"].get(item["id"], 0))
            deal["sale_allowed"] = True
            self.state["message"] = f"I will take it for {item['price']} gold."

    def has_progress(self):
        return bool(self.state.get("intro_seen") or self.state.get("creation",{}).get("allocated") or self.state["day"] > 1 or
                    self.state["total_visits"] or self.state["gold"] != STARTING_GOLD or
                    self.state.get("shelf_settings") or self.state.get("commissions") or
                    ("caravan" in self.state and not self.state["caravan"]["open"]))

    def new_game(self):
        """Archive the current campaign before starting a separate fresh story."""
        fresh = Game(self.asset_root, self.save_path, self.rng, load_existing=False)
        if self.has_progress():
            backup = self.save_path.with_name(self.save_path.stem + "-backup-" + uuid.uuid4().hex[:12] + ".json")
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        self.state = fresh.state

    def allocate_attributes(self, allocation):
        creation=self.state["creation"]
        if creation["completed"]:raise ValueError("Starting attributes have already been assigned.")
        attributes=("strength","dexterity","wisdom","eloquence","luck")
        if not isinstance(allocation,dict) or set(allocation)-set(attributes):raise ValueError("Choose valid attributes.")
        values={key:allocation.get(key,0) for key in attributes}
        if any(type(value) is not int or value<0 for value in values.values()) or sum(values.values())!=creation["points"]:
            raise ValueError("Distribute all 5 starting points.")
        old_max=self.player_stats()["max_hp"]
        for key,value in values.items():self.state["player"][key]=self.state["player"].get(key,2)+value
        self.shift_max_health(old_max)
        creation.update(completed=True,allocated=values,points=0)
        self.state["message"]="Your story begins."

    def finish_intro(self):
        self.state["intro_seen"] = True

    def _new_caravan(self, is_open=True):
        return {"day": self.state["day"], "open": is_open, "purchases": [],
                "stock": [{"item_id": item["id"], "price": item["cost"], "quantity": 40} for item in CATALOG]}

    def _upgrade_inventory(self):
        """Separate owned goods into display shelves and storage without loss."""
        self.state.setdefault("shelf_settings", {})
        for customer in self.state["customers"].values():
            self._ensure_buying_traits(customer)
        if "warehouse" not in self.state:
            defaults = ["greatsword", "longsword", "shield", "staff"]
            active = self.state.get("deal")
            if active and self.state["current_id"]:
                defaults = [active["item_id"]] + [x for x in defaults if x != active["item_id"]]
            self.state["shelf_capacity"] = SHELF_CAPACITY
            self.state["shelves"] = defaults[:SHELF_CAPACITY]
            self.state["warehouse"] = {}
            for item in self.state["stock"]:
                keep = min(item["quantity"], 3) if item["id"] in self.state["shelves"] else 0
                if active and item["id"] == active["item_id"]:
                    keep = item["quantity"]
                self.state["warehouse"][item["id"]] = item["quantity"] - keep
                item["quantity"] = keep
        for item in self.state["stock"]:
            self.state["warehouse"].setdefault(item["id"], 0)
        self.state["shelves"] = [item_id if item_id and self.item(item_id)["quantity"] > 0 else None
                                 for item_id in self.state["shelves"]]
        if "caravan" not in self.state:
            before_opening = (self.state["day"] - 1) % 7 == 0 and not self.state["current_id"] and self.state["daily"]["admitted"] == 0
            self.state["caravan"] = self._new_caravan(before_opening)
        self.state["caravan"].setdefault("purchases", [])
        listed = {entry["item_id"] for entry in self.state["caravan"]["stock"]}
        for item in CATALOG:
            if item["id"] not in listed:
                self.state["caravan"]["stock"].append({"item_id": item["id"], "price": item["cost"], "quantity": 40})

    def visit_caravan(self):
        self.require_peace()
        if (self.state["day"] - 1) % 7 or self.state["caravan"]["day"] != self.state["day"]:
            raise ValueError("The caravan visits on Mondays.")
        if self.state["daily"]["closed"]:
            raise ValueError("The shop has closed for today.")
        if self.state["current_id"] is not None:
            raise ValueError("See your customer out before visiting the caravan.")
        self.state["caravan"]["open"] = True
        self.state["message"] = "The Monday caravan awaits."

    def finish_market(self):
        if not self.state["caravan"]["open"]:
            raise ValueError("The caravan has already departed.")
        self.state["caravan"]["open"] = False
        self.state["message"] = "The shop is ready to open."

    def merchant_buy(self, item_id, quantity):
        quantity = positive_int(quantity, "Quantity")
        caravan = self.state["caravan"]
        if not caravan["open"] or caravan["day"] != self.state["day"] or (self.state["day"] - 1) % 7:
            raise ValueError("The travelling merchant is not here.")
        self.item(item_id)
        listing = next((x for x in caravan["stock"] if x["item_id"] == item_id), None)
        if listing is None or listing["quantity"] < quantity:
            raise ValueError("The merchant does not have that many.")
        unit_cost = self.merchant_price(listing["price"])
        total = unit_cost * quantity
        if total > self.state["gold"]:
            raise ValueError("Not enough gold.")
        item = self.item(item_id)
        owned = self.state["warehouse"][item_id] + item["quantity"]
        item["acquisition_cost"] = round((item.get("acquisition_cost", item["cost"]) * owned + total) / (owned + quantity), 2)
        self.state["gold"] -= total
        listing["quantity"] -= quantity
        self.state["warehouse"][item_id] += quantity
        caravan["purchases"].append({"id": uuid.uuid4().hex, "item_id": item_id, "quantity": quantity,
                                     "unit_cost": unit_cost, "total": total})
        self.state["message"] = f"Bought {quantity} {self.item(item_id)['name']} for {total} gold."

    def _shelf_edit_allowed(self, slot, incoming=None):
        if isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot < self.state["shelf_capacity"]:
            raise ValueError("Unknown shelf.")
        active = self.state.get("deal")
        old = self.state["shelves"][slot]
        if active and active["status"] in ("negotiating", "agreed", "payment") and active["item_id"] in (old, incoming):
            raise ValueError("Finish this item's negotiation before replacing its shelf.")

    def place_stock(self, slot, item_id, quantity, mode, price):
        quantity = positive_int(quantity, "Quantity")
        price = positive_int(price)
        self.item(item_id)
        self._shelf_edit_allowed(slot, item_id)
        if mode not in ("bargain", "fixed"):
            raise ValueError("Choose Bargain or Marked price.")
        self.validate_sale_price(self.item(item_id),price,mode)
        if quantity > UNITS_PER_SHELF:
            raise ValueError(f"A shelf holds at most {UNITS_PER_SHELF} items.")
        if item_id in self.state["shelves"] and self.state["shelves"].index(item_id) != slot:
            raise ValueError("This item is already on another shelf. Restock that shelf instead.")
        old = self.state["shelves"][slot]
        if old:
            old_item = self.item(old)
            self.state["warehouse"][old] += old_item["quantity"]
            old_item["quantity"] = 0
        if self.state["warehouse"][item_id] < quantity:
            raise ValueError("Not enough items in the warehouse.")
        self.state["warehouse"][item_id] -= quantity
        item = self.item(item_id)
        item.update(quantity=quantity, mode=mode, price=price)
        self.state["shelf_settings"][item_id] = {"mode": mode, "price": price, "quantity": quantity}
        self.state["shelves"][slot] = item_id
        self.state["message"] = f"{item['name']} placed on shelf {slot + 1}."

    def restock(self, slot, quantity):
        quantity = positive_int(quantity, "Quantity")
        if isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot < self.state["shelf_capacity"]:
            raise ValueError("Unknown shelf.")
        item_id = self.state["shelves"][slot]
        if not item_id:
            raise ValueError("Place an item on this shelf first.")
        item = self.item(item_id)
        if quantity > self.state["warehouse"][item_id]:
            raise ValueError("Not enough items in the warehouse.")
        if item["quantity"] + quantity > UNITS_PER_SHELF:
            raise ValueError(f"A shelf holds at most {UNITS_PER_SHELF} items.")
        self.state["warehouse"][item_id] -= quantity
        item["quantity"] += quantity
        self.state["message"] = f"Restocked {quantity} {item['name']}."

    def return_stock(self, slot):
        self._shelf_edit_allowed(slot)
        item_id = self.state["shelves"][slot]
        if item_id:
            item = self.item(item_id)
            self.state["warehouse"][item_id] += item["quantity"]
            item["quantity"] = 0
            self.state["shelves"][slot] = None
        self.state["message"] = "Shelf cleared. Items returned to the warehouse."

    def _upgrade_time(self):
        """Older trading saves start on Monday without retroactive charges."""
        self.state.setdefault("day", 1)
        if "daily" not in self.state:
            self.state["daily"] = new_daily()
            if self.state["current_id"]:
                self.state["daily"]["admitted"] = 1
        self.state.setdefault("day_summary", None)
        self.state.setdefault("day_history", [])
        self.state.setdefault("loan", new_loan())
        if not isinstance(self.state["day"], int) or self.state["day"] < 1:
            raise ValueError("Invalid game date.")

    def _assign_profession(self, customer, portrait):
        weapon = portrait["weapon"].replace("_outlaw", "")
        role = self.professions[weapon]
        customer.update(weapon_type=weapon, profession=role["name"], armour=role["armour"], accessories=role["accessories"])

    def _upgrade_professions(self):
        """Add role data to existing saves without replacing identity or history."""
        if self.state["message"] == "I cannot afford that. No roll can change the coins I have.":
            self.state["message"] = "That is more than I can afford."
        portrait_by_file = {p["file"]: p for p in self.portraits}
        for customer in self.state["customers"].values():
            portrait = portrait_by_file.get(customer["portrait"])
            if portrait:
                self._assign_profession(customer, portrait)
                customer["wanted"] = "_outlaw" in portrait["weapon"]
        existing = {item["id"] for item in self.state["stock"]}
        for item in CATALOG:
            if item["id"] not in existing:
                self.state["stock"].append(dict(copy.deepcopy(item), quantity=0) if "warehouse" in self.state else copy.deepcopy(item))
        for customer in self.state["customers"].values():
            for item in self.state["stock"]:
                customer["willingness"].setdefault(item["id"], min(customer["budget"], item["cost"] * 2))
        if self.state["current_id"]:
            c = self.customer()
            role = self.professions[c["weapon_type"]]
            active = self.state.get("deal")
            # Preserve an ongoing agreed/negotiating deal until the visitor leaves.
            if not active and not c.get("wants"):
                c["wants"] = role["preferred_items"][0]
                self.state["message"] = f"I am heading to {c['destination']}. I am looking for {self.item(c['wants'])['name'].lower()}."

    def _validate_save(self, data):
        if not isinstance(data, dict) or data.get("version") != 1:
            raise ValueError("Unsupported save format.")
        if not isinstance(data.get("gold"), int) or data["gold"] < 0:
            raise ValueError("Invalid gold balance.")
        if not isinstance(data.get("customers"), dict) or not isinstance(data.get("stock"), list):
            raise ValueError("Missing customer or stock data.")
        for key in ("version", "gold", "player", "stock", "customers", "current_id", "deal", "last_roll", "total_visits", "message"):
            if key not in data:
                raise ValueError(f"Missing {key}.")
        if data["current_id"] is not None and data["current_id"] not in data["customers"]:
            raise ValueError("Unknown current customer.")
        for item in data["stock"]:
            positive_int(item["price"])
            if not isinstance(item["quantity"], int) or item["quantity"] < 0:
                raise ValueError("Invalid inventory quantity.")
        for customer in data["customers"].values():
            if not 0 <= customer["mood"] < len(MOODS):
                raise ValueError("Invalid customer mood.")

    def save(self):
        """Write a complete temporary file before atomically replacing the save."""
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.save_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.save_path)

    def customer(self):
        key = self.state["current_id"]
        if key is None:
            raise ValueError("There is no customer at the counter.")
        return self.state["customers"][key]

    def item(self, item_id):
        for item in self.state["stock"]:
            if item["id"] == item_id:
                return item
        raise ValueError("Unknown item.")

    def _ensure_buying_traits(self, customer):
        """Hidden shopping tendencies persist with identity, not portrait art."""
        if "buying_style" not in customer:
            customer["buying_style"] = self.rng.choice(["thrifty", "practical", "quality"])
        if "urgency" not in customer:
            customer["urgency"] = self.rng.choice(["browsing", "prepared", "urgent"])
        customer.setdefault("observed", [])

    def _new_customer(self, portraits=None):
        portrait = self.rng.choice(self.portraits if portraits is None else portraits)
        weapon = portrait["weapon"].replace("_outlaw", "")
        name = self.rng.choice(NAMES[portrait["sex"]]) + " " + self.rng.choice(SURNAMES)
        existing = {c["name"] for c in self.state["customers"].values()}
        if name in existing:
            name += " " + str(len(existing) + 1)
        # Wealth and personality are independent of portrait selection.
        wealth = self.rng.choice(["careful", "comfortable", "wealthy"])
        budget = self.rng.randint(*{"careful": (55, 110), "comfortable": (110, 220), "wealthy": (220, 400)}[wealth])
        c = {
            "id": uuid.uuid4().hex, "name": name, "race": portrait["race"].title(),
            "wanted": "_outlaw" in portrait["weapon"], "sex": portrait["sex"], "portrait": portrait["file"], "equipment": EQUIPMENT[weapon],
            "personality": self.rng.choice(["patient", "proud", "impatient"]), "wealth": wealth,
            "budget": budget, "mood": 2, "visits": 0, "purchases": [], "actions": [],
            "known": [], "wants": None, "destination": None, "willingness": {}, "refused": [],
        }
        self._assign_profession(c, portrait)
        self._ensure_buying_traits(c)
        self.state["customers"][c["id"]] = c
        return c

    def _displayed_preferences(self, customer):
        if customer.get("defeated") or customer.get("final_boss"):
            return []
        """Storage never contributes to the customer's shopping choices."""
        preferred=self.professions[customer["weapon_type"]]["preferred_items"]
        return [item_id for item_id in self.state["shelves"] if item_id and self.item(item_id)["quantity"]>0
                and self.item(item_id).get("base_id",item_id) in preferred]

    def _shopping_choices(self, customer, budget, willingness):
        choices = []
        for item_id in self._displayed_preferences(customer):
            item = self.item(item_id)
            minimum = item["price"] if item["mode"] == "fixed" else max(1, (item["cost"] * 70 + 99) // 100)
            # Nobody enters for labels beyond any plausible valuation of this item.
            if item["mode"] == "fixed" and item["price"] > math.ceil(item["cost"] * 3.2 * 1.12):
                continue
            # Visitors must both afford and accept the displayed starting price.
            if min(budget, willingness[item_id]) >= minimum:
                choices.append(item_id)
        return choices

    def _visit_funds(self, customer):
        displayed = self._displayed_preferences(customer)
        if not displayed:
            return customer["budget"], customer["willingness"], []
        target = self.rng.choice(displayed)
        reference_price = self.item(target)["price"]
        budget = self.rng.randint(reference_price * 2, reference_price * 5)
        self._ensure_buying_traits(customer)
        value_factor = {"thrifty": 0.85, "practical": 1.0, "quality": 1.12}[customer["buying_style"]]
        willingness = {item["id"]: min(budget, max(1, int(item["cost"] * self.rng.uniform(1.6, 3.2) * value_factor)))
                       for item in self.state["stock"]}
        return budget, willingness, [target] if target in self._shopping_choices(customer, budget, willingness) else []

    def _request_message(self, customer):
        greeting = "Welcome back. " if customer["visits"] > 1 else ""
        request = (f"I am looking at the {self.item(customer['wants'])['name'].lower()}."
                   if customer["wants"] else "I do not see anything I need on your shelves.")
        return f"{greeting}I am heading to {customer['destination']}. {request}"

    def arrive(self):
        """Choose a compatible, affordable visitor and enforce recent portrait variety."""
        self.require_peace()
        if self.state["caravan"]["open"]:
            raise ValueError("Return from the caravan before opening the shop.")
        if self.state["daily"]["closed"] or self.state["daily"]["admitted"] >= CUSTOMERS_PER_DAY:
            raise ValueError("The shop is closed for today. Start the next day.")
        if self.state["current_id"] is not None:
            raise ValueError("See the current customer out first.")
        # Only shoppers who see a suitable stocked item enter the shop.
        displayed = {self.item(item_id).get("base_id",item_id) for item_id in self.state["shelves"]
                     if item_id is not None and self.item(item_id)["quantity"] > 0}
        portraits = [p for p in self.portraits
                     if displayed.intersection(self.professions[p["weapon"].replace("_outlaw", "")]["preferred_items"])]
        eligible = []
        for customer in self.state["customers"].values():
            if not self._adventurer_busy(customer["id"]) and self._displayed_preferences(customer):
                funds = self._visit_funds(customer)
                if funds[2]:
                    eligible.append((customer, *funds))
        if not portraits and not eligible:
            raise ValueError("No customers are interested. Restock the shelves before admitting a customer.")
        # A return visit must not monopolize the next few admissions. Artwork
        # variety is shared by new and returning identities, and survives reloads.
        original_portraits, original_eligible = portraits, eligible
        recent = self.state.get("arrival_history", [])[-3:]
        recent_ids = {entry["customer_id"] for entry in recent}
        spaced_returns = [entry for entry in eligible if entry[0]["id"] not in recent_ids]
        if portraits or spaced_returns:
            eligible = spaced_returns
        pool = {p["file"] for p in portraits} | {entry[0]["portrait"] for entry in eligible}
        allowed = pool
        for window in range(len(recent), -1, -1):
            blocked = {entry["portrait"] for entry in recent[-window:]} if window else set()
            allowed = pool - blocked
            if allowed:break
        portraits = [p for p in portraits if p["file"] in allowed]
        eligible = [entry for entry in eligible if entry[0]["portrait"] in allowed]
        selected = self.rng.choice(eligible) if eligible and (not portraits or self.rng.random() < .35) else None
        returning_adventurers = [entry for entry in eligible if entry[0].get("commission_return_visit")]
        if returning_adventurers:
            selected = self.rng.choice(returning_adventurers)
        if selected is None:
            # Rejected passers-by do not become customers, gain wealth, or use daily slots.
            for _ in range(200):
                candidate = self._new_customer(portraits)
                funds = self._visit_funds(candidate)
                if funds[2]:
                    selected = (candidate, *funds)
                    break
                del self.state["customers"][candidate["id"]]
        if selected is None and eligible:
            selected = self.rng.choice(eligible)
        if selected is None and original_eligible:
            selected = self.rng.choice(original_eligible)
        if selected is None and original_portraits != portraits:
            # Affordability can leave a smaller real pool than the display implies.
            for _ in range(200):
                candidate = self._new_customer(original_portraits)
                funds = self._visit_funds(candidate)
                if funds[2]:
                    selected = (candidate, *funds)
                    break
                del self.state["customers"][candidate["id"]]
        if selected is None:
            raise ValueError("No shoppers can afford the displayed goods at these prices. Lower prices or change the stock.")
        c, budget, willingness, choices = selected
        self.ensure_belongings(c)
        self.state["combat"] = None
        c.pop("commission_return_visit", None)
        c["visits"] += 1
        c["budget"] = budget
        c["willingness"] = willingness
        c["wants"] = self.rng.choice(choices)
        c["destination"] = self.rng.choice(["the abandoned mine", "the northern pass", "the old burial grounds", "the marsh road"])
        c["refused"] = []
        self.state.update(current_id=c["id"], deal=None, last_roll=None)
        self.state["total_visits"] += 1
        self.state.setdefault("arrival_history", []).append({"customer_id":c["id"],"portrait":c["portrait"]})
        self.state["arrival_history"] = self.state["arrival_history"][-12:]
        self.state["daily"]["admitted"] += 1
        self.state["message"] = self._request_message(c)

    def leave(self):
        """Finish one visit; the tenth departure closes and settles the current day."""
        if self.state.get("combat") and self.state["combat"]["status"] == "active":
            raise ValueError("You cannot dismiss someone during a fight.")
        if self.state["deal"] and self.state["deal"]["status"] == "payment":
            raise ValueError("Collect the coin pouch before sending the customer away.")
        c = self.customer()
        self.state.update(current_id=None, deal=None, last_roll=None, message=f"{c['name']} has left the shop.")
        if c.get("final_boss"):return
        self.state["daily"]["served"] += 1
        if self.state["daily"]["served"] == CUSTOMERS_PER_DAY:
            self._close_day()

    def _settle_loan(self):
        loan = self.state["loan"]
        if loan["balance"] == 0 and loan["interest_arrears"] == 0:
            return None
        # Round interest upward to a whole gold coin; charge only unpaid principal.
        interest = (loan["balance"] * loan["rate_percent"] + 99) // 100
        interest_due = interest + loan["interest_arrears"]
        principal_due = min(loan["balance"], loan["principal_per_month"] + loan["principal_arrears"])
        interest_paid = min(self.state["gold"], interest_due)
        principal_paid = min(self.state["gold"] - interest_paid, principal_due)
        payment = interest_paid + principal_paid
        self.state["gold"] -= payment
        loan["balance"] -= principal_paid
        loan["interest_arrears"] = interest_due - interest_paid
        loan["principal_arrears"] = principal_due - principal_paid
        loan["interest_paid"] += interest_paid
        loan["principal_paid"] += principal_paid
        receipt = {"day": self.state["day"], "principal_due": principal_due,
                   "interest_due": interest_due, "new_interest": interest,
                   "principal_paid": principal_paid, "interest_paid": interest_paid,
                   "paid": payment, "shortfall": principal_due + interest_due - payment,
                   "balance": loan["balance"],
                   "paid_off": loan["balance"] == 0 and loan["interest_arrears"] == 0}
        loan["payments"].append(receipt)
        return receipt

    def _close_day(self):
        """Settle rent and monthly debt once, then retain the daily report."""
        if self.state["daily"]["closed"]:
            return
        self.state["daily"]["closed"] = True
        rent_receipt = self._settle_rent() if self.state["day"] % 7 == 0 else None
        receipt = self._settle_loan() if self.state["day"] % DAYS_PER_MONTH == 0 else None
        summary = {"date": calendar_date(self.state["day"]),
                   "revenue": self.state["daily"]["revenue"], "sales": self.state["daily"]["sales"],
                   "customers": self.state["daily"]["served"], "loan_payment": receipt, "rent_payment": rent_receipt,
                   "closing_gold": self.state["gold"]}
        self.state["day_summary"] = summary
        self.state["day_history"].append(copy.deepcopy(summary))
        self.state["message"] = "The last customer has left. Time to count today's takings."

    def skip_day(self):
        """Close early without inventing sales or charging the loan twice."""
        if self.state["daily"]["closed"]:
            raise ValueError("The shop is already closed for today.")
        if self.state["current_id"] is not None:
            self.leave()
        self.state["caravan"]["open"] = False
        self.state.update(deal=None, last_roll=None)
        self._close_day()
        self.state["message"] = "The shop closed early. Time to count today's takings."

    def rest_after_defeat(self):
        """Close the injured merchant's day and recover in one transaction."""
        if self.state["player_health"] > 0:
            raise ValueError("You do not need to recover from defeat.")
        if self.state.get("combat") and self.state["combat"]["status"] in ("active","threatened","ready"):
            raise ValueError("Finish the confrontation first.")
        if not self.state["daily"]["closed"]:
            self.skip_day()
        elif self.state["current_id"] is not None:
            self.leave()
        self.next_day()
        self.state["message"] = "You rested until morning. Your health is restored."

    def next_day(self):
        """Advance the calendar, resolve due expeditions and restore player health."""
        if self.state["current_id"] is not None or not self.state["daily"]["closed"]:
            raise ValueError("Close the shop before starting the next day.")
        self.state["day"] += 1
        self.state["daily"] = new_daily()
        self.state["day_summary"] = None
        if (self.state["day"] - 1) % 7 == 0:
            self.state["caravan"] = self._new_caravan()
        self.state.update(deal=None, last_roll=None, message="A new day. The shop is open.")
        self._resolve_commissions()
        self._upgrade_equipment()
        self.state["player_health"] = self.player_stats()["max_hp"]
        self.state["combat"] = None

    def inspect(self, clue):
        c = self.customer()
        if clue not in ("equipment", "accessories", "manner", "purse"):
            raise ValueError("Unknown observation.")
        self._ensure_buying_traits(c)
        style = {"thrifty": "They compare prices before workmanship. A small premium will be easier to justify than a large one.", "practical": "They check fit and durability. A fair, useful purchase matters more than ornament.", "quality": "They carefully examine the stitching and fittings. They value workmanship and are more receptive to a premium."}[c["buying_style"]]
        urgency = {"browsing": "They browse slowly, with no journey pressing them. There is little reason for them to pay extra today.", "prepared": "Their supplies are packed for the road. They have time to consider a sensible offer.", "urgent": "They keep glancing toward the road. They need equipment soon and may accept a premium, but dislike drawn-out bargaining."}[c["urgency"]]
        text = {
            "equipment": f"I can see {c['equipment']}. Their actual skill is harder to judge. {style}",
            "accessories": f"{c['accessories']}. Their purpose, quality and value would require closer appraisal; decoration alone proves little. {style}",
            "manner": {"patient": "They study the shelves without rushing me.", "proud": "They speak with confidence and dislike being dismissed.", "impatient": "Their fingers drum on the counter. They seem impatient."}[c["personality"]] + " " + urgency,
            "purse": {"careful": "They count a few coins twice before putting them away.", "comfortable": "Several coins clink inside their pouch; they still check each price.", "wealthy": "A heavy pouch rests at their belt. Wealth does not guarantee generosity."}[c["wealth"]],
        }[clue]
        if clue not in c["observed"]:
            c["observed"].append(clue)
        if text not in c["known"]:
            c["known"].append(text)
        self.state["message"] = text

    def set_price(self, item_id, price):
        if self.state["current_id"] is not None:
            raise ValueError("Change shelf labels between customers.")
        item = self.item(item_id)
        price=positive_int(price)
        self.validate_sale_price(item,price)
        item["price"] = price
        self.state["message"] = f"{item['name']} price set to {price} gold."

    def _opening_offer(self, item, customer):
        """Weighted opening offer inside cost +/-30%, bounded by ability to pay.

        A triangular distribution makes edge prices rare. Personality shifts its
        peak; the merchant's price label never enters this calculation.
        """
        cost = item["cost"]
        lower = max(1, (cost * 70 + 99) // 100)
        upper = min(cost * 130 // 100, customer["budget"], customer["willingness"][item["id"]],self.sale_cap(item,"bargain"))
        if upper < lower:
            return None
        peak = min(upper, max(lower, cost * OPENING_PRICE_MODES[customer["personality"]]))
        return max(lower, min(upper, round(self.rng.triangular(lower, upper, peak))))

    def begin(self, item_id):
        self.require_peace()
        if self.customer().get("trade_blocked_visit") == self.customer()["visits"]:
            raise ValueError("This customer will not trade with you again today.")
        c, item = self.customer(), self.item(item_id)
        if item_id not in self.state["shelves"]:
            raise ValueError("Place this item on a shelf before offering it.")
        if self.state["deal"] and self.state["deal"]["status"] in ("negotiating", "agreed", "payment"):
            raise ValueError("Finish or end the current negotiation first.")
        if item["quantity"] <= 0:
            raise ValueError("This item is out of stock.")
        if item_id in c["refused"]:
            raise ValueError("They have already declined this item during this visit.")
        self.state["last_roll"] = None
        maximum = min(c["budget"], c["willingness"][item_id])
        self.state["deal"] = {"item_id": item_id, "status": "negotiating", "offer": None, "agreed": None, "round": 0, "failures": 0, "last_quote": None}
        if item["mode"] == "fixed":
            self.state["deal"].update(status="agreed", agreed=item["price"], sale_allowed=item["price"] <= maximum)
            self.state["message"] = (f"I will take it for {item['price']} gold." if item["price"] <= maximum else "I can afford it, but it is not worth that price.")
        else:
            offer = self._opening_offer(item, c)
            if offer is None:
                self.state["deal"]["status"] = "declined"
                c["refused"].append(item_id)
                self.state["message"] = "I cannot afford a reasonable offer for that item. I will have to pass."
                return
            self.state["deal"]["offer"] = offer
            prefix = f"The label says {item['price']}, but " if item["mode"] == "fixed" else ""
            self.state["message"] = f"{prefix}I can offer {offer} gold for the {item['name'].lower()}."

    def difficulty(self, quote):
        positive_int(quote)
        c = self.customer()
        deal = self.state["deal"]
        if not deal or deal["status"] != "negotiating":
            raise ValueError("No active negotiation.")
        base=self.bargain_base_difficulty(self.item(deal["item_id"]),quote)
        mood_modifier = [2, 1, 0, -1, -2][c["mood"]]
        personality = {"patient": 0, "proud": 0, "impatient": 1}[c["personality"]]
        style = {"thrifty": 1, "practical": 0, "quality": -1}.get(c.get("buying_style"), 0)
        urgency = {"browsing": 1, "prepared": 0, "urgent": -1}.get(c.get("urgency"), 0)
        return max(3,base+mood_modifier+personality+style+urgency+deal["failures"]-self.observation_bonus(c))

    def patience_limit(self):
        c = self.customer()
        base = {"patient": 4, "proud": 3, "impatient": 3}[c["personality"]]
        return self.skill_rank("patience") + max(2, base + (1 if c["mood"] >= 3 else 0) - (1 if c.get("urgency") == "urgent" else 0))

    def negotiation_preview(self, price):
        """Exact D20 odds and the same failure consequence used by quote()."""
        if self.state.get("deal"):self.validate_quote_price(self.item(self.state["deal"]["item_id"]),price)
        dc = self.difficulty(price)
        c, deal = self.customer(), self.state["deal"]
        bonus = self.effective_eloquence()
        guaranteed = price <= deal["offer"]
        affordable = price <= c["budget"]
        chance = 100 if guaranteed else (sum(raw + bonus >= dc for raw in range(1, 21)) * 5 if affordable else 0)
        previous = deal["last_quote"]
        loses_mood = not affordable or previous is None or price >= previous or c["personality"] == "impatient"
        failed_mood = max(0, c["mood"] - int(loses_mood and deal["failures"] >= self.skill_rank("patience")))
        # Patience's happy-customer bonus disappears if failure takes them below Pleased.
        limit = self.patience_limit() - int(c["mood"] >= 3 and failed_mood < 3)
        walkaway = failed_mood == 0 or deal["failures"] + 1 >= limit
        return {"difficulty": dc, "bonus": bonus, "success_percent": chance,
                "failure_mood": MOODS[failed_mood], "walkaway_on_failure": walkaway,
                "remaining_patience": max(0, self.patience_limit() - deal["failures"]),
                "insight_bonus": self.observation_bonus(c)}

    def quote(self, price):
        price = positive_int(price)
        if self.state.get("deal"):self.validate_quote_price(self.item(self.state["deal"]["item_id"]),price)
        c = self.customer()
        deal = self.state["deal"]
        if not deal or deal["status"] != "negotiating":
            raise ValueError("No active negotiation.")
        if price > c["budget"]:
            c["mood"] = max(0, c["mood"] - int(deal["failures"] >= self.skill_rank("patience")))
            deal["failures"] += 1
            self.state["last_roll"] = None
            self.state["message"] = "That is more than I can afford."
            c["actions"].append(f"Asked {price} gold for {self.item(deal['item_id'])['name']}; the customer could not afford it.")
            self._check_walkaway()
            return
        if price <= deal["offer"]:
            deal.update(status="agreed", agreed=price, last_quote=price)
            self.state["last_roll"] = None
            self.state["message"] = f"Agreed. {price} gold."
            return
        terms=self.negotiation_preview(price)
        dc=terms["difficulty"]
        raw = self.rng.randint(1, 20)
        bonus = self.effective_eloquence()
        success=raw+bonus>=dc
        deal["round"] += 1
        self.state["last_roll"]={"raw":raw,"bonus":bonus,"attribute":"Eloquence","total":raw+bonus,
            "difficulty":dc,"success":success}
        previous = deal["last_quote"]
        deal["last_quote"] = price
        if success:
            deal.update(status="agreed", agreed=price)
            c["mood"] = min(4, c["mood"] + 1)
            self.state["message"] = f"You have a deal: {price} gold."
        else:
            deal["failures"] += 1
            # A genuine concession can preserve mood; repetition and price hikes cannot.
            if (previous is None or price >= previous or c["personality"] == "impatient") and deal["failures"] > self.skill_rank("patience"):
                c["mood"] = max(0, c["mood"] - 1)
            ceiling = min(c["budget"], c["willingness"][deal["item_id"]])
            concession_price=min(price,self.sale_cap(self.item(deal["item_id"]),"bargain"))
            deal["offer"] = max(deal["offer"], min(ceiling, deal["offer"] + math.ceil(max(1, (concession_price - deal["offer"]) // 4) * (1 + .1 * self.skill_rank("counteroffer")))))
            self.state["message"] = f"Not at that price. My offer is {deal['offer']} gold."
            self._check_walkaway()
        c["actions"].append(f"Negotiated {self.item(deal['item_id'])['name']} at {price} gold; round {deal['round']}: {'persuasion succeeded' if success else 'persuasion failed'}.")

    def _check_walkaway(self):
        c, deal = self.customer(), self.state["deal"]
        if c["mood"] == 0 or deal["failures"] >= self.patience_limit():
            deal["status"] = "declined"
            c["refused"].append(deal["item_id"])
            self.state["message"] += " Enough. I am not buying that item."

    def _sell(self, price):
        """Commit cash, shelf stock, customer ownership and experience as one sale."""
        c, deal = self.customer(), self.state["deal"]
        item = self.item(deal["item_id"])
        if item["quantity"] < 1 or price > c["budget"]:
            raise ValueError("This sale is no longer possible.")
        item["quantity"] -= 1
        if item["quantity"] == 0:
            self.state["shelves"] = [None if item_id == item["id"] else item_id
                                     for item_id in self.state["shelves"]]
        c["budget"] -= price
        self.state["gold"] += price
        self.state["daily"]["revenue"] += price
        self.state["daily"]["sales"] += 1
        c["purchases"].append({"item": item["name"], "price": price, "visit": c["visits"]})
        if item["id"]=="life_potion":c["life_potions"]=c.get("life_potions",0)+1
        if item.get("gear"):
            purchased=copy.deepcopy(item["gear"]);purchased["customer_paid"]=price
            c.setdefault("purchased_gear",[]).append(purchased)
        deal.update(status="sold", agreed=price)
        self.gain_xp(10)
        self.state["message"] = f"I will take the {item['name'].lower()} for {price} gold."

    def prepare_payment(self):
        """Reserve the agreed sale until the player picks up the customer's pouch."""
        deal = self.state["deal"]
        if not deal or deal["status"] not in ("negotiating", "agreed"):
            raise ValueError("There is no offer to confirm.")
        if deal.get("sale_allowed") is False:
            raise ValueError("The customer will not buy at the marked price.")
        price = deal["agreed"] if deal["status"] == "agreed" else deal["offer"]
        if self.item(deal["item_id"])["quantity"] < 1 or price > self.customer()["budget"]:
            raise ValueError("This sale is no longer possible.")
        deal.update(status="payment", agreed=price)
        self.state["message"] = "Here is your gold. A pleasure doing business."

    def drink_potion(self):
        """Consume stored medicine and restart only the drinker's attack timer."""
        stats=self.player_stats()
        if stats["hp"]<=0:raise ValueError("You must rest until tomorrow.")
        if stats["hp"]>=stats["max_hp"]:raise ValueError("Your health is full.")
        if self.state["warehouse"].get("life_potion",0)<1:raise ValueError("You have no life potions.")
        healed=min(40,stats["max_hp"]-stats["hp"])
        self.state["warehouse"]["life_potion"]-=1
        self.state["player_health"]=stats["hp"]+healed
        self.state["message"]="Life Potion restores "+str(healed)+" health."
        combat=self.state.get("combat")
        if combat and combat["status"]=="active":
            import time
            combat["player_next"]=time.time()+combat["player_interval"]
            combat["logs"].append(self.state["message"])

    def collect_payment(self):
        deal = self.state["deal"]
        if not deal or deal["status"] != "payment":
            raise ValueError("There is no coin pouch to collect.")
        self._sell(deal["agreed"])

    def accept(self):
        deal = self.state["deal"]
        if not deal or deal["status"] not in ("negotiating", "agreed"):
            raise ValueError("There is no offer to accept.")
        if deal.get("sale_allowed") is False:
            raise ValueError("The customer will not buy at the marked price.")
        self._sell(deal["agreed"] if deal["status"] == "agreed" else deal["offer"])

    def cancel(self):
        c, deal = self.customer(), self.state["deal"]
        if not deal or deal["status"] not in ("negotiating", "agreed"):
            raise ValueError("No active deal to end.")
        deal["status"] = "declined"
        c["refused"].append(deal["item_id"])
        c["actions"].append(f"Ended negotiations for {self.item(deal['item_id'])['name']} without a sale.")
        self.state["message"] = "Perhaps another time."

    def public(self):
        """Return a detached browser view; authoritative campaign data stays in Python."""
        result = {key: copy.deepcopy(self.state[key]) for key in ("gold", "player", "stock", "deal", "last_roll", "message", "total_visits", "daily", "day_summary", "loan", "warehouse", "shelves", "shelf_capacity", "caravan", "shelf_settings", "rent")}
        for item in result["stock"]:
            if item.get("category")=="consumable":
                item.update(wear=None,quality="common",affixes=[],price_caps={mode:self.sale_cap(item,mode) for mode in ["fixed","bargain"]},pricing_reference=self.sale_reference(item))
                continue
            gear=item.get("gear") or {"id":"stock:"+item["id"],"item_id":item["id"],"quality":"common","affixes":[],"identified":True}
            item["wear"]=self.gear_public(gear,gear.get("identified",True))
            item.update(quality=item["wear"]["quality"],affixes=item["wear"]["affixes"],price_caps={mode:self.sale_cap(item,mode) for mode in ["fixed","bargain"]},pricing_reference=self.sale_reference(item))
            item.pop("gear",None)
        if result["deal"] and self.state["current_id"]:
            result["deal"]["quote_cap"]=self.quote_cap(self.item(result["deal"]["item_id"]),self.customer())
        result["revision"] = self.state.get("revision",0)
        result["equipment"] = self.equipment_public()
        result["combat"] = self.combat_public()
        result["caravan"]["gear_stock"] = [dict(self.gear_public(g),price=self.merchant_price(g["price"])) for g in self.state["caravan"]["gear_stock"]]
        result["ending"] = copy.deepcopy(self.state.get("ending"))
        result["final_boss"] = self.finale_public()
        result["creation"] = dict(copy.deepcopy(self.state["creation"]),base={key:self.state["player"].get(key,2) for key in ("strength","dexterity","wisdom","eloquence","luck")})
        result["skills"] = self.skill_tree()
        result["player"]["eloquence"] = self.effective_eloquence()
        for listing in result["caravan"]["stock"]:
            listing["price"] = self.merchant_price(listing["price"])
        for item in result["stock"]:
            item["cost"] = item.get("acquisition_cost", item["cost"])
        result["has_progress"] = self.has_progress()
        result["intro_seen"] = self.state["intro_seen"]
        result["commission_board"] = self.commission_board()
        result["units_per_shelf"] = UNITS_PER_SHELF
        result["calendar"] = calendar_date(self.state["day"])
        result["calendar"]["days_until_rent"] = 7 - (self.state["day"] - 1) % 7
        result["calendar"]["days_until_payment"] = DAYS_PER_MONTH - (self.state["day"] - 1) % DAYS_PER_MONTH
        result["loan"]["paid_off"] = self.state["loan"]["balance"] == 0 and self.state["loan"]["interest_arrears"] == 0
        result["customer"] = None
        if self.state["current_id"]:
            c = self.customer()
            result["customer"] = {key: copy.deepcopy(c[key]) for key in ("id", "name", "race", "sex", "portrait", "equipment", "profession", "armour", "accessories", "visits", "purchases", "actions", "known", "wants", "destination")}
            result["customer"]["mood"] = MOODS[c["mood"]]
            result["customer"]["wanted"] = bool(c.get("wanted"))
            result["customer"]["final_boss"] = bool(c.get("final_boss"))
            result["customer"]["defeated"] = bool(c.get("defeated"))
            result["customer"]["stats"] = self.customer_stats(c)
            result["customer"]["life_potions"]=c.get("life_potions",0)
            result["customer"]["belongings_seen"] = c.get("belongings_seen",False)
            result["customer"]["can_steal"] = self.can_attempt_theft(c)
            result["customer"]["can_buy_belongings"] = self.can_buy_belongings(c)
            result["customer"]["trade_blocked"] = c.get("trade_blocked_visit") == c["visits"]
            result["customer"]["belongings"] = [dict(self.gear_public(g,False),buy_price=self.belongings_price(c,g),steal_chance=self.theft_chance(c,g),steal_difficulty=self.theft_difficulty(c,g)) for g in c.get("belongings",[])+c.get("purchased_gear",[])] if c.get("belongings_seen") else []
        return result

    def action(self, action, payload):
        """Validate an action, save it atomically, and roll back on any failure."""
        handlers = {
            "save": lambda: None,
            "drink_potion": self.drink_potion,
            "allocate_attributes": lambda: self.allocate_attributes(payload.get("allocation")),
            "begin_final_battle": self.begin_final_battle, "acknowledge_boss": self.acknowledge_boss,
            "attack_wanted": self.attack_wanted, "collect_combat_rewards": self.collect_combat_rewards,
            "repay_early": lambda: self.repay_early(payload.get("amount")),
            "inspect_belongings": self.inspect_belongings,
            "identify_gear": lambda: self.identify_gear(payload.get("gear_id")),
            "steal_gear": lambda: self.steal_gear(payload.get("gear_id")),
            "equip_gear": lambda: self.equip_gear(payload.get("gear_id"),payload.get("item_id"),payload.get("slot")),
            "unequip_gear": lambda: self.unequip_gear(payload.get("slot")),
            "stock_gear": lambda: self.stock_gear(payload.get("gear_id")),
            "buy_gear": lambda: self.buy_gear(payload.get("gear_id")),
            "buy_belonging": lambda: self.buy_belonging(payload.get("gear_id")),
            "combat_tick": self.combat_tick, "flee_combat": self.flee_combat,
            "fight": self.choose_fight, "beg_mercy": self.beg_mercy,
            "learn_skill": lambda: self.learn_skill(payload.get("skill")),
            "new_game": self.new_game, "finish_intro": self.finish_intro,
            "arrive": self.arrive, "leave": self.leave,
            "dispatch_commission": lambda: self.dispatch_commission(payload.get("customer_id"), payload.get("region_id"), payload.get("gear"), payload.get("use_relic", False), payload.get("deep", False), payload.get("weapon"), payload.get("armour")),
            "claim_commission": lambda: self.claim_commission(payload.get("mission_id")),
            "sell_relic": lambda: self.sell_relic(payload.get("region_id")),
            "unlock_deep_route": lambda: self.unlock_deep_route(payload.get("region_id")),
            "next_day": self.next_day,
            "skip_day": self.skip_day, "rest": self.rest_after_defeat,
            "finish_market": self.finish_market, "visit_caravan": self.visit_caravan,
            "merchant_buy": lambda: self.merchant_buy(payload.get("item_id"), payload.get("quantity")),
            "place_stock": lambda: self.place_stock(payload.get("slot"), payload.get("item_id"), payload.get("quantity"), payload.get("mode"), payload.get("price")),
            "restock": lambda: self.restock(payload.get("slot"), payload.get("quantity")),
            "return_stock": lambda: self.return_stock(payload.get("slot")),
            "inspect": lambda: self.inspect(payload.get("clue")),
            "set_price": lambda: self.set_price(payload.get("item_id"), payload.get("price")),
            "begin": lambda: self.begin(payload.get("item_id")),
            "quote": lambda: self.quote(payload.get("price")),
            "accept": self.accept, "cancel": self.cancel,
            "prepare_payment": self.prepare_payment, "collect_payment": self.collect_payment,
        }
        if action not in handlers:
            raise ValueError("Unknown action.")
        if not self.state["creation"]["completed"] and action not in ("allocate_attributes","new_game","save"):
            raise ValueError("Assign your starting attributes first.")
        if self.state.get("ending") and action not in ("save","new_game"):
            raise ValueError("Your debt is repaid. This story is complete.")
        if self.state.get("combat") and self.state["combat"]["status"] == "active" and action not in ("combat_tick","flee_combat","drink_potion"):
            raise ValueError("Finish the fight first.")
        if self.state.get("combat") and self.state["combat"]["status"] in ("threatened","ready") and action not in ("fight","beg_mercy","combat_tick"):
            raise ValueError("Face the confrontation first.")
        if self.state["player_health"] <= 0 and action != "rest":
            raise ValueError("You must rest until tomorrow.")
        rewards=(self.state.get("combat") or {}).get("rewards",{})
        if not rewards.get("claimed",True) and action in ("leave","arrive","skip_day","next_day","begin_final_battle"):
            raise ValueError("Open the treasure chest first.")
        before = copy.deepcopy(self.state)
        try:
            handlers[action]()
            self._upgrade_wear_requirements()
            self.normalize_sale_prices()
            self.check_ending()
            self.state["revision"] = self.state.get("revision",0)+1
            self.save()
        except Exception:
            self.state = before
            raise
        return self.public()
