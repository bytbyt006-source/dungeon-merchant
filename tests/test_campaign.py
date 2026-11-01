"""Campaign completion, voluntary repayments and combat talent outcomes."""
import copy,json,random,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from game import Game
from shop_fixture import stock_shop
class CampaignTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
  self.path=Path(self.folder.name)/'save.json';self.g=Game(ROOT/'assets',self.path,random.Random(7),load_existing=False)
  stock_shop(self.g);self.g.finish_market();self.g.state['gold']=5000

 def test_early_repayment_updates_cash_principal_arrears_and_receipt(self):
  loan=self.g.state['loan'];loan['principal_arrears']=2000
  self.g.action('repay_early',{'amount':1500})
  self.assertEqual(self.g.state['gold'],3500);self.assertEqual(loan['balance'],18500)
  self.assertEqual(loan['principal_paid'],1500);self.assertEqual(loan['principal_arrears'],500)
  self.assertTrue(loan['payments'][-1]['early']);self.assertIsNone(self.g.public()['ending'])
  loaded=Game(ROOT/'assets',self.path);self.assertEqual(loaded.state['loan'],loan)

 def test_invalid_repayments_leave_state_unchanged(self):
  for amount in [0,-1,True,1.5,'abc',5001,100001]:
   before=copy.deepcopy(self.g.state)
   with self.assertRaises(ValueError):self.g.action('repay_early',{'amount':amount})
   self.assertEqual(self.g.state,before)

 def test_early_repayment_does_not_skip_the_next_monthly_installment(self):
  self.g.action('repay_early',{'amount':1000});self.g.state['day']=28
  self.g.action('skip_day',{})
  self.assertEqual(self.g.state['gold'],2800);self.assertEqual(self.g.state['loan']['balance'],18000)
  self.assertEqual(len(self.g.state['loan']['payments']),2)

 def test_final_payment_ends_campaign_and_cannot_be_repeated(self):
  self.g.state['loan'].update(balance=500,principal_paid=19500,principal_arrears=200)
  result=self.g.action('repay_early',{'amount':500})
  self.assertIsNone(result['ending']);self.assertEqual(result['final_boss']['status'],'waiting')
  self.assertEqual(self.g.state['gold'],4500)
  self.assertEqual(self.g.state['loan']['principal_arrears'],0)
  self.assertEqual(self.g.state['loan']['principal_paid'],20000)
  loaded=Game(ROOT/'assets',self.path);before=copy.deepcopy(loaded.state)
  for action,payload in [('repay_early',{'amount':1}),('next_day',{})]:
   with self.assertRaises(ValueError):loaded.action(action,payload)
  self.assertEqual(loaded.state,before)
  loaded.action('save',{});loaded.action('new_game',{})
  self.assertIsNone(loaded.public()['ending']);self.assertEqual(loaded.state['loan']['balance'],20000)

 def test_repayment_cannot_interrupt_a_customer(self):
  self.g.arrive()
  with self.assertRaises(ValueError):self.g.action('repay_early',{'amount':100})

 def test_combat_talent_stats_and_prerequisites(self):
  g=self.g;g.state['skills']['points']=20;base=g.player_stats()
  with self.assertRaises(ValueError):g.action('learn_skill',{'skill':'battle_tempo'})
  for name in ['weapon_mastery','iron_guard','footwork','battle_tempo']:
   g.action('learn_skill',{'skill':name})
  stats=g.player_stats();self.assertEqual(stats['attack'],base['attack']+3);self.assertEqual(stats['defense'],base['defense']+3)
  self.assertLess(stats['interval'],base['interval']);self.assertEqual(g.public()['equipment']['stats']['dodge'],3)
  loaded=Game(ROOT/'assets',self.path);self.assertEqual(loaded.player_stats(),stats)

 def test_critical_hit_second_wind_and_victory_xp_resolve_once(self):
  g=self.g;g.arrive();c=g.customer();g.ensure_belongings(c);c['health']=1
  g.state['skills']['ranks'].update(critical_strike=3,second_wind=2)
  g.state['player_health']=30;xp=g.state['skills']['xp']
  with patch('combat.time.time',return_value=100):g.start_combat(c)
  fight=g.state['combat'];fight.update(player_next=101,enemy_next=103)
  with patch('combat.time.time',return_value=101),patch.object(g.rng,'random',side_effect=[.999,.999,0]):
   g.combat_tick();g.combat_tick()
  self.assertEqual(fight['status'],'victory');self.assertTrue(fight['events'][0]['critical'])
  self.assertEqual(g.state['player_health'],50);self.assertEqual(g.state['skills']['xp'],xp+25)
  self.assertEqual(len(fight['events']),1)

 def test_footwork_changes_real_dodge_not_enemy_chance(self):
  g=self.g;g.arrive();c=g.customer();g.ensure_belongings(c)
  g.state['skills']['ranks']['footwork']=3
  self.assertEqual(g.dodge_percent(g.player_stats(),True),7)
  self.assertEqual(g.dodge_percent(g.player_stats(),False),1)
  with patch('combat.time.time',return_value=100):g.start_combat(c)
  g.state['combat'].update(enemy_next=101,player_next=103)
  with patch('combat.time.time',return_value=101),patch.object(g.rng,'random',return_value=.05):g.combat_tick()
  self.assertEqual(g.state['combat']['events'][0]['outcome'],'dodge');self.assertEqual(g.state['player_health'],100)


class EconomyMigrationTests(unittest.TestCase):
 def test_old_campaign_keeps_cash_goods_and_principal_credit_once(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'save.json';g=Game(ROOT/'assets',path,random.Random(7),load_existing=False)
   g.state['economy_version']=2;g.state['gold']=143
   g.state['loan'].update(original=100000,balance=88000,principal_paid=12000,principal_per_month=2000,principal_arrears=1500)
   g.state['warehouse']['longsword']=3;g.save()
   loaded=Game(ROOT/'assets',path)
   self.assertEqual(loaded.state['gold'],143);self.assertEqual(loaded.state['loan']['balance'],8000)
   self.assertEqual(loaded.state['loan']['principal_paid'],12000);self.assertEqual(loaded.state['loan']['principal_per_month'],1000)
   self.assertEqual(loaded.state['warehouse']['longsword'],3);loaded.save()
   again=Game(ROOT/'assets',path);self.assertEqual(again.state['loan'],loaded.state['loan'])
 def test_old_campaign_over_new_target_finishes_without_refunding_money(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'save.json';g=Game(ROOT/'assets',path,load_existing=False)
   g.state['economy_version']=2;g.state['gold']=91;g.state['loan'].update(original=100000,balance=75000,principal_paid=25000,principal_per_month=2000,principal_arrears=3000);g.save()
   loaded=Game(ROOT/'assets',path)
   self.assertEqual(loaded.state['gold'],91);self.assertEqual(loaded.state['loan']['balance'],0)
   self.assertEqual(loaded.state['loan']['principal_paid'],25000);self.assertEqual(loaded.state['loan']['principal_arrears'],0)
   self.assertIsNone(loaded.public()['ending']);self.assertEqual(loaded.public()['final_boss']['status'],'waiting')
 def test_new_game_has_final_starting_cash_and_no_free_stock(self):
  with tempfile.TemporaryDirectory() as folder:
   g=Game(ROOT/'assets',Path(folder)/'save.json',load_existing=False)
   self.assertEqual(g.state['gold'],1000);self.assertEqual(g.state['loan']['balance'],20000)
   self.assertEqual(g.state['loan']['principal_per_month'],1000);self.assertFalse(g.has_progress())
   self.assertEqual(sum(g.state['warehouse'].values()),0)
