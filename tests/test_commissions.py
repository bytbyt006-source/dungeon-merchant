"""Commission resource accounting, time progression, persistence and unlocks."""
import copy
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shop_fixture import stock_shop
from game import Game


class CommissionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.save = Path(self.folder.name) / "save.json"
        self.g = Game(ROOT / "assets", self.save, random.Random(7))
        stock_shop(self.g)
        self.g.finish_market()
        portrait = next(p for p in self.g.portraits if p["weapon"] == "hammer_shield")
        self.c = self.g._new_customer([portrait])
        self.c["visits"] = 1

    def dispatch(self, **extra):
        self.g.action("dispatch_commission", dict(customer_id=self.c["id"], region_id="mine", **extra))
        return self.g.state["commissions"][-1]

    def advance(self, days):
        for _ in range(days):
            self.g.action("skip_day", {})
            self.g.action("next_day", {})

    def test_success_returns_property_loot_and_discovers_next_region(self):
        before = self.g.state["warehouse"]["hammer"]
        m = self.dispatch(gear="hammer")
        self.assertEqual(self.g.state["gold"], 965)
        self.assertEqual(self.g.state["warehouse"]["hammer"], before - 1)
        self.advance(1)
        self.assertEqual(m["status"], "away")
        with patch.object(self.g.rng, "randint", return_value=20), patch.object(self.g.rng, "randrange", return_value=1):
            self.advance(1)
        self.assertEqual(m["status"], "returned")
        before_claim = copy.deepcopy(self.g.state["warehouse"])
        self.g.action("claim_commission", {"mission_id": m["id"]})
        self.assertEqual(self.g.state["warehouse"]["hammer"], before_claim["hammer"] + 1 + int(m["loot_item"] == "hammer"))
        self.assertEqual(self.g.state["relics"]["mine"], 0)
        self.assertIn("marsh", self.g.state["routes"])
        self.assertTrue(any("returned with treasure" in entry for entry in self.c["actions"]))
        saved = copy.deepcopy(self.g.state)
        with self.assertRaises(ValueError):
            self.g.action("claim_commission", {"mission_id": m["id"]})
        self.assertEqual(self.g.state, saved)

    def test_failure_can_lose_both_loans_without_refunding_fee(self):
        self.g.state["relics"]["mine"] = 1
        self.c["weapon_type"] = "staff"
        stored = self.g.state["warehouse"]["staff"]
        with patch.object(self.g, "_adventure_skill", return_value=1):
            m = self.dispatch(gear="staff", use_relic=True)
        with patch.object(self.g.rng, "randint", return_value=1), patch.object(self.g.rng, "random", return_value=0):
            self.advance(2)
        self.assertFalse(m["success"])
        self.g.action("claim_commission", {"mission_id": m["id"]})
        self.assertEqual(self.g.state["warehouse"]["staff"], stored - 1)
        self.assertEqual(self.g.state["relics"]["mine"], 0)
        self.assertEqual(self.g.state["gold"], 965)
        self.assertNotIn("marsh", self.g.state["routes"])

    def test_weapon_and_armour_can_be_loaned_together_and_both_return(self):
        self.c["weapon_type"] = "staff"
        before = {item: self.g.state["warehouse"][item] for item in ("staff", "mage_robes")}
        single = self.g.commission_preview(self.c["id"], "mine", weapon="staff")
        both = self.g.commission_preview(self.c["id"], "mine", weapon="staff", armour="mage_robes")
        self.assertEqual(both["bonus"], single["bonus"] + 2)
        self.assertEqual((both["weapon_bonus"], both["armour_bonus"], both["gear_bonus"]), (2, 2, 4))
        m = self.dispatch(weapon="staff", armour="mage_robes")
        for item in before:
            self.assertEqual(self.g.state["warehouse"][item], before[item] - 1)
        with patch.object(self.g.rng, "randint", return_value=20), patch.object(self.g.rng, "randrange", return_value=1):
            self.advance(2)
        self.assertTrue(all(loan["returned"] for loan in m["loaned_equipment"]))
        self.g.action("claim_commission", {"mission_id": m["id"]})
        for item in before:
            self.assertEqual(self.g.state["warehouse"][item], before[item])

    def test_weapon_and_armour_loss_are_independent_on_failure(self):
        self.c["weapon_type"] = "staff"
        before = {item: self.g.state["warehouse"][item] for item in ("staff", "mage_robes")}
        with patch.object(self.g, "_adventure_skill", return_value=1):
            m = self.dispatch(weapon="staff", armour="mage_robes")
        with patch.object(self.g.rng, "randint", return_value=1), patch.object(self.g.rng, "random", side_effect=[0, .99]):
            self.advance(2)
        self.assertFalse(m["success"])
        self.assertEqual([loan["returned"] for loan in m["loaned_equipment"]], [False, True])
        self.g.action("claim_commission", {"mission_id": m["id"]})
        self.assertEqual(self.g.state["warehouse"]["staff"], before["staff"] - 1)
        self.assertEqual(self.g.state["warehouse"]["mage_robes"], before["mage_robes"])

    def test_wrong_slots_and_missing_armour_never_partially_deduct_items(self):
        for payload in ({"weapon": "plate_armour"}, {"armour": "hammer"},
                        {"weapon": "hammer", "armour": "hammer"}, {"gear": "hammer", "armour": "plate_armour"}):
            before = copy.deepcopy(self.g.state)
            with self.assertRaises(ValueError):
                self.dispatch(**payload)
            self.assertEqual(self.g.state, before)
        self.g.state["warehouse"]["plate_armour"] = 0
        before = copy.deepcopy(self.g.state)
        with self.assertRaises(ValueError):
            self.dispatch(weapon="hammer", armour="plate_armour")
        self.assertEqual(self.g.state, before)

    def test_legacy_single_shield_loan_remains_armour_and_returns_once(self):
        stored = self.g.state["warehouse"]["shield"]
        m = self.dispatch(gear="shield")
        m.pop("loaned_equipment")
        m.pop("weapon")
        m.pop("armour")
        self.g.save()
        self.g = Game(ROOT / "assets", self.save)
        with patch.object(self.g.rng, "randint", return_value=20), patch.object(self.g.rng, "randrange", return_value=1):
            self.advance(2)
        report = self.g.commission_board()["missions"][0]
        self.assertEqual(report["loaned_equipment"], [{"item_id": "shield", "slot": "armour", "returned": True}])
        self.g.action("claim_commission", {"mission_id": m["id"]})
        self.assertEqual(self.g.state["warehouse"]["shield"], stored)

    def test_preview_is_pure_and_options_improve_success_chance(self):
        before = copy.deepcopy(self.g.state)
        random_state = self.g.rng.getstate()
        plain = self.g.commission_preview(self.c["id"], "mine")
        self.assertEqual(self.g.state, before)
        self.assertEqual(self.g.rng.getstate(), random_state)
        self.g.state["relics"]["mine"] = 1
        enhanced = self.g.commission_preview(self.c["id"], "mine", "hammer", True)
        self.assertEqual(enhanced["bonus"], plain["bonus"] + 5)
        self.assertGreaterEqual(enhanced["success_percent"], plain["success_percent"])
        self.assertEqual(plain["region_bonus"], 2)

    def test_away_and_returned_people_cannot_be_hired_twice(self):
        m = self.dispatch()
        with self.assertRaises(ValueError):
            self.dispatch()
        self.g.arrive()
        self.assertNotEqual(self.g.customer()["id"], self.c["id"])
        self.g.leave()
        with patch.object(self.g.rng, "randint", return_value=20), patch.object(self.g.rng, "randrange", return_value=1):
            self.advance(2)
        with self.assertRaises(ValueError):
            self.dispatch()
        self.g.action("claim_commission", {"mission_id": m["id"]})
        self.dispatch()

    def test_successful_adventurer_returns_to_shop_for_suitable_displayed_goods(self):
        m = self.dispatch()
        with patch.object(self.g.rng, "randint", return_value=20), patch.object(self.g.rng, "randrange", return_value=1):
            self.advance(2)
        self.g.action("claim_commission", {"mission_id": m["id"]})
        self.g.action("arrive", {})
        self.assertEqual(self.g.customer()["id"], self.c["id"])
        self.assertIn(self.g.customer()["wants"], self.g.state["shelves"])
        self.assertNotIn("commission_return_visit", self.g.customer())

    def test_save_load_preserves_return_report_without_reroll(self):
        m = self.dispatch()
        restored = Game(ROOT / "assets", self.save)
        self.assertEqual(restored.state["commissions"][0], m)
        self.g = restored
        with patch.object(self.g.rng, "randint", return_value=20), patch.object(self.g.rng, "randrange", return_value=1):
            self.advance(2)
        report = copy.deepcopy(self.g.state["commissions"][0])
        restored = Game(ROOT / "assets", self.save)
        with patch.object(restored.rng, "randint") as roll:
            restored._resolve_commissions()
            roll.assert_not_called()
        self.assertEqual(restored.state["commissions"][0], report)

    def test_relics_have_mutually_exclusive_sell_lend_and_unlock_uses(self):
        self.g.state["relics"]["mine"] = 3
        self.g.action("sell_relic", {"region_id": "mine"})
        self.assertEqual(self.g.state["gold"], 1065)
        self.assertEqual(self.g.state["daily"]["revenue"], 65)
        self.g.action("unlock_deep_route", {"region_id": "mine"})
        self.assertEqual(self.g.state["relics"]["mine"], 0)
        self.assertIn("mine", self.g.state["deep_routes"])
        with self.assertRaises(ValueError):
            self.dispatch(use_relic=True)
        with self.assertRaises(ValueError):
            self.g.action("unlock_deep_route", {"region_id": "mine"})
        terms = self.g.commission_preview(self.c["id"], "mine", deep=True)
        self.assertEqual(terms["fee"], 70)
        self.assertEqual(terms["days"], 3)
        self.assertEqual(terms["difficulty"], 15)

    def test_locked_regions_insufficient_funds_and_wrong_gear_are_atomic(self):
        self.g.save()
        for extra in ({"region_id": "crypt"}, {"deep": True}, {"gear": "bow"}, {"use_relic": True}, {"deep": "false"}):
            payload = dict(customer_id=self.c["id"], region_id="mine", **{k:v for k,v in extra.items() if k != "region_id"})
            payload.update(extra)
            before = copy.deepcopy(self.g.state)
            with self.assertRaises(ValueError):
                self.g.action("dispatch_commission", payload)
            self.assertEqual(self.g.state, before)
        self.g.state["gold"] = 0
        with self.assertRaises(ValueError):
            self.dispatch()
        self.assertEqual(self.g.state["commissions"], [])

    def test_three_active_limit_and_current_customer_guard(self):
        self.g.state["gold"] = 500
        customers = [self.c] + [self.g._new_customer() for _ in range(3)]
        for c in customers[:3]:
            self.g.action("dispatch_commission", {"customer_id": c["id"], "region_id": "mine"})
        with self.assertRaises(ValueError):
            self.g.action("dispatch_commission", {"customer_id": customers[3]["id"], "region_id": "mine"})
        self.g.state["current_id"] = customers[3]["id"]
        with self.assertRaises(ValueError):
            self.g.commission_preview(customers[3]["id"], "mine")

    def test_all_regions_progress_and_depths_produce_double_loot(self):
        self.g.state["gold"] = 1000
        for region, days in (("mine", 2), ("marsh", 3), ("crypt", 4)):
            self.g.action("dispatch_commission", {"customer_id": self.c["id"], "region_id": region})
            m = self.g.state["commissions"][-1]
            with patch.object(self.g.rng, "randint", return_value=20), patch.object(self.g.rng, "randrange", return_value=1):
                self.advance(days)
            self.g.action("claim_commission", {"mission_id": m["id"]})
            self.assertEqual(self.g.state["relics"][region], 0)
        self.g.state["relics"]["mine"] = 2
        self.g.action("unlock_deep_route", {"region_id": "mine"})
        m = self.dispatch(deep=True)
        with patch.object(self.g.rng, "randint", return_value=20), patch.object(self.g.rng, "randrange", return_value=1):
            self.advance(3)
        self.assertEqual(m["loot_quantity"], 2)
        self.g.action("claim_commission", {"mission_id": m["id"]})
        self.assertEqual(self.g.state["relics"]["mine"], 0)

    def test_drop_table_is_one_percent_relic_eight_percent_unique_and_rest_equipment(self):
        region = self.g._region("mine")
        with patch.object(self.g.rng, "randrange", side_effect=range(100)):
            rewards = self.g._roll_commission_loot(region, 100)
        self.assertEqual(rewards["relic_quantity"], 1)
        self.assertEqual(sum(x["quantity"] for x in rewards["equipment_loot"]), 91)
        self.assertEqual(len(rewards["unique_loot"]),8)
        self.assertTrue(all(x["item_id"] in region["loot"] for x in rewards["equipment_loot"]))

    def test_depth_slots_roll_independently_and_can_mix_rewards(self):
        with patch.object(self.g.rng, "randrange", side_effect=[0, 9]):
            rewards = self.g._roll_commission_loot(self.g._region("mine"), 2)
        self.assertEqual(rewards["relic_quantity"], 1)
        self.assertEqual(sum(x["quantity"] for x in rewards["equipment_loot"]), 1)
        with patch.object(self.g.rng, "randrange", side_effect=[0, 0]):
            rare = self.g._roll_commission_loot(self.g._region("mine"), 2)
        self.assertEqual(rare["relic_quantity"], 2)
        self.assertEqual(rare["equipment_loot"], [])

    def test_relic_only_report_can_be_collected_without_equipment(self):
        m = self.dispatch()
        before = copy.deepcopy(self.g.state["warehouse"])
        with patch.object(self.g.rng, "randint", return_value=20), patch.object(self.g.rng, "randrange", return_value=0):
            self.advance(2)
        self.assertIsNone(m["loot_item"])
        self.assertEqual(m["loot_quantity"], 0)
        self.g.action("claim_commission", {"mission_id": m["id"]})
        self.assertEqual(self.g.state["warehouse"], before)
        self.assertEqual(self.g.state["relics"]["mine"], 1)

    def test_already_rolled_legacy_report_keeps_its_original_rewards(self):
        m = self.dispatch()
        m.update(status="returned", success=True, roll=20, loot_item="hammer", loot_quantity=2,
                 relic_quantity=2, gear_returned=False, relic_returned=False)
        self.g.save()
        restored = Game(ROOT / "assets", self.save)
        before = restored.state["warehouse"]["hammer"]
        public_report = restored.commission_board()["missions"][0]
        self.assertEqual(public_report["equipment_loot"], [{"item_id": "hammer", "quantity": 2}])
        restored.action("claim_commission", {"mission_id": m["id"]})
        self.assertEqual(restored.state["warehouse"]["hammer"], before + 2)
        self.assertEqual(restored.state["relics"]["mine"], 2)

    def test_old_save_gets_empty_commissions_without_changing_gold(self):
        for key in ("commissions", "relics", "routes", "deep_routes"):
            self.g.state.pop(key)
        self.g.save()
        restored = Game(ROOT / "assets", self.save)
        self.assertEqual(restored.state["gold"], 1000)
        self.assertEqual(restored.state["routes"], ["mine"])
        self.assertEqual(restored.state["commissions"], [])
        self.assertEqual(restored.state["customers"][self.c["id"]]["name"], self.c["name"])


if __name__ == "__main__":
    unittest.main()
