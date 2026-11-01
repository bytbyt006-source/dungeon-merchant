"""Portrait diversity applies to both new identities and returning customers."""
import random,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from game import Game
from shop_fixture import stock_shop
class ArrivalVarietyTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
  self.path=Path(self.folder.name)/'save.json';self.g=Game(ROOT/'assets',self.path,random.Random(7),load_existing=False)
  stock_shop(self.g);self.g.finish_market()
 def next_visitor(self):
  if self.g.state['daily']['closed']:
   self.g.next_day()
   if self.g.state['caravan']['open']:self.g.finish_market()
  self.g.arrive();c=self.g.customer();snapshot=(c['id'],c['portrait']);self.g.leave();return snapshot
 def test_ordinary_and_returning_visitors_avoid_last_three_portraits(self):
  seen=[];returns=0
  for _ in range(80):
   cid,portrait=self.next_visitor()
   self.assertNotIn(portrait,[p for _,p in seen[-3:]])
   self.assertNotIn(cid,[i for i,_ in seen[-3:]])
   returns+=cid in [i for i,_ in seen];seen.append((cid,portrait))
  self.assertGreater(returns,0);self.assertGreater(len({p for _,p in seen}),15)
 def test_single_class_display_still_has_multiple_races_and_portraits(self):
  for slot in range(4):self.g.return_stock(slot)
  self.g.place_stock(0,'staff',10,'bargain',40)
  seen=[]
  for _ in range(40):
   cid,portrait=self.next_visitor();self.assertNotIn(portrait,seen[-3:]);seen.append(portrait)
  self.assertEqual(len(set(seen)),7)
 def test_two_available_portraits_relax_window_without_back_to_back_repeats(self):
  self.g.portraits=[p for p in self.g.portraits if p["weapon"]=="staff"][:2];seen=[]
  for _ in range(20):
   _,portrait=self.next_visitor()
   if seen:self.assertNotEqual(portrait,seen[-1])
   seen.append(portrait)
 def test_only_one_portrait_does_not_block_admission(self):
  self.g.portraits=[next(p for p in self.g.portraits if p["weapon"]=="staff")]
  visits=[self.next_visitor() for _ in range(12)]
  self.assertEqual(len({portrait for _,portrait in visits}),1)
  for i in range(1,len(visits)):self.assertNotEqual(visits[i][0],visits[i-1][0])
 def test_variety_history_survives_save_reload_and_day_change(self):
  seen=[]
  for _ in range(14):
   visitor=self.next_visitor();self.assertNotIn(visitor[1],[p for _,p in seen[-3:]]);seen.append(visitor)
   self.g.save();self.g=Game(ROOT/'assets',self.path,random.Random(7))
  self.assertLessEqual(len(self.g.state['arrival_history']),12)
 def test_returning_expedition_waits_for_spacing_then_gets_priority(self):
  cid,portrait=self.next_visitor();c=self.g.state['customers'][cid];c['commission_return_visit']=True
  for _ in range(3):
   with patch.object(self.g.rng,'random',return_value=1):new_id,new_portrait=self.next_visitor()
   self.assertNotEqual(new_id,cid);self.assertNotEqual(new_portrait,portrait)
   self.assertTrue(c['commission_return_visit'])
  with patch.object(self.g.rng,'random',return_value=1):new_id,_=self.next_visitor()
  self.assertEqual(new_id,cid);self.assertNotIn('commission_return_visit',c)
 def test_changing_display_does_not_leave_old_portrait_filters_stuck(self):
  for _ in range(5):self.next_visitor()
  for slot in range(4):self.g.return_stock(slot)
  self.g.place_stock(0,'book',10,'bargain',25)
  for _ in range(5):
   cid,_=self.next_visitor();self.assertEqual(self.g.state['customers'][cid]['weapon_type'],'prayer_book')
