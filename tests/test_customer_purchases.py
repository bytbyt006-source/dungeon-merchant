"""Buying a customer's carried equipment is an ownership and money transfer."""
import copy,random,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from game import Game
from shop_fixture import stock_shop
class CustomerPurchaseTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
  self.path=Path(self.folder.name)/'save.json';self.g=Game(ROOT/'assets',self.path,random.Random(7),load_existing=False)
  stock_shop(self.g);self.g.finish_market();self.g.arrive();self.g.inspect_belongings();self.c=self.g.customer()
  self.gear=self.g.make_gear('longsword','magic');self.gear['identified']=False;self.c['belongings']=[self.gear];self.c['purchased_gear']=[]

 def test_buy_transfers_exactly_one_item_and_price_and_persists(self):
  g=self.g;price=g.belongings_price(self.c,self.gear);cash=g.state['gold'];wallet=self.c['budget']
  shown=g.public()['customer']['belongings'][0];self.assertEqual(shown['buy_price'],price)
  g.action('buy_belonging',{'gear_id':self.gear['id']})
  self.assertEqual(g.state['gold'],cash-price);self.assertEqual(self.c['budget'],wallet+price)
  self.assertEqual(self.c['belongings'],[]);self.assertEqual(len(g.state['equipment_bag']),1)
  self.assertEqual(g.state['equipment_bag'][0]['id'],self.gear['id']);self.assertEqual(self.gear['paid_cost'],price)
  self.assertIn('Bought their',self.c['actions'][-1])
  loaded=Game(ROOT/'assets',self.path);self.assertEqual(loaded.state['equipment_bag'][0],self.gear)
  before=copy.deepcopy(g.state)
  with self.assertRaises(ValueError):g.action('buy_belonging',{'gear_id':self.gear['id']})
  self.assertEqual(g.state,before)

 def test_unidentified_purchased_item_can_be_equipped_when_attributes_suffice(self):
  self.g.state['player'].update(strength=4,dexterity=4,wisdom=2)
  self.g.action('buy_belonging',{'gear_id':self.gear['id']})
  self.assertFalse(self.gear['identified'])
  self.g.action('equip_gear',{'gear_id':self.gear['id']})
  self.assertEqual(self.g.state['loadout']['weapon']['id'],self.gear['id'])

 def test_purchase_does_not_bypass_wearing_requirements(self):
  self.g.action('buy_belonging',{'gear_id':self.gear['id']})
  before=copy.deepcopy(self.g.state)
  with self.assertRaises(ValueError):self.g.action('equip_gear',{'gear_id':self.gear['id']})
  self.assertEqual(self.g.state,before)

 def test_rejects_unseen_unaffordable_or_caught_customer_trades_atomically(self):
  for changes in [{'belongings_seen':False},{'trade_blocked_visit':self.c['visits']}]:
   original=copy.deepcopy(self.g.state);self.c.update(changes);before=copy.deepcopy(self.g.state)
   with self.assertRaises(ValueError):self.g.action('buy_belonging',{'gear_id':self.gear['id']})
   self.assertEqual(self.g.state,before);self.g.state=original;self.c=self.g.customer()
  self.g.state['gold']=0;before=copy.deepcopy(self.g.state)
  with self.assertRaises(ValueError):self.g.action('buy_belonging',{'gear_id':self.gear['id']})
  self.assertEqual(self.g.state,before)

 def test_buyback_price_exceeds_customer_last_payment(self):
  self.gear['customer_paid']=500
  self.assertGreaterEqual(self.g.belongings_price(self.c,self.gear),550)
  self.c['purchased_gear']=self.c['belongings'];self.c['belongings']=[]
  self.g.action('buy_belonging',{'gear_id':self.gear['id']})
  self.assertEqual(self.c['purchased_gear'],[])

 def test_pending_payment_or_combat_prevents_purchase(self):
  self.g.begin(self.c['wants']);self.g.state['deal'].update(status='payment',agreed=1)
  self.assertFalse(self.g.public()['customer']['can_buy_belongings'])
  with self.assertRaises(ValueError):self.g.action('buy_belonging',{'gear_id':self.gear['id']})
  self.g.state['deal']=None;self.g.confront_customer(self.c)
  with self.assertRaises(ValueError):self.g.action('buy_belonging',{'gear_id':self.gear['id']})
