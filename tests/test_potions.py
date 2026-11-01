"""Consumable trading, healing, and independent attack interruption."""
import random,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from game import Game
from shop_fixture import stock_shop
class PotionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.path=Path(self.tmp.name)/'save.json';self.g=Game(ROOT/'assets',self.path,random.Random(7),load_existing=False)
  self.g.state['creation']={'completed':True,'points':0,'allocated':{}}
 def test_purchase_stock_and_sale_transfers_potion_to_customer(self):
  g=self.g;g.action('merchant_buy',{'item_id':'life_potion','quantity':3})
  self.assertEqual(g.state['warehouse']['life_potion'],3)
  g.action('place_stock',{'slot':0,'item_id':'life_potion','quantity':2,'mode':'fixed','price':23});g.finish_market();g.arrive()
  self.assertEqual(g.customer()['wants'],'life_potion')
  g.begin('life_potion');g.accept()
  self.assertEqual(g.customer()['life_potions'],1)
  self.assertEqual(g.item('life_potion')['quantity'],1)
  self.assertEqual(g.state['warehouse']['life_potion'],1)
  self.assertIsNone(next(i for i in g.public()['stock'] if i['id']=='life_potion')['wear'])
 def test_healing_clamps_and_cannot_consume_at_full_or_zero_health(self):
  g=self.g;g.state['warehouse']['life_potion']=2;g.state['player_health']=90
  g.action('drink_potion',{});self.assertEqual(g.state['player_health'],100)
  self.assertEqual(g.state['warehouse']['life_potion'],1)
  with self.assertRaises(ValueError):g.action('drink_potion',{})
  g.state['player_health']=0
  with self.assertRaises(ValueError):g.action('drink_potion',{})
  self.assertEqual(g.state['warehouse']['life_potion'],1)
 def test_player_drink_restarts_only_own_attack_and_survives_reload(self):
  g=self.g;stock_shop(g);g.finish_market();g.arrive();g.start_combat(g.customer())
  g.state['player_health']=20;g.state['warehouse']['life_potion']=1
  f=g.state['combat'];f.update(player_next=101,enemy_next=102,last_tick=100)
  with patch('time.time',return_value=100.8):g.action('drink_potion',{})
  self.assertEqual(g.state['player_health'],60);self.assertEqual(f['enemy_next'],102)
  self.assertAlmostEqual(f['player_next'],100.8+f['player_interval'])
  restored=Game(ROOT/'assets',self.path)
  self.assertEqual(restored.state['warehouse']['life_potion'],0)
  self.assertEqual(restored.state['player_health'],60)
 def test_enemy_drinks_consumes_and_restarts_only_own_attack(self):
  g=self.g;stock_shop(g);g.finish_market();g.arrive();c=g.customer();g.start_combat(c)
  c.update(health=10,life_potions=1);f=g.state['combat'];f.update(player_next=105,enemy_next=101,last_tick=100)
  with patch('combat.time.time',return_value=100.8):g.action('combat_tick',{})
  self.assertEqual(c['health'],50);self.assertEqual(c['life_potions'],0)
  self.assertEqual(f['player_next'],105);self.assertAlmostEqual(f['enemy_next'],100.8+f['enemy_interval'])
  self.assertEqual(f['event_seq'],0)
 def test_old_save_gets_catalog_but_no_free_potions(self):
  g=self.g;g.state['stock']=[i for i in g.state['stock'] if i['id']!='life_potion'];g.state['warehouse'].pop('life_potion');g.save()
  loaded=Game(ROOT/'assets',self.path)
  self.assertEqual(loaded.state['warehouse']['life_potion'],0)
  self.assertEqual(loaded.item('life_potion')['quantity'],0)
