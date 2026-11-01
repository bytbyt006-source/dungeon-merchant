"""Behavioral tests for money, bargaining, identity and persistent state."""

import copy
import json
from pathlib import Path
import random
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shop_fixture import stock_shop
from game import Game, positive_int, calendar_date, new_daily, CATALOG
from main import create_server


class TradingTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.save = Path(self.folder.name) / "save.json"
        self.game = Game(ROOT / "assets", self.save, random.Random(7))
        stock_shop(self.game)
        # Trading-rule fixtures use a fully stocked display, after Monday buying.
        self.game.state["caravan"]["open"] = False
        self.game.state["shelf_capacity"] = len(self.game.state["stock"])
        self.game.state["shelves"] = [item["id"] for item in self.game.state["stock"]]
        for item in self.game.state["stock"]:
            if not item["quantity"]:
                amount = min(3, self.game.state["warehouse"][item["id"]])
                item["quantity"] += amount
                self.game.state["warehouse"][item["id"]] -= amount

    def test_armour_purchase_display_and_customer_sale(self):
        armour_ids = [x["id"] for x in CATALOG if x.get("category") == "armour"]
        self.assertEqual(len(armour_ids), 5)
        for item_id in armour_ids:
            with self.subTest(item=item_id):
                g = Game(ROOT / "assets", Path(self.folder.name) / (item_id + ".json"), random.Random(7))
                g.action("allocate_attributes",{"allocation":{"luck":5}})
                cost = g.item(item_id)["cost"]
                stored = g.state["warehouse"][item_id]
                g.action("merchant_buy", {"item_id": item_id, "quantity": 1})
                self.assertEqual(g.state["gold"], 1000 - cost)
                self.assertEqual(g.state["warehouse"][item_id], stored + 1)
                for slot in range(g.state["shelf_capacity"]):
                    g.action("return_stock", {"slot": slot})
                g.action("place_stock", {"slot": 0, "item_id": item_id, "quantity": 1,
                                         "mode": g.item(item_id)["mode"], "price": g.item(item_id)["price"]})
                g.action("finish_market", {})
                g.action("arrive", {})
                c = g.customer()
                self.assertEqual(c["wants"], item_id)
                self.assertIn(item_id, g.professions[c["weapon_type"]]["preferred_items"])
                g.action("begin", {"item_id": item_id})
                offer = g.state["deal"]["agreed"] if g.state["deal"]["status"] == "agreed" else g.state["deal"]["offer"]
                g.action("accept", {})
                self.assertEqual(g.state["gold"], 1000 - cost + offer)
                self.assertEqual(g.item(item_id)["quantity"], 0)
                self.assertEqual(c["purchases"][-1]["item"], g.item(item_id)["name"])

    def test_old_inventory_gets_armour_without_granting_free_stock(self):
        self.prepare()
        old = copy.deepcopy(self.game.state)
        armour_ids = {x["id"] for x in CATALOG if x.get("category") == "armour"}
        old["stock"] = [x for x in old["stock"] if x["id"] not in armour_ids]
        old["shelves"] = [x for x in old["shelves"] if x not in armour_ids]
        old["shelf_capacity"] = len(old["shelves"])
        for item_id in armour_ids:
            old["warehouse"].pop(item_id)
        old["caravan"]["stock"] = [x for x in old["caravan"]["stock"] if x["item_id"] not in armour_ids]
        self.save.write_text(json.dumps(old), encoding="utf-8")
        restored = Game(ROOT / "assets", self.save)
        self.assertEqual(restored.state["gold"], old["gold"])
        self.assertEqual(restored.state["deal"], old["deal"])
        for item_id in armour_ids:
            self.assertEqual(restored.item(item_id)["quantity"], 0)
            self.assertEqual(restored.state["warehouse"][item_id], 0)
        self.assertEqual(len(restored.state["caravan"]["stock"]), len(CATALOG))
        restored.save()
        again = Game(ROOT / "assets", self.save)
        self.assertEqual(again.state["warehouse"], restored.state["warehouse"])
        self.assertEqual(again.state["caravan"], restored.state["caravan"])

    def prepare(self, mode="bargain"):
        g = self.game
        g.action("arrive", {})
        c = g.customer()
        c["budget"] = 1000
        c["willingness"]["longsword"] = 100
        g.item("longsword")["mode"] = mode
        g.action("begin", {"item_id": "longsword"})
        return c

    def test_coin_pouch_waits_for_collection_and_survives_reload(self):
        c = self.prepare()
        before_gold = self.game.state["gold"]
        before_stock = self.game.item("longsword")["quantity"]
        offer = self.game.state["deal"]["offer"]
        self.game.action("prepare_payment", {})
        self.assertEqual(self.game.state["deal"]["status"], "payment")
        self.assertEqual(self.game.state["gold"], before_gold)
        self.assertEqual(self.game.item("longsword")["quantity"], before_stock)
        self.assertEqual(c["purchases"], [])
        restored = Game(ROOT / "assets", self.save)
        self.assertEqual(restored.state["deal"]["status"], "payment")
        for action, payload in [("prepare_payment", {}), ("leave", {}), ("skip_day", {}),
                                ("cancel", {}), ("quote", {"price": offer}),
                                ("begin", {"item_id": "shield"}), ("return_stock", {"slot": 1})]:
            with self.subTest(action=action), self.assertRaises(ValueError):
                restored.action(action, payload)
        restored.action("collect_payment", {})
        self.assertEqual(restored.state["gold"], before_gold + offer)
        self.assertEqual(restored.item("longsword")["quantity"], before_stock - 1)
        self.assertEqual(len(restored.customer()["purchases"]), 1)
        with self.assertRaises(ValueError):
            restored.action("collect_payment", {})
        self.assertEqual(restored.state["gold"], before_gold + offer)

    def test_last_sale_clears_shelf_and_can_be_replaced(self):
        self.prepare("fixed")
        item = self.game.item("longsword")
        item["quantity"] = 1
        slot = self.game.state["shelves"].index("longsword")
        stored = self.game.state["warehouse"]["longsword"]
        self.game.action("prepare_payment", {})
        self.game.action("collect_payment", {})
        self.assertIsNone(self.game.state["shelves"][slot])
        self.assertEqual(item["quantity"], 0)
        self.assertEqual(self.game.state["warehouse"]["longsword"], stored)
        self.game.action("place_stock", {"slot": slot, "item_id": "longsword", "quantity": 1,
                                         "mode": "fixed", "price": 40})
        self.assertEqual(self.game.state["shelves"][slot], "longsword")
        self.assertEqual(item["quantity"], 1)

    def test_loading_sold_out_shelf_marks_it_empty(self):
        self.game.item("longsword")["quantity"] = 0
        slot = self.game.state["shelves"].index("longsword")
        self.game.save()
        restored = Game(ROOT / "assets", self.save)
        self.assertIsNone(restored.state["shelves"][slot])
        self.assertEqual(restored.state["warehouse"], self.game.state["warehouse"])

    def test_marked_price_pouch_collects_exact_label(self):
        self.prepare("fixed")
        self.game.action("prepare_payment", {})
        self.assertEqual(self.game.state["deal"]["agreed"], 40)
        self.game.action("collect_payment", {})
        self.assertEqual(self.game.state["gold"], 1040)
        self.assertEqual(self.game.state["daily"]["revenue"], 40)

    def test_unaffordable_sale_cannot_create_pouch(self):
        self.prepare("fixed")
        self.game.state["deal"]["sale_allowed"] = False
        with self.assertRaises(ValueError):
            self.game.action("prepare_payment", {})
        with self.assertRaises(ValueError):
            self.game.action("collect_payment", {})

    def test_accept_changes_money_stock_and_journal_once(self):
        c = self.prepare()
        price = self.game.state["deal"]["offer"]
        before_gold = self.game.state["gold"]
        before_stock = self.game.item("longsword")["quantity"]
        self.game.action("accept", {})
        self.assertEqual(self.game.state["gold"], before_gold + price)
        self.assertEqual(self.game.item("longsword")["quantity"], before_stock - 1)
        self.assertEqual(c["purchases"][-1]["price"], price)
        saved = copy.deepcopy(self.game.state)
        with self.assertRaises(ValueError):
            self.game.action("accept", {})
        self.assertEqual(self.game.state, saved)

    def test_marked_price_direct_sale(self):
        self.prepare("fixed")
        self.assertEqual(self.game.state["deal"]["status"], "agreed")
        self.assertEqual(self.game.state["gold"], 1000)
        self.game.action("accept", {})
        self.assertEqual(self.game.state["gold"], 1040)

    def test_unaffordable_marked_price_cannot_be_sold(self):
        self.game.action("arrive", {})
        self.game.customer()["willingness"]["shield"] = 20
        self.game.action("begin", {"item_id": "shield"})
        self.assertEqual(self.game.state["deal"]["status"], "agreed")
        self.assertFalse(self.game.state["deal"]["sale_allowed"])
        with self.assertRaises(ValueError):
            self.game.action("accept", {})
        self.assertEqual(self.game.state["gold"], 1000)

    def test_opening_offer_cost_band_and_personality_distribution(self):
        c = self.prepare()
        item = dict(self.game.item("longsword"), cost=100)
        c["budget"] = 1000
        c["willingness"][item["id"]] = 1000
        means = {}
        for personality in ("patient", "proud", "impatient"):
            c["personality"] = personality
            self.game.rng.seed(123)
            samples = [self.game._opening_offer(item, c) for _ in range(10000)]
            self.assertGreaterEqual(min(samples), 70)
            self.assertLessEqual(max(samples), 130)
            means[personality] = sum(samples) / len(samples)
            # Equal-width bands: extreme high prices are rarer than central ones.
            self.assertLess(sum(125 <= x <= 130 for x in samples), sum(97 <= x <= 102 for x in samples))
        self.assertLess(means["patient"], means["impatient"])
        self.assertLess(means["impatient"], means["proud"])

    def test_opening_offer_independent_of_shop_label(self):
        c = self.prepare()
        item = self.game.item("longsword")
        self.game.rng.seed(19)
        first = self.game._opening_offer(item, c)
        item["price"] = 99999
        self.game.rng.seed(19)
        self.assertEqual(self.game._opening_offer(item, c), first)

    def test_opening_offer_handles_budget_below_band_without_invalid_bid(self):
        c = self.prepare()
        self.game.action("cancel", {})
        c["budget"] = 1
        self.game.action("begin", {"item_id": "hammer"})
        self.assertEqual(self.game.state["deal"]["status"], "declined")
        self.assertIsNone(self.game.state["deal"]["offer"])
        self.assertEqual(self.game.state["gold"], 1000)

    def test_opening_offer_caps_budget_within_band(self):
        c = self.prepare()
        item = self.game.item("longsword")
        c["budget"] = 26
        for _ in range(100):
            offer = self.game._opening_offer(item, c)
            self.assertGreaterEqual(offer, 25)
            self.assertLessEqual(offer, 26)

    def test_d20_addition_and_confirmation(self):
        self.prepare()
        quote = self.game.state["deal"]["offer"] + 5
        dc = self.game.difficulty(quote)
        with patch.object(self.game.rng, "randint", return_value=20):
            self.game.action("quote", {"price": quote})
        roll = self.game.state["last_roll"]
        self.assertEqual(roll["total"], 23)
        self.assertEqual(roll["difficulty"], dc)
        self.assertTrue(roll["success"])
        self.assertEqual(self.game.state["gold"], 1000)
        self.game.action("accept", {})
        self.assertEqual(self.game.state["gold"], 1000 + quote)

    def test_observation_improves_odds_without_revealing_private_prices(self):
        c = self.prepare()
        price = self.game.state["deal"]["offer"] + 10
        before = self.game.difficulty(price)
        self.game.action("inspect", {"clue": "equipment"})
        self.game.action("inspect", {"clue": "manner"})
        after = self.game.difficulty(price)
        self.assertLessEqual(after, before)
        self.assertEqual(self.game.negotiation_preview(price)["insight_bonus"], 2)
        self.game.action("inspect", {"clue": "equipment"})
        self.assertEqual(self.game.difficulty(price), after)
        public = self.game.public()["customer"]
        for key in ("buying_style", "urgency", "budget", "willingness"):
            self.assertNotIn(key, public)
        self.assertTrue(any("premium" in clue or "purchase" in clue for clue in c["known"]))

    def test_preview_odds_and_failure_match_actual_d20_outcomes(self):
        self.prepare()
        price = self.game.state["deal"]["offer"] + 10
        preview = self.game.negotiation_preview(price)
        expected = sum(raw + 3 >= self.game.difficulty(price) for raw in range(1, 21)) * 5
        self.assertEqual(preview["success_percent"], expected)
        with patch.object(self.game.rng, "randint", return_value=1):
            self.game.action("quote", {"price": price})
        self.assertEqual(self.game.public()["customer"]["mood"], preview["failure_mood"])
        self.assertEqual(self.game.state["deal"]["status"] == "declined", preview["walkaway_on_failure"])

    def test_good_mood_and_patient_temperament_allow_more_bargaining(self):
        c = self.prepare()
        c.update(personality="patient", urgency="prepared", mood=4)
        happy = self.game.patience_limit()
        c["mood"] = 2
        neutral = self.game.patience_limit()
        c["personality"] = "impatient"
        self.assertGreater(happy, neutral)
        self.assertGreater(neutral, self.game.patience_limit())

    def test_unwilling_fixed_shopper_is_excluded_even_with_enough_cash(self):
        self.prepare("fixed")
        c = self.game.customer()
        c["budget"] = 300
        c["weapon_type"] = "sword"
        c["willingness"]["longsword"] = 30
        self.assertNotIn("longsword", self.game._shopping_choices(c, c["budget"], c["willingness"]))
        self.game.action("cancel", {})
        c["refused"] = []
        self.game.action("begin", {"item_id": "longsword"})
        self.assertFalse(self.game.state["deal"]["sale_allowed"])
        with self.assertRaises(ValueError):
            self.game.action("prepare_payment", {})

    def test_loaded_initial_fixed_offer_is_repaired_without_creating_a_sale(self):
        self.prepare("fixed")
        c = self.game.customer()
        c["wants"] = "longsword"
        c["budget"] = 200
        c["willingness"]["longsword"] = 50
        self.game.state["deal"]["sale_allowed"] = False
        self.game.save()
        original = copy.deepcopy(self.game.state)
        restored = Game(ROOT / "assets", self.save)
        self.assertTrue(restored.state["deal"]["sale_allowed"])
        self.assertEqual(restored.state["gold"], original["gold"])
        self.assertEqual(restored.state["daily"], original["daily"])
        self.assertEqual(restored.state["stock"], original["stock"])
        self.assertEqual(restored.customer()["id"], c["id"])
        self.assertEqual(restored.customer()["budget"], 200)
        restored.action("prepare_payment", {})
        restored.action("collect_payment", {})
        self.assertEqual(restored.state["gold"], original["gold"] + 40)

    def test_buying_tendencies_change_the_same_quote_difficulty(self):
        c = self.prepare()
        price = self.game.state["deal"]["offer"] + 10
        c.update(buying_style="thrifty", urgency="browsing", observed=[])
        cautious = self.game.difficulty(price)
        c.update(buying_style="quality", urgency="urgent")
        self.assertLess(self.game.difficulty(price), cautious)

    def test_stocking_settings_survive_empty_shelf_and_reload(self):
        self.game.action("place_stock", {"slot": 0, "item_id": "greatsword", "quantity": 2,
                                         "mode": "fixed", "price": 69})
        self.game.action("return_stock", {"slot": 0})
        restored = Game(ROOT / "assets", self.save)
        self.assertEqual(restored.public()["shelf_settings"]["greatsword"],
                         {"mode": "fixed", "price": 69, "quantity": 2})

    def test_roll_equal_to_difficulty_succeeds(self):
        self.prepare()
        quote = self.game.state["deal"]["offer"] + 1
        needed = self.game.difficulty(quote) - 3
        with patch.object(self.game.rng, "randint", return_value=needed):
            self.game.action("quote", {"price": quote})
        self.assertTrue(self.game.state["last_roll"]["success"])

    def test_failure_second_round_and_mood(self):
        c = self.prepare()
        price = self.game.state["deal"]["offer"] + 20
        with patch.object(self.game.rng, "randint", return_value=1):
            self.game.action("quote", {"price": price})
        self.assertEqual(c["mood"], 1)
        self.assertEqual(self.game.state["deal"]["status"], "negotiating")
        with patch.object(self.game.rng, "randint", return_value=20):
            self.game.action("quote", {"price": price - 1})
        self.assertEqual(self.game.state["deal"]["round"], 2)
        self.assertEqual(self.game.state["deal"]["status"], "agreed")

    def test_unaffordable_quote_cannot_roll(self):
        c = self.prepare()
        c["budget"] = 30
        with patch.object(self.game.rng, "randint") as die:
            self.game.action("quote", {"price": 31})
            die.assert_not_called()
        self.assertIsNone(self.game.state["last_roll"])
        self.assertEqual(self.game.state["gold"], 1000)

    def test_low_quote_requires_no_die(self):
        self.prepare()
        offer = self.game.state["deal"]["offer"]
        with patch.object(self.game.rng, "randint") as die:
            self.game.action("quote", {"price": offer})
            die.assert_not_called()
        self.assertEqual(self.game.state["deal"]["status"], "agreed")

    def test_angry_customer_cannot_repeat_same_item(self):
        self.prepare()
        with patch.object(self.game.rng, "randint", return_value=1):
            self.game.action("quote", {"price": 52})
            self.game.action("quote", {"price": 52})
        self.assertEqual(self.game.state["deal"]["status"], "declined")
        with self.assertRaises(ValueError):
            self.game.action("begin", {"item_id": "longsword"})

    def test_same_portrait_does_not_mean_same_identity(self):
        self.game.portraits = self.game.portraits[:1]
        first = self.game._new_customer()
        second = self.game._new_customer()
        self.assertEqual(first["portrait"], second["portrait"])
        self.assertNotEqual(first["id"], second["id"])
        first["actions"].append("A private interaction")
        self.assertEqual(second["actions"], [])

    def test_returning_customer_keeps_history_and_portrait(self):
        self.prepare()
        self.game.action("accept", {})
        before = copy.deepcopy(self.game.customer())
        self.game.action("leave", {})
        # A returning shopper waits for three intervening visitors.
        for _ in range(3):
            with patch.object(self.game.rng,"random",return_value=1):self.game.action("arrive",{})
            self.game.action("leave",{})
        # Keep this returning shopper eligible; this test concerns identity/history.
        for item in self.game.state["stock"]:
            item.update(mode="bargain", price=item["cost"])
        with patch.object(self.game.rng, "random", return_value=0):
            self.game.action("arrive", {})
        c = self.game.customer()
        self.assertEqual(c["id"], before["id"])
        self.assertEqual(c["portrait"], before["portrait"])
        self.assertEqual(c["purchases"], before["purchases"])
        self.assertEqual(c["visits"], 2)

    def test_save_restore_including_active_negotiation(self):
        self.prepare()
        restored = Game(ROOT / "assets", self.save)
        self.assertEqual(restored.state, self.game.state)
        restored.action("accept", {})
        self.assertEqual(len(restored.customer()["purchases"]), 1)

    def test_invalid_save_is_preserved(self):
        self.save.write_text("broken json", encoding="utf-8")
        with self.assertRaises(ValueError):
            Game(ROOT / "assets", self.save)
        self.assertEqual(self.save.read_text(), "broken json")

    def test_public_state_hides_budget_willingness_and_personality(self):
        self.prepare()
        public = self.game.public()["customer"]
        for key in ("budget", "willingness", "wealth", "personality"):
            self.assertNotIn(key, public)

    def test_invalid_prices_leave_state_unchanged(self):
        for value in (0, -1, 2.5, True, "90", 100000):
            with self.subTest(price=value):
                before = copy.deepcopy(self.game.state)
                with self.assertRaises(ValueError):
                    self.game.action("set_price", {"item_id": "longsword", "price": value})
                self.assertEqual(before, self.game.state)

    def test_price_labels_locked_during_visit(self):
        self.game.action("arrive", {})
        with self.assertRaises(ValueError):
            self.game.action("set_price", {"item_id": "shield", "price": 1})

    def test_all_42_portraits_exist(self):
        self.assertEqual(len(self.game.portraits), 42)
        for portrait in self.game.portraits:
            self.assertTrue((ROOT / "assets/characters" / portrait["file"]).is_file())

    def test_every_portrait_requests_its_profession_weapon(self):
        portraits = list(self.game.portraits)
        for portrait in portraits:
            with self.subTest(portrait=portrait["id"]):
                if self.game.state["daily"]["closed"]:
                    self.game.action("next_day", {})
                if self.game.state["caravan"]["open"]:
                    self.game.action("finish_market", {})
                self.game.portraits = [portrait]
                with patch.object(self.game.rng, "random", return_value=1):
                    self.game.action("arrive", {})
                c = self.game.customer()
                role = self.game.professions[portrait["weapon"].replace("_outlaw", "")]
                self.assertEqual(c["profession"], role["name"])
                self.assertIn(c["wants"], role["preferred_items"])
                self.assertTrue(c["armour"])
                self.assertTrue(c["accessories"])
                self.game.action("leave", {})

    def test_recommendation_does_not_overwrite_original_request(self):
        self.game.action("arrive", {})
        c = self.game.customer()
        requested = c["wants"]
        other = next(x["id"] for x in self.game.state["stock"] if x["id"] != requested)
        self.game.action("begin", {"item_id": other})
        self.assertEqual(c["wants"], requested)

    def test_old_save_gets_profession_without_losing_money_or_history(self):
        self.prepare()
        self.game.action("accept", {})
        old = copy.deepcopy(self.game.state)
        c = old["customers"][old["current_id"]]
        for key in ("profession", "weapon_type", "armour", "accessories"):
            c.pop(key)
        old["stock"] = [x for x in old["stock"] if x["id"] != "greatsword"]
        c["willingness"].pop("greatsword", None)
        self.save.write_text(json.dumps(old), encoding="utf-8")
        restored = Game(ROOT / "assets", self.save)
        self.assertEqual(restored.state["gold"], old["gold"])
        self.assertEqual(restored.customer()["purchases"], c["purchases"])
        self.assertEqual(restored.customer()["id"], c["id"])
        self.assertIn("profession", restored.customer())
        self.assertIn("greatsword", restored.customer()["willingness"])


class CalendarTests(unittest.TestCase):
    setUp = TradingTests.setUp
    prepare = TradingTests.prepare
    def finish_day(self):
        if self.game.state["caravan"]["open"]:
            self.game.action("finish_market", {})
        for _ in range(10):
            self.game.action("arrive", {})
            self.game.action("leave", {})

    def test_skip_day_preserves_sales_and_cancels_current_trade(self):
        self.prepare()
        self.game.action("accept", {})
        self.game.action("leave", {})
        self.game.action("arrive", {})
        self.game.action("begin", {"item_id": "longsword"})
        gold = self.game.state["gold"]
        quantity = self.game.item("longsword")["quantity"]
        self.game.action("skip_day", {})
        self.assertTrue(self.game.state["daily"]["closed"])
        self.assertIsNone(self.game.state["current_id"])
        self.assertIsNone(self.game.state["deal"])
        self.assertEqual(self.game.state["gold"], gold)
        self.assertEqual(self.game.item("longsword")["quantity"], quantity)
        self.assertEqual(self.game.state["day_summary"]["sales"], 1)
        self.assertEqual(self.game.state["day_summary"]["customers"], 2)
        self.game.action("next_day", {})
        self.assertEqual(self.game.state["day"], 2)
        self.assertEqual(self.game.state["daily"]["served"], 0)

    def test_skip_month_end_settles_once(self):
        self.game.state["day"] = 28
        self.game.state["gold"] = 500
        self.game.action("skip_day", {})
        self.assertEqual(self.game.state["gold"], 0)
        self.assertEqual(len(self.game.state["loan"]["payments"]), 1)
        with self.assertRaises(ValueError):
            self.game.action("skip_day", {})
        self.assertEqual(self.game.state["gold"], 0)
        self.assertEqual(len(self.game.state["day_history"]), 1)
        self.game.action("next_day", {})
        self.assertTrue(self.game.state["caravan"]["open"])

    def test_skip_day_can_close_monday_market(self):
        self.game.state["caravan"]["open"] = True
        self.game.action("skip_day", {})
        self.assertFalse(self.game.state["caravan"]["open"])
        self.assertEqual(self.game.state["day_summary"]["customers"], 0)
        self.assertEqual(self.game.state["day_summary"]["revenue"], 0)

    def test_initial_calendar_and_week_year_rollovers(self):
        self.assertEqual(calendar_date(1), {"day": 1, "year": 1, "week": 1, "weekday": "Monday", "month": 1, "day_of_month": 1})
        self.assertEqual(calendar_date(7)["weekday"], "Sunday")
        self.assertEqual(calendar_date(8)["week"], 2)
        self.assertEqual(calendar_date(29)["month"], 2)
        self.assertEqual(calendar_date(336)["week"], 48)
        self.assertEqual(calendar_date(337)["year"], 2)
        self.assertEqual(calendar_date(337)["week"], 1)
        self.assertEqual(calendar_date(337)["weekday"], "Monday")

    def test_tenth_departure_closes_shop_and_next_day_is_explicit(self):
        self.finish_day()
        self.assertTrue(self.game.state["daily"]["closed"])
        self.assertEqual(self.game.state["day_summary"]["customers"], 10)
        self.assertEqual(self.game.state["day"], 1)
        with self.assertRaises(ValueError):
            self.game.action("arrive", {})
        self.game.action("next_day", {})
        self.assertEqual(self.game.state["day"], 2)
        self.assertEqual(self.game.state["daily"], new_daily())

    def test_cannot_skip_unfinished_day(self):
        with self.assertRaises(ValueError):
            self.game.action("next_day", {})
        self.game.action("arrive", {})
        with self.assertRaises(ValueError):
            self.game.action("next_day", {})

    def test_tenth_customer_still_has_time_to_trade(self):
        for _ in range(9):
            self.game.action("arrive", {})
            self.game.action("leave", {})
        self.game.action("arrive", {})
        self.assertFalse(self.game.state["daily"]["closed"])
        c=self.game.customer()
        c["budget"]=1000
        c["willingness"]["shield"]=1000
        self.game.action("begin", {"item_id": "shield"})
        self.game.action("accept", {})
        self.assertEqual(self.game.state["daily"]["revenue"],27)
        self.game.action("leave", {})
        self.assertEqual(self.game.state["day_summary"]["revenue"],27)
        self.assertEqual(self.game.state["day_summary"]["sales"],1)

    def test_month_end_pays_weekly_rent_then_fixed_debt_once(self):
        self.game.state["day"] = 28
        self.game.state["gold"] = 3000
        self.finish_day()
        summary = self.game.state["day_summary"]
        self.assertEqual(summary["rent_payment"]["paid"], 200)
        self.assertEqual(summary["loan_payment"]["principal_paid"], 1000)
        self.assertEqual(summary["loan_payment"]["interest_paid"], 0)
        self.assertEqual(self.game.state["gold"], 1800)
        self.assertEqual(self.game.state["loan"]["balance"], 19000)
        self.game._close_day()
        self.assertEqual(len(self.game.state["loan"]["payments"]), 1)
        self.assertEqual(len(self.game.state["rent"]["payments"]), 1)
        restored = Game(ROOT / "assets", self.save)
        restored.action("next_day", {})
        self.assertEqual(restored.state["gold"], 1800)

    def test_monthly_payment_remains_1000_without_extra_interest(self):
        self.game.state["day"] = 56
        self.game.state["gold"] = 3000
        self.game.state["loan"]["balance"] = 19000
        self.finish_day()
        p = self.game.state["day_summary"]["loan_payment"]
        self.assertEqual(p["interest_paid"], 0)
        self.assertEqual(p["principal_paid"], 1000)
        self.assertEqual(p["balance"], 18000)

    def test_insufficient_cash_carries_arrears_without_negative_cash(self):
        self.game.state["day"] = 28
        self.game.state["gold"] = 20
        self.finish_day()
        loan = self.game.state["loan"]
        self.assertEqual(self.game.state["gold"], 0)
        self.assertEqual(self.game.state["rent"]["arrears"], 180)
        self.assertEqual(loan["interest_arrears"], 0)
        self.assertEqual(loan["principal_arrears"], 1000)
        self.assertEqual(loan["balance"], 20000)
        self.game.action("next_day", {})
        self.game.state["day"] = 56
        self.game.state["gold"] = 5000
        self.finish_day()
        self.assertEqual(self.game.state["rent"]["arrears"], 0)
        self.assertEqual(loan["principal_arrears"], 0)
        self.assertEqual(loan["balance"], 18000)
        self.assertEqual(self.game.state["gold"], 2620)

    def test_final_debt_payment_ends_the_campaign(self):
        self.game.state["day"] = 28
        self.game.state["gold"] = 500
        self.game.state["loan"]["balance"] = 50
        self.finish_day()
        self.assertTrue(self.game.public()["loan"]["paid_off"])
        self.assertEqual(self.game.state["gold"], 250)
        self.assertIsNone(self.game.public()["ending"])
        self.assertEqual(self.game.public()["final_boss"]["status"],"waiting")
        self.game.action("next_day", {})

    def test_rent_is_due_at_sunday_closing_only(self):
        self.game.state["day"] = 6
        self.game.state["gold"] = 500
        self.finish_day()
        self.assertIsNone(self.game.state["day_summary"]["rent_payment"])
        self.assertEqual(self.game.state["gold"], 500)
        self.game.action("next_day", {})
        self.finish_day()
        self.assertEqual(self.game.state["gold"], 300)
        self.assertEqual(self.game.state["rent"]["payments"][0]["day"], 7)
        self.assertIsNone(self.game.state["day_summary"]["loan_payment"])

    def test_old_debt_migration_preserves_cash_goods_and_paid_principal(self):
        self.game.state.pop("economy_version")
        self.game.state.pop("rent")
        self.game.state["loan"].update(original=1000, balance=900, principal_paid=100,
                                         principal_per_month=100, rate_percent=5)
        self.game.save()
        restored = Game(ROOT / "assets", self.save)
        self.assertEqual(restored.state["loan"]["balance"], 19900)
        self.assertEqual(restored.state["gold"], self.game.state["gold"])
        self.assertEqual(restored.state["warehouse"], self.game.state["warehouse"])
        self.assertEqual(restored.state["rent"]["arrears"], 0)
        restored.save()
        again = Game(ROOT / "assets", self.save)
        self.assertEqual(again.state["loan"], restored.state["loan"])

    def test_empty_shelves_do_not_admit_or_count_customers(self):
        for item in self.game.state["stock"]:
            item["quantity"]=0
        before=copy.deepcopy(self.game.state)
        with self.assertRaisesRegex(ValueError,"Restock"):
            self.game.action("arrive",{})
        self.assertEqual(self.game.state,before)

    def test_legacy_save_starts_monday_without_erasing_progress(self):
        self.prepare()
        old=copy.deepcopy(self.game.state)
        for key in ("day", "daily", "loan", "day_history", "day_summary"):
            old.pop(key)
        self.save.write_text(json.dumps(old),encoding="utf-8")
        restored=Game(ROOT / "assets",self.save)
        self.assertEqual(restored.state["day"],1)
        self.assertEqual(restored.state["daily"]["admitted"],1)
        self.assertEqual(restored.state["daily"]["revenue"],0)
        self.assertEqual(restored.state["gold"],old["gold"])
        self.assertEqual(restored.state["current_id"],old["current_id"])


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.save = Path(self.folder.name) / "save.json"
        self.game = Game(ROOT / "assets", self.save, random.Random(18))
        stock_shop(self.game)

    def totals(self):
        return {item["id"]: item["quantity"] + self.game.state["warehouse"][item["id"]] for item in self.game.state["stock"]}

    def test_stocked_fixture_preserves_shelf_and_storage_totals(self):
        self.assertEqual(self.totals(), {x["id"]: x["quantity"] for x in CATALOG})
        self.assertEqual(len(self.game.state["shelves"]), 4)
        self.assertEqual(self.game.item("bow")["quantity"], 0)
        self.assertTrue(self.game.state["caravan"]["open"])

    def test_caravan_receipts_record_order_quantities_and_total_cost(self):
        self.game.action("merchant_buy", {"item_id": "greatsword", "quantity": 2})
        self.game.action("merchant_buy", {"item_id": "longsword", "quantity": 1})
        receipts = self.game.public()["caravan"]["purchases"]
        self.assertEqual([x["item_id"] for x in receipts], ["greatsword", "longsword"])
        self.assertEqual([x["quantity"] for x in receipts], [2, 1])
        self.assertEqual([x["total"] for x in receipts], [120, 35])
        self.assertEqual(self.game.state["gold"], 1000 - sum(x["total"] for x in receipts))
        self.assertNotEqual(receipts[0]["id"], receipts[1]["id"])
        restored = Game(ROOT / "assets", self.save)
        self.assertEqual(restored.public()["caravan"]["purchases"], receipts)
        with self.assertRaises(ValueError):
            restored.action("merchant_buy", {"item_id": "greatsword", "quantity": 40})
        self.assertEqual(restored.state["caravan"]["purchases"], receipts)

    def test_new_week_starts_a_fresh_caravan_receipt_list(self):
        self.game.action("merchant_buy", {"item_id": "book", "quantity": 1})
        self.game.state["day"] = 7
        self.game.state["caravan"]["open"] = False
        self.game.action("skip_day", {})
        self.game.action("next_day", {})
        self.assertEqual(self.game.state["caravan"]["day"], 8)
        self.assertEqual(self.game.state["caravan"]["purchases"], [])

    def test_legacy_caravan_gets_receipts_without_changing_inventory(self):
        self.game.state["caravan"].pop("purchases")
        before = copy.deepcopy(self.game.state)
        self.game.save()
        restored = Game(ROOT / "assets", self.save)
        self.assertEqual(restored.state["caravan"]["purchases"], [])
        for key in ("gold", "warehouse", "stock", "shelves"):
            self.assertEqual(restored.state[key], before[key])

    def test_buy_deducts_cash_and_only_adds_to_warehouse(self):
        before = self.game.item("greatsword")["quantity"]
        stored = self.game.state["warehouse"]["greatsword"]
        self.game.action("merchant_buy", {"item_id": "greatsword", "quantity": 2})
        self.assertEqual(self.game.state["gold"],880)
        self.assertEqual(self.game.item("greatsword")["quantity"],before)
        self.assertEqual(self.game.state["warehouse"]["greatsword"],stored+2)
        self.assertEqual(self.game.state["daily"]["revenue"],0)
        self.assertEqual(self.game.state["daily"]["admitted"],0)
        self.assertEqual(self.game.state["caravan"]["stock"][0]["quantity"],38)

    def test_cannot_buy_without_gold_or_after_departure(self):
        before=copy.deepcopy(self.game.state)
        with self.assertRaises(ValueError):
            self.game.action("merchant_buy", {"item_id":"greatsword","quantity":40})
        self.assertEqual(self.game.state,before)
        self.game.action("finish_market",{})
        with self.assertRaises(ValueError):
            self.game.action("merchant_buy", {"item_id":"book","quantity":1})

    def test_caravan_precedes_shop_and_reopens_next_monday(self):
        with self.assertRaises(ValueError):
            self.game.action("arrive",{})
        self.game.action("finish_market",{})
        self.game.state["day"]=7
        self.game.state["daily"]["closed"]=True
        self.game.action("next_day",{})
        self.assertEqual(self.game.state["day"],8)
        self.assertTrue(self.game.state["caravan"]["open"])
        self.assertEqual(self.game.state["caravan"]["day"],8)
        self.assertEqual(self.game.state["caravan"]["stock"][0]["quantity"],40)

    def test_replace_returns_original_goods_and_sets_sale_mode(self):
        before=self.totals()
        self.game.action("place_stock",{"slot":0,"item_id":"bow","quantity":2,"mode":"fixed","price":36})
        self.assertEqual(self.totals(),before)
        self.assertEqual(self.game.state["shelves"][0],"bow")
        self.assertEqual(self.game.item("greatsword")["quantity"],0)
        self.assertEqual(self.game.item("bow")["quantity"],2)
        self.assertEqual(self.game.item("bow")["mode"],"fixed")
        self.assertEqual(self.game.item("bow")["price"],36)
        self.assertEqual(self.game.state["gold"],1000)

    def test_restock_and_return_conserve_items(self):
        before=self.totals()
        self.game.action("restock",{"slot":0,"quantity":2})
        self.assertEqual(self.game.item("greatsword")["quantity"],5)
        self.game.action("return_stock",{"slot":0})
        self.assertEqual(self.totals(),before)
        self.assertIsNone(self.game.state["shelves"][0])
        self.assertEqual(self.game.item("greatsword")["quantity"],0)

    def test_failed_replacement_rolls_back_returns_and_quantities(self):
        before=copy.deepcopy(self.game.state)
        for payload in (
            {"slot":0,"item_id":"bow","quantity":20,"mode":"fixed","price":65},
            {"slot":0,"item_id":"bow","quantity":2,"mode":"free","price":65},
            {"slot":0,"item_id":"longsword","quantity":2,"mode":"fixed","price":65},
        ):
            with self.assertRaises(ValueError):
                self.game.action("place_stock",payload)
            self.assertEqual(self.game.state,before)

    def test_storage_goods_are_not_customer_requests(self):
        self.game.action("finish_market",{})
        self.game.portraits=[x for x in self.game.portraits if x["weapon"]=="bow"]
        before=copy.deepcopy(self.game.state)
        with self.assertRaisesRegex(ValueError,"Restock"):
            self.game.action("arrive",{})
        self.assertEqual(self.game.state,before)
        self.game.action("place_stock",{"slot":0,"item_id":"bow","quantity":2,"mode":"bargain","price":48})
        self.game.action("arrive",{})
        self.assertEqual(self.game.customer()["wants"],"bow")
        self.game.action("begin",{"item_id":"bow"})
        self.assertEqual(self.game.state["deal"]["item_id"],"bow")

    def test_requests_choose_only_available_preferred_shelf_items(self):
        self.game.action("finish_market",{})
        self.game.portraits=[x for x in self.game.portraits if x["weapon"]=="hammer_shield"]
        for _ in range(10):
            self.game.action("arrive",{})
            self.assertEqual(self.game.customer()["wants"],"shield")
            self.game.action("leave",{})
        self.game.item("shield")["quantity"]=0
        self.game.action("next_day",{})
        with self.assertRaisesRegex(ValueError,"Restock"):
            self.game.action("arrive",{})
        self.assertIsNone(self.game.state["current_id"])

    def test_fixed_price_visitors_can_afford_and_accept_the_label(self):
        self.game.action("finish_market",{})
        for slot in range(len(self.game.state["shelves"])):
            self.game.action("return_stock",{"slot":slot})
        self.game.action("place_stock",{"slot":0,"item_id":"book","quantity":10,"mode":"fixed","price":20})
        for _ in range(10):
            self.game.action("arrive",{})
            c=self.game.customer()
            self.assertEqual(c["wants"],"book")
            self.assertGreaterEqual(c["budget"],20)
            self.game.action("begin",{"item_id":"book"})
            self.assertTrue(self.game.state["deal"]["sale_allowed"])
            self.game.action("cancel",{})
            self.game.action("leave",{})

    def test_arriving_cash_is_two_to_five_times_the_requested_price(self):
        self.game.action("finish_market",{})
        for mode in ("bargain","fixed"):
            for item in self.game.state["stock"]:
                item.update(mode=mode,price=item["cost"])
            for _ in range(10):
                if self.game.state["daily"]["closed"]:
                    self.game.action("next_day",{})
                self.game.action("arrive",{})
                c=self.game.customer()
                price=self.game.item(c["wants"])["price"]
                self.assertGreaterEqual(c["budget"],2*price)
                self.assertLessEqual(c["budget"],5*price)
                self.game.action("leave",{})

    def test_returning_cash_uses_this_visits_target_price(self):
        self.game.action("finish_market",{})
        self.game.action("arrive",{})
        previous=self.game.customer()
        previous["budget"]=99999
        identity=previous["id"]
        self.game.action("leave",{})
        for _ in range(3):
            with patch.object(self.game.rng,"random",return_value=1):self.game.action("arrive",{})
            self.game.action("leave",{})
        for item in self.game.state["stock"]:
            item.update(mode="bargain",price=20)
        with patch.object(self.game.rng,"random",return_value=0):
            self.game.action("arrive",{})
        self.assertEqual(self.game.customer()["id"],identity)
        self.assertGreaterEqual(self.game.customer()["budget"],40)
        self.assertLessEqual(self.game.customer()["budget"],100)

    def test_unaffordable_prices_do_not_consume_visitors_or_create_customers(self):
        self.game.action("finish_market",{})
        for item in self.game.state["stock"]:
            item.update(mode="fixed",price=99999)
        before=copy.deepcopy(self.game.state)
        with self.assertRaisesRegex(ValueError,"afford"):
            self.game.action("arrive",{})
        self.assertEqual(self.game.state,before)

    def test_bargain_admissions_always_have_a_valid_opening_offer(self):
        self.game.action("finish_market",{})
        for item in self.game.state["stock"]:
            item["mode"]="bargain"
        for _ in range(10):
            self.game.action("arrive",{})
            c=self.game.customer()
            self.game.action("begin",{"item_id":c["wants"]})
            self.assertEqual(self.game.state["deal"]["status"],"negotiating")
            self.assertIsNotNone(self.game.state["deal"]["offer"])
            self.game.action("leave",{})

    def test_ineligible_returning_customers_do_not_enter(self):
        self.game.action("finish_market",{})
        bow_portraits=[p for p in self.game.portraits if p["weapon"]=="bow"]
        old=self.game._new_customer(bow_portraits)
        old["visits"]=1
        with patch.object(self.game.rng,"random",return_value=0):
            self.game.action("arrive",{})
        self.assertNotEqual(self.game.customer()["id"],old["id"])
        self.assertIn(self.game.customer()["wants"],self.game.state["shelves"])
        self.assertEqual(old["visits"],1)

    def test_active_negotiation_locks_replacement_but_allows_restock(self):
        self.game.action("finish_market",{})
        self.game.action("arrive",{})
        self.game.customer()["budget"]=1000
        self.game.customer()["willingness"]["greatsword"]=1000
        self.game.action("begin",{"item_id":"greatsword"})
        before=copy.deepcopy(self.game.state)
        with self.assertRaises(ValueError):
            self.game.action("place_stock",{"slot":0,"item_id":"bow","quantity":2,"mode":"fixed","price":70})
        self.assertEqual(self.game.state,before)
        self.game.action("restock",{"slot":0,"quantity":1})
        self.assertEqual(self.game.item("greatsword")["quantity"],4)

    def test_storage_and_caravan_persist(self):
        self.game.action("merchant_buy",{"item_id":"book","quantity":2})
        restored=Game(ROOT / "assets",self.save)
        self.assertEqual(restored.state,self.game.state)

    def test_legacy_stock_migration_preserves_owned_counts(self):
        old=copy.deepcopy(self.game.state)
        for key in ("warehouse","shelves","shelf_capacity","caravan"):
            old.pop(key)
        old_counts={x["id"]:x["quantity"] for x in old["stock"]}
        self.save.write_text(json.dumps(old),encoding="utf-8")
        restored=Game(ROOT / "assets",self.save)
        self.assertEqual({x["id"]:x["quantity"]+restored.state["warehouse"][x["id"]] for x in restored.state["stock"]},old_counts)
        self.assertEqual(restored.state["gold"],old["gold"])


class LocalServerTest(unittest.TestCase):
    def test_http_flow_and_save_is_not_public(self):
        with tempfile.TemporaryDirectory() as folder:
            game = Game(ROOT / "assets", Path(folder) / "save.json", random.Random(3))
            stock_shop(game)
            game.state["caravan"]["open"] = False
            server = create_server(game)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with urlopen(base + "/api/state") as response:
                    data = json.load(response)
                payload = json.dumps({"action": "arrive"}).encode()
                headers = {"Content-Type": "application/json", "X-Game-Token": data["token"]}
                with urlopen(Request(base + "/api/action", data=payload, headers=headers)) as response:
                    result = json.load(response)
                self.assertIsNotNone(result["state"]["customer"])
                with urlopen(base + "/") as response:
                    self.assertIn(b"DUNGEON MERCHANT", response.read())
                for path in ("/game.py", "/saves/save.json", "/../game.py"):
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(base + path)
                    self.assertEqual(caught.exception.code, 404)
                    caught.exception.close()
                with self.assertRaises(HTTPError) as caught:
                    urlopen(Request(base + "/api/action", data=payload, headers={"Content-Type": "application/json"}))
                self.assertEqual(caught.exception.code, 403)
                caught.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)


if __name__ == "__main__":
    unittest.main()


class ManualSaveAndCaravanTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.path=Path(self.folder.name)/"save.json"
        self.game=Game(ROOT/"assets",self.path,random.Random(7),load_existing=False)
        self.game.action("allocate_attributes",{"allocation":{"luck":5}})

    def test_manual_save_persists_progress_without_advancing_time(self):
        self.game.state["gold"]=432
        self.game.action("save",{})
        saved=json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(saved,self.game.state)
        loaded=Game(ROOT/"assets",self.path)
        self.assertEqual(loaded.state["gold"],432)
        self.assertEqual(loaded.state["day"],1)
        self.assertEqual(loaded.state["daily"]["admitted"],0)

    def test_monday_revisits_preserve_stock_prices_and_purchase_history(self):
        self.game.action("merchant_buy",{"item_id":"longsword","quantity":1})
        wares=copy.deepcopy(self.game.state["caravan"])
        for _ in range(3):
            self.game.action("finish_market",{});self.game.action("visit_caravan",{})
            self.assertEqual(self.game.state["caravan"],wares)
        self.assertEqual(self.game.state["gold"],965)
        self.game.action("save",{})
        loaded=Game(ROOT/"assets",self.path)
        loaded.action("finish_market",{});loaded.action("visit_caravan",{})
        self.assertEqual(loaded.state["caravan"]["stock"],wares["stock"])
        self.assertEqual(loaded.state["caravan"]["purchases"],wares["purchases"])

    def test_caravan_requires_monday_and_open_day_without_customer(self):
        g=self.game;stock_shop(g);g.finish_market();g.arrive()
        with self.assertRaises(ValueError):g.action("visit_caravan",{})
        g.leave();g.skip_day()
        with self.assertRaises(ValueError):g.action("visit_caravan",{})
        g.next_day()
        with self.assertRaises(ValueError):g.action("visit_caravan",{})
