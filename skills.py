"""Persistent merchant talents and experience rewards."""
import copy
import math

TALENTS = [
    {"id":"weapon_mastery","name":"Seasoned Fighter","group":"Combat","icon":"gear","effects":["Attack +3","Attack +6","Attack +9"],"nodes":["Firm Grip","Battle Drills","Master at Arms"]},
    {"id":"iron_guard","name":"Iron Guard","group":"Combat","icon":"shield","effects":["Defense +3","Defense +6","Defense +9"],"nodes":["Brace Yourself","Hold the Line","Living Bulwark"]},
    {"id":"footwork","name":"Evasive Footwork","group":"Combat","icon":"hand","effects":["Dodge +2%","Dodge +4%","Dodge +6%"],"nodes":["Sidestep","Read the Strike","Untouchable"]},
    {"id":"battle_tempo","name":"Battle Rhythm","group":"Combat","icon":"clock","requires":"weapon_mastery","effects":["Attack speed +5%","Attack speed +10%","Attack speed +15%"],"nodes":["Find Your Rhythm","Relentless Blows","Steel Tempest"]},
    {"id":"critical_strike","name":"Exploit Weakness","group":"Combat","icon":"gear","requires":"weapon_mastery","effects":["5% chance of 150% damage","10% chance of 150% damage","15% chance of 150% damage"],"nodes":["Find an Opening","Precise Strike","Killing Edge"]},
    {"id":"second_wind","name":"Second Wind","group":"Combat","icon":"shield","requires":"iron_guard","effects":["Victory restores 10% health","Victory restores 20% health","Victory restores 30% health"],"nodes":["Catch Your Breath","Battle-Hardened","Still Standing"]},
    {"id":"strength_training","name":"Iron Constitution","group":"Character","icon":"gear","effects":["Strength +3","Strength +6","Strength +9"],"nodes":["Heavy Lifting","Iron Muscles","Titan's Might"]},
    {"id":"agility_training","name":"Light on Your Feet","group":"Character","icon":"hand","effects":["Dexterity +3","Dexterity +6","Dexterity +9"],"nodes":["Steady Hands","Cat's Grace","Shadowstep"]},
    {"id":"scholar","name":"A Scholar's Mind","group":"Character","icon":"scroll","effects":["Wisdom +3","Wisdom +6","Wisdom +9"],"nodes":["Old Books","Arcane Study","The Unseen Truth"]},
    {"id": "eloquence", "name": "Silver Tongue", "group": "Trading", "icon": "d20", "effects": ["Persuasion +1", "Persuasion +2", "Persuasion +3"], "nodes": ["A Gentle Word", "Honeyed Bargain", "Voice of Gold"]},
    {"id": "patience", "name": "Patient Company", "group": "Trading", "icon": "clock", "effects": ["1 extra refusal", "2 extra refusals", "3 extra refusals"], "nodes": ["Warm Welcome", "A Seat by the Fire", "Old Friends"]},
    {"id": "appraisal", "name": "Merchant's Eye", "group": "Trading", "icon": "scroll", "effects": ["Observation +1", "Observation +2", "Observation +3"], "nodes": ["Sharp Eyes", "Read the Room", "Nothing Unseen"]},
    {"id": "counteroffer", "name": "Give and Take", "group": "Trading", "icon": "hand", "requires": "eloquence", "effects": ["Counter-offer gains +10%", "Counter-offer gains +20%", "Counter-offer gains +30%"], "nodes": ["Find Common Ground", "Meet Me Halfway", "One Last Offer"]},
    {"id": "supplier", "name": "Merchant Connections", "group": "Commerce", "icon": "coin", "effects": ["Buying prices −5%", "Buying prices −10%", "Buying prices −15%"], "nodes": ["Familiar Face", "Trusted Partner", "Guild Privilege"]},
    {"id": "contracts", "name": "Well-Written Contracts", "group": "Commerce", "icon": "gear", "requires": "supplier", "effects": ["Commission fees −10%", "Commission fees −20%", "Commission fees −30%"], "nodes": ["Fair Terms", "Shared Interests", "A Merchant's Seal"]},
    {"id": "expedition", "name": "Careful Preparation", "group": "Expeditions", "icon": "shield", "effects": ["Expedition rolls +1", "Expedition rolls +2", "Expedition rolls +3"], "nodes": ["Check the Supplies", "Plan Every Step", "Leave Nothing to Chance"]},
    {"id": "pathfinder", "name": "Hidden Roads", "group": "Expeditions", "icon": "map", "requires": "expedition", "effects": ["Travel −1 day", "Travel −2 days", "Travel −3 days"], "nodes": ["Local Guides", "Forgotten Paths", "Roads Without Names"]},
    {"id": "salvage", "name": "Bring Them Home", "group": "Expeditions", "icon": "warehouse", "requires": "expedition", "effects": ["Gear loss 25% · relic 15%", "Gear loss 15% · relic 10%", "Gear loss 5% · relic 5%"], "nodes": ["Pack with Care", "Recovery Plans", "No Gear Left Behind"]},
    {"id": "fortune", "name": "Bountiful Expeditions", "group": "Expeditions", "icon": "chest", "effects": ["20% chance of extra loot", "35% chance of extra loot", "50% chance of extra loot"], "nodes": ["A Lucky Find", "A Second Look", "Fortune's Favourite"]},
]


class SkillMixin:
    def _upgrade_skills(self):
        if "skills" not in self.state:
            # Credit completed trades in existing campaigns once, then persist XP.
            xp = sum(len(c.get("purchases", [])) for c in self.state["customers"].values()) * 10
            xp += sum(35 if m.get("success") else 5 for m in self.state["commissions"] if m["status"] == "claimed")
            self.state["skills"] = {"xp": xp, "points": 1 + xp // 100, "ranks": {t["id"]: 0 for t in TALENTS}}

        for talent in TALENTS:
            self.state["skills"]["ranks"].setdefault(talent["id"], 0)

    def skill_rank(self, name):
        """Combine learned and equipment-granted ranks, capped at three."""
        return min(3,self.state["skills"]["ranks"].get(name, 0) + self.equipped_modifier("talent_"+name))

    def gain_xp(self, amount):
        skills = self.state["skills"]
        before = skills["xp"] // 100
        skills["xp"] += amount
        skills["points"] += skills["xp"] // 100 - before

    def learn_skill(self, name):
        """Spend a talent point after validating prerequisites and the maximum rank."""
        if name not in {t["id"] for t in TALENTS}:
            raise ValueError("Unknown talent.")
        talent = next(t for t in TALENTS if t["id"] == name)
        if talent.get("requires") and self.skill_rank(talent["requires"]) < 1:
            required = next(t["name"] for t in TALENTS if t["id"] == talent["requires"])
            raise ValueError("Requires " + required + " I.")
        skills = self.state["skills"]
        if skills["points"] < 1 or skills["ranks"][name] >= 3:
            raise ValueError("No talent point available.")
        old_max=self.player_stats()["max_hp"]
        skills["ranks"][name] += 1
        skills["points"] -= 1
        self.shift_max_health(old_max)

    def effective_eloquence(self):
        return self.state["player"]["eloquence"] + self.skill_rank("eloquence") + self.equipped_modifier("eloquence")

    def merchant_price(self, base):
        return max(1, math.ceil(base * (100 - 5 * self.skill_rank("supplier")) / 100))

    def duplicate_chance(self):
        return [0, 20, 35, 50][self.skill_rank("fortune")]

    def observation_bonus(self, customer):
        observed = len(set(customer.get("observed", [])) & {"equipment", "accessories", "manner"})
        return min(2, observed) + (self.skill_rank("appraisal") if observed else 0)

    def loan_loss_rates(self):
        rank = self.skill_rank("salvage")
        return {"gear_loss_percent": [35, 25, 15, 5][rank], "relic_loss_percent": [20, 15, 10, 5][rank]}

    def skill_tree(self):
        result = copy.deepcopy(self.state["skills"])
        result["effective_ranks"] = {t["id"]:self.skill_rank(t["id"]) for t in TALENTS}
        result["groups"] = ["Trading", "Commerce", "Expeditions", "Character", "Combat"]
        result.update(level=1 + result["xp"] // 100, progress=result["xp"] % 100, talents=copy.deepcopy(TALENTS))
        return result
