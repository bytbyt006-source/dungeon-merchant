"""A fresh campaign journey through actual saved actions, without stocked fixtures."""
import json,random,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from game import Game
class FreshCampaignJourney(unittest.TestCase):
 def test_purchase_wear_display_sell_reload_collect_and_expedition(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'save.json';g=Game(ROOT/'assets',path,random.Random(7),load_existing=False)
   self.assertEqual(sum(g.state['warehouse'].values()),0)
   g.action('allocate_attributes',{'allocation':{'strength':2,'dexterity':1,'wisdom':1,'eloquence':1}})
   g.action('finish_intro',{})
   for item,count in [('longsword',2),('leather_armour',1),('staff',1),('book',1)]:g.action('merchant_buy',{'item_id':item,'quantity':count})
   g.action('equip_gear',{'item_id':'longsword'})
   self.assertEqual(g.state['loadout']['weapon']['item_id'],'longsword')
   for slot,item in enumerate(['longsword','staff','book']):
    g.action('place_stock',{'slot':slot,'item_id':item,'quantity':1,'mode':'fixed','price':g.sale_cap(g.item(item),'fixed')})
   g.action('finish_market',{});g.action('save',{});g.action('visit_caravan',{});g.action('finish_market',{})
   g.action('arrive',{});cid=g.state['current_id'];wanted=g.customer()['wants'];gold=g.state['gold']
   g.action('begin',{'item_id':wanted});agreed=g.state['deal']['agreed']
   g.action('prepare_payment',{});self.assertEqual(g.state['gold'],gold)
   g=Game(ROOT/'assets',path,random.Random(23));self.assertEqual(g.state['deal']['status'],'payment')
   g.action('collect_payment',{});self.assertEqual(g.state['gold'],gold+agreed)
   self.assertIsNone(g.state['shelves'][['longsword','staff','book'].index(wanted)])
   with self.assertRaises(ValueError):g.action('collect_payment',{})
   g.action('leave',{});g.action('dispatch_commission',{'customer_id':cid,'region_id':'mine'})
   mission=g.state['commissions'][0]
   for _ in range(2):g.action('skip_day',{});g.action('next_day',{})
   self.assertEqual(mission['status'],'returned')
   g.action('claim_commission',{'mission_id':mission['id']})
   self.assertEqual(mission['status'],'claimed')
   if not mission['success']:self.assertEqual(mission['equipment_loot'],[])
   with self.assertRaises(ValueError):g.action('claim_commission',{'mission_id':mission['id']})
   g.action('save',{});saved=json.loads(path.read_text(encoding='utf-8'))
   self.assertEqual(saved,g.state)
   loaded=Game(ROOT/'assets',path)
   self.assertEqual(loaded.state['warehouse'],g.state['warehouse'])
   self.assertEqual(loaded.state['loadout'],g.state['loadout'])
