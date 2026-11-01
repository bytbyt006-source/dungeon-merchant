"""Timed adventurer commissions, reusable relics and permanent route progression."""
import copy
import uuid
from dungeon_loot import SPECIAL_DROP_PERCENT, DUNGEON_GEAR, reward_view, make_dungeon_gear


RELIC_DROP_PERCENT = 1

REGIONS = [
    {"id": "mine", "name": "Abandoned Mine", "days": 2, "fee": 35, "difficulty": 11,
     "roles": ["greatsword", "hammer_shield"], "loot": ["greatsword", "chainmail", "hammer"],
     "relic": "Miner's Seal", "sell_price": 65, "next": "marsh",
     "description": "Unstable tunnels and heavy stone doors. Strong, armoured adventurers excel."},
    {"id": "marsh", "name": "Whispering Marsh", "days": 3, "fee": 50, "difficulty": 13,
     "roles": ["bow", "staff"], "loot": ["bow", "staff", "leather_armour", "mage_robes"],
     "relic": "Marsh Compass", "sell_price": 95, "next": "crypt",
     "description": "Hidden paths and wandering lights. Rangers and mages find safer routes."},
    {"id": "crypt", "name": "Sunken Crypt", "days": 4, "fee": 70, "difficulty": 15,
     "roles": ["prayer_book", "hammer_shield"], "loot": ["book", "shield", "cleric_robes", "plate_armour"],
     "relic": "Dawn Reliquary", "sell_price": 135, "next": None,
     "description": "Sealed tombs and restless dead. Clerics and guardians are well suited."},
]


class CommissionMixin:
    def _upgrade_commissions(self):
        self.state.setdefault("commissions", [])
        self.state.setdefault("relics", {r["id"]: 0 for r in REGIONS})
        self.state.setdefault("routes", ["mine"])
        self.state.setdefault("deep_routes", [])

    def _region(self, region_id):
        region = next((r for r in REGIONS if r["id"] == region_id), None)
        if region is None:
            raise ValueError("Unknown adventure location.")
        return region

    def _adventurer_busy(self, customer_id):
        return any(m["customer_id"] == customer_id and m["status"] in ("away", "returned")
                   for m in self.state["commissions"])

    def _adventure_record(self, customer_id):
        completed = [m for m in self.state["commissions"]
                     if m["customer_id"] == customer_id and m["status"] in ("returned", "claimed")]
        return len(completed), sum(m["success"] for m in completed)

    def _adventure_skill(self, customer_id):
        # A persistent identity trait, unrelated to the art chosen for the customer.
        return 1 + sum(map(ord, customer_id)) % 3

    def _loan_slot(self, item_id):
        if self.item(item_id).get("category") == "accessory":
            raise ValueError("Lend a weapon or armour for this expedition.")
        return "armour" if item_id == "shield" or self.item(item_id).get("category") == "armour" else "weapon"

    def _commission_loadout(self, customer, gear=None, weapon=None, armour=None):
        # Continue accepting the old one-item API and saves during the upgrade.
        if gear is not None:
            if weapon is not None or armour is not None:
                raise ValueError("Choose separate slots or a legacy single loan, not both.")
            if not isinstance(gear, str):
                raise ValueError("Invalid loan equipment.")
            if self._loan_slot(gear) == "armour":
                armour = gear
            else:
                weapon = gear
        for slot, item_id in (("weapon", weapon), ("armour", armour)):
            if item_id is None:
                continue
            if item_id=="life_potion":raise ValueError("Choose a weapon or armour.")
            if not isinstance(item_id, str) or item_id not in self.professions[customer["weapon_type"]]["preferred_items"]:
                raise ValueError("Choose equipment suited to this adventurer's profession.")
            if self._loan_slot(item_id) != slot:
                raise ValueError("Place the weapon and armour in their matching slots.")
            if self.state["warehouse"].get(item_id, 0) < 1:
                raise ValueError("Loan equipment must be in the warehouse.")
        return weapon, armour

    def _commission_loans(self, mission):
        if "loaned_equipment" in mission:
            return mission["loaned_equipment"]
        gear = mission.get("gear")
        return ([{"item_id": gear, "slot": self._loan_slot(gear), "returned": mission.get("gear_returned", False)}]
                if gear else [])

    def commission_preview(self, customer_id, region_id, gear=None, use_relic=False, deep=False, weapon=None, armour=None):
        """Calculate the same fees, bonuses and odds used for actual dispatch."""
        region = self._region(region_id)
        if not isinstance(use_relic, bool) or not isinstance(deep, bool):
            raise ValueError("Invalid expedition options.")
        if region_id not in self.state["routes"]:
            raise ValueError("Complete the previous route to discover this location.")
        if deep and region_id not in self.state["deep_routes"]:
            raise ValueError("Unlock the deeper route with two relics first.")
        c = self.state["customers"].get(customer_id)
        if c is None:
            raise ValueError("Choose an adventurer you have met in the shop.")
        if c.get("defeated"):
            raise ValueError("This adventurer is too badly hurt to travel.")
        if customer_id == self.state["current_id"]:
            raise ValueError("See this customer out before hiring them.")
        if self._adventurer_busy(customer_id):
            raise ValueError("This adventurer is away or waiting for their report to be collected.")
        skill = self._adventure_skill(customer_id)
        fit = 2 if c["weapon_type"] in region["roles"] else 0
        _, wins = self._adventure_record(customer_id)
        experience = min(2, wins)
        weapon, armour = self._commission_loadout(c, gear, weapon, armour)
        weapon_bonus, armour_bonus = (2 if weapon else 0), (2 if armour else 0)
        gear_bonus = weapon_bonus + armour_bonus
        if use_relic and self.state["relics"][region_id] < 1:
            raise ValueError("You do not have this location's relic to lend.")
        relic_bonus = 3 if use_relic else 0
        carried_bonus = sum(self.gear_modifiers(g).get("expedition",0) for g in c.get("belongings",[]))
        bonus = skill + fit + experience + gear_bonus + relic_bonus + self.skill_rank("expedition") + self.player_stats()["expedition"] + carried_bonus
        dc = region["difficulty"] + (4 if deep else 0)
        fee = (region["fee"] * (2 if deep else 1) * (100 - 10 * self.skill_rank("contracts")) + 99) // 100
        return {**self.loan_loss_rates(), "talent_bonus": self.skill_rank("expedition"), "skill": skill, "region_bonus": fit, "experience_bonus": experience,
                "weapon_bonus": weapon_bonus, "armour_bonus": armour_bonus, "weapon": weapon, "armour": armour,
                "gear_bonus": gear_bonus, "relic_bonus": relic_bonus, "bonus": bonus,
                "difficulty": dc, "success_percent": sum(raw + bonus >= dc for raw in range(1, 21)) * 5,
                "fee": fee, "days": max(1, region["days"] + int(deep) - self.skill_rank("pathfinder")), "can_afford": self.state["gold"] >= fee,
                "drop_slots": 2 if deep else 1, "relic_drop_percent": RELIC_DROP_PERCENT}

    def dispatch_commission(self, customer_id, region_id, gear=None, use_relic=False, deep=False, weapon=None, armour=None):
        terms = self.commission_preview(customer_id, region_id, gear, use_relic, deep, weapon, armour)
        if not terms["can_afford"]:
            raise ValueError("Not enough gold for the commission fee.")
        if len([m for m in self.state["commissions"] if m["status"] == "away"]) >= 3:
            raise ValueError("You can fund at most three expeditions at once.")
        if self.state["daily"]["closed"]:
            raise ValueError("Start the next day before commissioning an expedition.")
        self.state["gold"] -= terms["fee"]
        weapon, armour = terms["weapon"], terms["armour"]
        loans = [{"item_id": item_id, "slot": slot} for slot, item_id in (("weapon", weapon), ("armour", armour)) if item_id]
        for loan in loans:
            self.state["warehouse"][loan["item_id"]] -= 1
        if use_relic:
            self.state["relics"][region_id] -= 1
        mission = {"id": uuid.uuid4().hex, "customer_id": customer_id, "region_id": region_id,
                   "deep": deep, "gear": gear or weapon or armour, "weapon": weapon, "armour": armour,
                   "loaned_equipment": loans, "use_relic": use_relic, "status": "away",
                   "departed": self.state["day"], "due_day": self.state["day"] + terms["days"],
                   **self.loan_loss_rates(), "duplicate_chance": self.duplicate_chance(),
                   "bonus": terms["bonus"], "difficulty": terms["difficulty"], "fee": terms["fee"]}
        self.state["commissions"].append(mission)
        c, region = self.state["customers"][customer_id], self._region(region_id)
        c["actions"].append(f"Commissioned for {region['name']}{' depths' if deep else ''}; fee {terms['fee']} gold; due on day {mission['due_day']}.")
        self.state["message"] = f"{c['name']} departs for {region['name']}."

    def _roll_commission_loot(self, region, slots):
        """Each independent success-only slot is 1% relic, otherwise equipment."""
        equipment, relics, uniques = {}, 0, []
        for _ in range(slots):
            roll=self.rng.randrange(100)
            if roll < RELIC_DROP_PERCENT:
                relics += 1
            elif roll < RELIC_DROP_PERCENT+SPECIAL_DROP_PERCENT:
                keys=[key for key,item in DUNGEON_GEAR.items() if item["region"]==region["id"]]
                uniques.append(make_dungeon_gear(self.rng.choice(keys)))
            else:
                item_id = self.rng.choice(region["loot"])
                equipment[item_id] = equipment.get(item_id, 0) + 1
        return {"equipment_loot": [{"item_id": item_id, "quantity": quantity}
                                    for item_id, quantity in equipment.items()],
                "relic_quantity": relics, "unique_loot":uniques}

    def _equipment_rewards(self, mission):
        if "equipment_loot" in mission:
            return mission["equipment_loot"]
        # Previously rolled reports keep their promised loot after upgrading.
        return ([{"item_id": mission["loot_item"], "quantity": mission["loot_quantity"]}]
                if mission.get("loot_item") and mission.get("loot_quantity", 0) else [])

    def _resolve_commissions(self):
        """Resolve each due expedition once and retain recoverable loans separately from loot."""
        for m in self.state["commissions"]:
            if m["status"] != "away" or m["due_day"] > self.state["day"]:
                continue
            region = self._region(m["region_id"])
            raw = self.rng.randint(1, 20)
            success = raw + m["bonus"] >= m["difficulty"]
            rewards = self._roll_commission_loot(region, 2 if m["deep"] else 1) if success else {"equipment_loot": [], "relic_quantity": 0}
            chance = m.get("duplicate_chance", 0)
            if chance:
                for reward in rewards["equipment_loot"]:
                    reward["quantity"] += sum(self.rng.randrange(100) < chance for _ in range(reward["quantity"]))
                rewards["relic_quantity"] += sum(self.rng.randrange(100) < chance for _ in range(rewards["relic_quantity"]))
                for gear in list(rewards.get("unique_loot",[])):
                    if self.rng.randrange(100)<chance:
                        duplicate=copy.deepcopy(gear);duplicate["id"]=uuid.uuid4().hex
                        rewards["unique_loot"].append(duplicate)
            m.update(rewards)
            loans = copy.deepcopy(self._commission_loans(m))
            for loan in loans:
                loan["returned"] = success or self.rng.random() >= m.get("gear_loss_percent", 35) / 100
            m["loaned_equipment"] = loans
            m.update(status="returned", roll=raw, success=success,
                     loot_item=rewards["equipment_loot"][0]["item_id"] if rewards["equipment_loot"] else None,
                     loot_quantity=sum(item["quantity"] for item in rewards["equipment_loot"])+len(rewards.get("unique_loot",[])),
                     gear_returned=next((loan["returned"] for loan in loans if loan["item_id"] == m.get("gear")), False),
                     relic_returned=m["use_relic"] and (success or self.rng.random() >= m.get("relic_loss_percent", 20) / 100))
            c = self.state["customers"][m["customer_id"]]
            outcome = "returned with treasure" if success else "returned empty-handed"
            c["actions"].append(f"Day {self.state['day']}: {region['name']} — {outcome}.")

    def claim_commission(self, mission_id):
        """Transfer a returned report's rewards and surviving loans exactly once."""
        m = next((m for m in self.state["commissions"] if m["id"] == mission_id), None)
        if m is None or m["status"] != "returned":
            raise ValueError("There is no returned expedition to collect.")
        for loan in self._commission_loans(m):
            if loan.get("returned"):
                self.state["warehouse"][loan["item_id"]] += 1
        if m["relic_returned"]:
            self.state["relics"][m["region_id"]] += 1
        if m["success"]:
            self.state["equipment_bag"].extend(copy.deepcopy(m.get("unique_loot",[])))
            for reward in self._equipment_rewards(m):
                self.state["warehouse"][reward["item_id"]] += reward["quantity"]
            self.state["relics"][m["region_id"]] += m["relic_quantity"]
            self.state["customers"][m["customer_id"]]["commission_return_visit"] = True
            next_route = self._region(m["region_id"])["next"]
            if next_route and next_route not in self.state["routes"]:
                self.state["routes"].append(next_route)
        m["status"] = "claimed"
        self.gain_xp(35 if m["success"] else 5)
        self.state["customers"][m["customer_id"]]["actions"].append("Received the expedition haul.")
        self.state["message"] = "The expedition haul is in your warehouse."

    def sell_relic(self, region_id):
        region = self._region(region_id)
        if self.state["relics"][region_id] < 1:
            raise ValueError("You do not have a relic to sell.")
        if self.state["daily"]["closed"]:
            raise ValueError("Start the next day before selling relics.")
        self.state["relics"][region_id] -= 1
        self.state["gold"] += region["sell_price"]
        self.state["daily"]["revenue"] += region["sell_price"]
        self.state["daily"]["sales"] += 1
        self.state["message"] = f"Sold {region['relic']} to a collector for {region['sell_price']} gold."

    def unlock_deep_route(self, region_id):
        region = self._region(region_id)
        if region_id in self.state["deep_routes"]:
            raise ValueError("This deeper route is already unlocked.")
        if self.state["relics"][region_id] < 2:
            raise ValueError("Keep two relics from this location to unlock its depths.")
        self.state["relics"][region_id] -= 2
        self.state["deep_routes"].append(region_id)
        self.state["message"] = f"The deeper route through {region['name']} is permanently unlocked."

    def commission_board(self):
        regions = copy.deepcopy(REGIONS)
        for r in regions:
            r["unique_rewards"]=[reward_view(key) for key,item in DUNGEON_GEAR.items() if item["region"]==r["id"]]
            r.update(unlocked=r["id"] in self.state["routes"], deep_unlocked=r["id"] in self.state["deep_routes"],
                     owned=self.state["relics"][r["id"]], relic_drop_percent=RELIC_DROP_PERCENT,
                     equipment_drop_percent=100-RELIC_DROP_PERCENT)
        roster = []
        for c in self.state["customers"].values():
            if c.get("final_boss"):continue
            attempts, wins = self._adventure_record(c["id"])
            roster.append({"id": c["id"], "name": c["name"], "portrait": c["portrait"],
                           "profession": c["profession"], "skill": self._adventure_skill(c["id"]),
                           "attempts": attempts, "wins": wins,
                           "available": c["id"] != self.state["current_id"] and not c.get("defeated") and not self._adventurer_busy(c["id"]),
                           "gear": [item_id for item_id in self.professions[c["weapon_type"]]["preferred_items"] if self.item(item_id).get("category") not in ("accessory","consumable")]})
        missions = []
        visible = [m for m in self.state["commissions"] if m["status"] != "claimed"]
        visible += [m for m in self.state["commissions"] if m["status"] == "claimed"][-5:]
        for mission in visible:
            m = copy.deepcopy(mission)
            m["name"] = self.state["customers"][m["customer_id"]]["name"]
            m["loaned_equipment"] = copy.deepcopy(self._commission_loans(m))
            if m["status"] != "away":
                m["equipment_loot"] = copy.deepcopy(self._equipment_rewards(m))
                counts = {}
                for loan in self._commission_loans(m):
                    if loan.get("returned"):
                        counts[loan["item_id"]] = counts.get(loan["item_id"], 0) + 1
                for reward in (self._equipment_rewards(m) if m["success"] else []):
                    counts[reward["item_id"]] = counts.get(reward["item_id"], 0) + reward["quantity"]
                m["collectible_items"] = [{"key": item_id, "name": self.item(item_id)["name"], "quantity": count,
                                           "src": "assets/items/" + item_id + ".png"} for item_id, count in counts.items()]
                if m["success"]:
                    for gear in m.get("unique_loot",[]):
                        view=self.gear_public(gear)
                        m["collectible_items"].append({"key":"gear_"+gear["id"],"name":view["name"],"quantity":1,"src":view["src"],"quality":view["quality"]})
                relic_count = (m.get("relic_quantity", 0) if m["success"] else 0) + int(bool(m.get("relic_returned")))
                if relic_count:
                    m["collectible_items"].append({"key": "relic", "name": self._region(m["region_id"])["relic"],
                                                   "quantity": relic_count, "src": "assets/relics/" + m["region_id"] + ".png"})
            missions.append(m)
        return {**self.loan_loss_rates(), "regions": regions, "roster": roster, "missions": missions,
                "ready": sum(m["status"] == "returned" for m in missions)}
