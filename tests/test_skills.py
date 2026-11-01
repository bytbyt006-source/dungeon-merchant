"""Talents affect actual outcomes and persist without replaying rewards."""
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

class SkillTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.save = Path(folder.name) / "save.json"
        self.g = Game(ROOT / "assets", self.save, random.Random(7))
        stock_shop(self.g)

    def test_ranks_points_and_reload(self):
        self.g.action("learn_skill", {"skill": "eloquence"})
        self.assertEqual(self.g.effective_eloquence(), 4)
        before = copy.deepcopy(self.g.state)
        with self.assertRaises(ValueError):
            self.g.action("learn_skill", {"skill": "supplier"})
        self.assertEqual(before, self.g.state)
        self.g.gain_xp(300)
        self.g.action("learn_skill", {"skill": "eloquence"})
        self.g.action("learn_skill", {"skill": "eloquence"})
        with self.assertRaises(ValueError):
            self.g.action("learn_skill", {"skill": "eloquence"})
        loaded = Game(ROOT / "assets", self.save)
        self.assertEqual(loaded.skill_tree(), self.g.skill_tree())
        self.assertEqual(loaded.effective_eloquence(), 6)

    def test_supplier_discount_matches_payment_receipt_and_public_price(self):
        self.g.action("learn_skill", {"skill": "supplier"})
        self.assertEqual(self.g.public()["caravan"]["stock"][0]["price"], 57)
        self.g.action("merchant_buy", {"item_id": "greatsword", "quantity": 2})
        self.assertEqual(self.g.state["gold"], 886)
        self.assertEqual(self.g.state["caravan"]["purchases"][-1]["total"], 114)
        self.assertEqual(self.g.item("greatsword")["cost"], 60)
        self.assertLess(self.g.public()["stock"][0]["cost"], 60)

    def trade(self):
        self.g.finish_market()
        self.g.arrive()
        self.g.begin(self.g.customer()["wants"])
        if self.g.state["deal"]["status"] != "negotiating":
            self.g.state["deal"].update(status="negotiating", offer=20, last_quote=None, failures=0)
        return self.g.customer(), self.g.state["deal"]

    def test_patience_preview_and_failed_roll_agree(self):
        self.g.action("learn_skill", {"skill": "patience"})
        c, deal = self.trade()
        c.update(mood=2, personality="impatient")
        deal.update(item_id="longsword",offer=20, last_quote=None, failures=0)
        c["budget"] = 1000
        price = 52
        preview = self.g.negotiation_preview(price)
        with patch.object(self.g.rng, "randint", return_value=1):
            self.g.quote(price)
        self.assertEqual(c["mood"], 2)
        self.assertEqual(preview["failure_mood"], "Neutral")
        self.assertEqual(preview["walkaway_on_failure"], deal["status"] == "declined")
        with patch.object(self.g.rng, "randint", return_value=1):
            self.g.quote(price)
        self.assertEqual(c["mood"], 1)

    def test_confirmed_sale_grants_xp_once(self):
        self.trade()
        self.g.prepare_payment()
        self.assertEqual(self.g.state["skills"]["xp"], 0)
        self.g.action("collect_payment", {})
        self.assertEqual(self.g.state["skills"]["xp"], 10)
        with self.assertRaises(ValueError):
            self.g.action("collect_payment", {})
        self.assertEqual(self.g.state["skills"]["xp"], 10)

    def test_loot_copy_excludes_loan_and_claim_cannot_repeat(self):
        self.g.action("learn_skill", {"skill": "fortune"})
        self.g.finish_market()
        c = self.g._new_customer([next(p for p in self.g.portraits if p["weapon"] == "hammer_shield")])
        self.g.dispatch_commission(c["id"], "mine", weapon="hammer")
        m = self.g.state["commissions"][-1]
        self.assertEqual(m["duplicate_chance"], 20)
        self.g.state["day"] = m["due_day"]
        with patch.object(self.g.rng, "randint", return_value=20), patch.object(self.g.rng, "randrange", side_effect=[50, 0]), patch.object(self.g.rng, "choice", return_value="hammer"):
            self.g._resolve_commissions()
        self.assertEqual(m["equipment_loot"], [{"item_id": "hammer", "quantity": 2}])
        drops = self.g.commission_board()["missions"][0]["collectible_items"]
        self.assertEqual(drops[0]["quantity"], 3)
        self.assertTrue((ROOT / drops[0]["src"]).is_file())
        before = self.g.state["warehouse"]["hammer"]
        self.g.action("claim_commission", {"mission_id": m["id"]})
        self.assertEqual(self.g.state["warehouse"]["hammer"], before + 3)
        self.assertEqual(self.g.state["skills"]["xp"], 35)
        reloaded = Game(ROOT / "assets", self.save)
        with self.assertRaises(ValueError):
            reloaded.action("claim_commission", {"mission_id": m["id"]})
        self.assertEqual(reloaded.state["warehouse"], self.g.state["warehouse"])

    def test_legacy_progress_credited_only_once(self):
        self.g.state.pop("skills")
        self.g._upgrade_skills()
        self.g.gain_xp(100)
        self.g.save()
        loaded = Game(ROOT / "assets", self.save)
        self.assertEqual(loaded.state["skills"]["points"], 2)

    def test_ten_branches_have_names_and_prerequisites_are_enforced(self):
        tree = self.g.skill_tree()
        self.assertEqual(len(tree["talents"]), 19)
        self.assertEqual(sum(len(t["nodes"]) for t in tree["talents"]), 57)
        self.g.gain_xp(1000)
        before = copy.deepcopy(self.g.state)
        with self.assertRaisesRegex(ValueError, "Requires"):
            self.g.action("learn_skill", {"skill": "contracts"})
        self.assertEqual(self.g.state, before)
        self.g.action("learn_skill", {"skill": "supplier"})
        self.g.action("learn_skill", {"skill": "contracts"})
        self.assertEqual(self.g.skill_rank("contracts"), 1)

    def test_appraisal_requires_observation_and_matches_preview(self):
        c, deal = self.trade()
        c.update(observed=[], budget=1000)
        deal.update(item_id="longsword",offer=30, failures=0, last_quote=None)
        before = self.g.difficulty(45)
        self.g.state["skills"]["ranks"]["appraisal"] = 3
        self.assertEqual(self.g.difficulty(45), before)
        c["observed"] = ["manner"]
        self.assertEqual(self.g.difficulty(45), before - 4)
        self.assertEqual(self.g.negotiation_preview(45)["insight_bonus"], 4)

    def test_counteroffer_changes_real_customer_concession(self):
        c, deal = self.trade()
        c.update(mood=4, budget=1000, personality="patient")
        c["willingness"]["greatsword"] = 1000
        deal.update(item_id="greatsword",offer=30, failures=0, last_quote=None)
        initial = copy.deepcopy(self.g.state)
        with patch.object(self.g.rng, "randint", return_value=1):
            self.g.quote(90)
        ordinary = self.g.state["deal"]["offer"]
        self.g.state = initial
        self.g.state["skills"]["ranks"]["counteroffer"] = 3
        with patch.object(self.g.rng, "randint", return_value=1):
            self.g.quote(90)
        self.assertEqual(ordinary, 45)
        self.assertEqual(self.g.state["deal"]["offer"], 50)

    def test_expedition_talents_change_fee_roll_days_and_snapshot_risk(self):
        self.g.finish_market()
        c = self.g._new_customer([next(p for p in self.g.portraits if p["weapon"] == "hammer_shield")])
        before = self.g.commission_preview(c["id"], "mine", weapon="hammer")
        self.g.state["skills"]["ranks"].update(contracts=3, expedition=3, pathfinder=3, salvage=1)
        after = self.g.commission_preview(c["id"], "mine", weapon="hammer")
        self.assertEqual(after["fee"], 25)
        self.assertEqual(after["bonus"], before["bonus"] + 3)
        self.assertEqual(after["success_percent"], before["success_percent"] + 15)
        self.assertEqual(after["days"], 1)
        self.g.dispatch_commission(c["id"], "mine", weapon="hammer")
        mission = self.g.state["commissions"][-1]
        self.assertEqual(mission["gear_loss_percent"], 25)
        self.g.state["skills"]["ranks"]["salvage"] = 3
        self.g.state["day"] = mission["due_day"]
        mission["difficulty"] = 30
        with patch.object(self.g.rng, "randint", return_value=1), patch.object(self.g.rng, "random", return_value=.2):
            self.g._resolve_commissions()
        self.assertFalse(mission["loaned_equipment"][0]["returned"])

    def test_old_skill_tree_gains_new_routes_without_losing_points(self):
        self.g.state["skills"] = {"xp": 100, "points": 1, "ranks": {"eloquence": 1, "patience": 0, "supplier": 0, "fortune": 0}}
        self.g.save()
        loaded = Game(ROOT / "assets", self.save)
        self.assertEqual(len(loaded.state["skills"]["ranks"]), 19)
        self.assertEqual(loaded.skill_rank("eloquence"), 1)
        self.assertEqual(loaded.state["skills"]["points"], 1)
