"""Individual equipment, identification, modifiers and storage transfers."""
import copy
import math
import random
import uuid

ACCESSORIES = [
 {"id":"ring","name":"Ruby Signet","category":"accessory","mode":"fixed","cost":22,"price":48,"quantity":6},
 {"id":"amulet","name":"Sun Amulet","category":"accessory","mode":"bargain","cost":30,"price":70,"quantity":6},
 {"id":"charm","name":"Raven Talisman","category":"accessory","mode":"fixed","cost":16,"price":36,"quantity":6},
]
BASE = {
 "greatsword":("weapon",25,0,3.2),"longsword":("weapon",16,0,2.0),"hammer":("weapon",23,0,3.0),
 "staff":("weapon",18,0,2.6),"book":("weapon",15,0,2.8),"bow":("weapon",14,0,1.8),
 "shield":("armour",0,10,0),"leather_armour":("armour",0,6,0),"chainmail":("armour",0,12,0),
 "plate_armour":("armour",0,18,0),"mage_robes":("armour",0,4,0),"cleric_robes":("armour",0,5,0),
 "ring":("accessory",0,1,0),"amulet":("accessory",0,1,0),"charm":("accessory",0,0,0),
}
QUALITY = {"common":("Common",0),"magic":("Magic",3),"rare":("Rare",6),"legendary":("Legendary",10)}
# Attribute families are fixed by equipment type, independent of rarity.
WEAR_REQUIREMENTS = {
 "greatsword":{"strength":3}, "hammer":{"strength":3},
 "longsword":{"strength":2,"dexterity":2}, "bow":{"dexterity":3},
 "staff":{"wisdom":2}, "book":{"strength":1,"wisdom":2},
 "shield":{"strength":2}, "leather_armour":{"dexterity":2},
 "chainmail":{"strength":3,"dexterity":2}, "plate_armour":{"strength":4},
 "mage_robes":{"dexterity":1,"wisdom":2}, "cleric_robes":{"strength":1,"wisdom":2},
 "ring":{"dexterity":2,"wisdom":1}, "amulet":{"wisdom":2},
 "charm":{"strength":1,"dexterity":2,"wisdom":2},
}
QUALITY_REQUIREMENT_BONUS = {"common":0,"magic":2,"rare":5,"legendary":8}

AFFIXES = [
 ("Brawny","strength",2,"Strength +2"),
 ("Mighty","attack",4,"Attack +4"),("Warding","defense",3,"Defense +3"),
 ("Stalwart","max_hp",20,"Maximum health +20"),("Learned","wisdom",2,"Wisdom +2"),
 ("Nimble","dexterity",2,"Dexterity +2"),("Persuasive","eloquence",1,"Persuasion +1"),
 ("Swift","haste",10,"Attack speed +10%"),("Trailwise","expedition",1,"Expedition rolls +1"),
 ("Insightful","talent_appraisal",1,"Merchant's Eye +1"),
 ("Fortunate","talent_fortune",1,"Bountiful Expeditions +1"),
 ("Patient","talent_patience",1,"Patient Company +1"),
 ("Connected","talent_supplier",1,"Merchant Connections +1"),
]

class EquipmentMixin:
 def _upgrade_equipment(self):
  self.state["player"].setdefault("strength",2)
  self.state["player"].setdefault("dexterity",2)
  self.state.setdefault("equipment_bag",[])
  self.state.setdefault("loadout",{"weapon":None,"armour":None,"accessory1":None,"accessory2":None})
  self.state.setdefault("player_health",100)
  self.state.setdefault("combat",None)
  self.state.setdefault("equipment_version",1)
  if self.state["combat"]:
   self.state["combat"].setdefault("id",uuid.uuid4().hex)
   self.state["combat"].setdefault("event_seq",0)
   self.state["combat"].setdefault("events",[])
  caravan=self.state["caravan"]
  if "gear_stock" not in caravan:
   source=random.Random("caravan:"+str(caravan["day"]))
   caravan["gear_stock"]=[]
   for _ in range(4):
    chance=source.randrange(100)
    caravan["gear_stock"].append(self.make_gear(source.choice(list(BASE)),"magic" if chance<70 else "rare" if chance<95 else "legendary",rng=source))
   for gear in caravan["gear_stock"]:gear["price"]=self.gear_value(gear)
  all_gear=self.state["equipment_bag"]+[g for g in self.state["loadout"].values() if g]+caravan["gear_stock"]
  all_gear += [item["gear"] for item in self.state["stock"] if item.get("gear")]
  for customer in self.state["customers"].values():all_gear += customer.get("belongings",[])+customer.get("purchased_gear",[])
  for gear in all_gear:
   if gear["quality"]=="common":gear["identified"]=True
  self._upgrade_wear_requirements()

 def make_gear(self,item_id,quality=None,rng=None):
  source=rng or self.rng
  if quality is None:
   n=source.randrange(100)
   quality="common" if n<55 else "magic" if n<85 else "rare" if n<98 else "legendary"
  if quality not in QUALITY or item_id not in BASE:raise ValueError("Unknown equipment.")
  count={"common":0,"magic":source.choice([1,2]),"rare":source.choice([3,4]),"legendary":3}[quality]
  affixes=[{"name":name,"stat":stat,"value":value,"text":text} for name,stat,value,text in source.sample(AFFIXES,count)]
  if quality=="legendary":affixes.append({"name":"Heirloom","stat":"legendary","value":1,"text":"Heirloom: Attack +8 · Defense +5 · Expedition +2"})
  return {"id":uuid.uuid4().hex,"item_id":item_id,"quality":quality,"affixes":affixes,"identified":True}

 def gear_value(self,gear):
  if gear.get("signature_value"):return gear["signature_value"]
  return math.ceil(self.item(gear["item_id"])["cost"]*{"common":1.2,"magic":2,"rare":4,"legendary":9}[gear["quality"]])

 def gear_modifiers(self,gear):
  mods={}
  if not gear:return mods
  for affix in gear["affixes"]:
   stat=affix["stat"]
   if stat=="legendary":
    for key,value in [("attack",8),("defense",5),("expedition",2)]:mods[key]=mods.get(key,0)+value
   else:mods[stat]=mods.get(stat,0)+affix["value"]
  return mods

 def equipped_modifier(self,key):
  return sum(self.gear_modifiers(g).get(key,0) for g in self.state.get("loadout",{}).values() if g)

 def player_stats(self,loadout=None):
  """Combine base attributes, worn equipment and talent modifiers."""
  loadout=loadout if loadout is not None else self.state["loadout"]
  mods={}
  for gear in loadout.values():
   for key,value in self.gear_modifiers(gear).items():mods[key]=mods.get(key,0)+value
  weapon=loadout["weapon"]
  attack=BASE[weapon["item_id"]][1] if weapon else 5
  interval=BASE[weapon["item_id"]][3] if weapon else 2.2
  defense=2+sum(BASE[g["item_id"]][2] for g in loadout.values() if g)
  strength=self.state["player"].get("strength",2)+3*self.skill_rank("strength_training")+mods.get("strength",0)
  maximum=80+strength*10+mods.get("max_hp",0)
  return {"max_hp":maximum,"hp":min(self.state["player_health"],maximum),"attack":attack+strength*2+mods.get("attack",0)+3*self.skill_rank("weapon_mastery"),
          "defense":defense+mods.get("defense",0)+3*self.skill_rank("iron_guard"),"interval":round(max(.6,interval/(1+(mods.get("haste",0)+5*self.skill_rank("battle_tempo"))/100)),2),
          "wisdom":self.state["player"]["wisdom"]+3*self.skill_rank("scholar")+mods.get("wisdom",0),
          "strength":strength,"dexterity":self.state["player"].get("dexterity",2)+3*self.skill_rank("agility_training")+mods.get("dexterity",0),"expedition":mods.get("expedition",0)}

 def dodge_percent(self,stats,player=False):
  return min(100,max(0,stats["dexterity"]*.5+(2*self.skill_rank("footwork") if player else 0)))

 def wear_requirements(self,gear):
  bonus=QUALITY_REQUIREMENT_BONUS[gear["quality"]]
  return {stat:value+bonus for stat,value in WEAR_REQUIREMENTS[gear["item_id"]].items()}

 def loadout_failures(self,loadout):
  stats=self.player_stats(loadout)
  failures=[]
  for slot,gear in loadout.items():
   if not gear:continue
   own=self.gear_modifiers(gear)
   for stat,required in self.wear_requirements(gear).items():
    available=stats[stat]-own.get(stat,0)
    if available<required:failures.append({"slot":slot,"stat":stat,"required":required,"available":available})
  return failures

 def shift_max_health(self,old_max):
  old_hp=self.state["player_health"]
  new_max=self.player_stats()["max_hp"]
  self.state["player_health"]=(max(1,min(new_max,old_hp+new_max-old_max)) if old_hp>0 else 0)

 def _upgrade_wear_requirements(self):
  if self.state.get("wear_requirements_version",0)>=2:return
  if self.state.get("combat") and self.state["combat"]["status"]=="active":return
  old_max=self.player_stats()["max_hp"]
  moved=[]
  while True:
   failures=self.loadout_failures(self.state["loadout"])
   if not failures:break
   slot=failures[0]["slot"]
   gear=self.state["loadout"][slot]
   self.state["equipment_bag"].append(gear);self.state["loadout"][slot]=None
   moved.append(self.item(gear["item_id"])["name"])
  self.shift_max_health(old_max)
  self.state["wear_requirements_version"]=2
  if moved:self.state["equipment_notice"]="Moved to storage: "+", ".join(moved)

 def gear_public(self,gear,reveal=True):
  """Expose visible properties and calculate wearing requirements for each slot."""
  data=copy.deepcopy(gear);item=self.item(gear["item_id"])
  known=gear["quality"]=="common" or reveal or gear.get("identified",False)
  data.update(name=gear.get("signature_name") if known and gear.get("signature_name") else ((gear["affixes"][0]["name"]+" ") if gear["affixes"] and known else "")+item["name"],
              slot=BASE[gear["item_id"]][0],requirement=QUALITY[gear["quality"]][1],
              identification_wisdom=QUALITY[gear["quality"]][1],requirements=self.wear_requirements(gear),
              src=gear.get("signature_src","assets/items/"+gear["item_id"]+".png"),identified=known)
  options=["accessory1","accessory2"] if data["slot"]=="accessory" else [data["slot"]]
  data["equip_options"]={};data["equip_failures"]={}
  for slot in options:
   proposed=copy.deepcopy(self.state["loadout"]);proposed[slot]=gear
   failures=self.loadout_failures(proposed)
   data["equip_options"][slot]=not failures
   data["equip_failures"][slot]=failures
  if not known:data["affixes"]=[]
  data["attack"],data["defense"],data["interval"]=BASE[gear["item_id"]][1:]
  return data

 def equip_gear(self,gear_id=None,item_id=None,slot=None):
  """Validate the complete proposed loadout before moving either equipment item."""
  self.require_peace()
  if gear_id:
   gear=next((g for g in self.state["equipment_bag"] if g["id"]==gear_id),None)
   if not gear:raise ValueError("Equipment is not in your warehouse.")
  else:
   if self.state["warehouse"].get(item_id,0)<1:raise ValueError("No equipment in storage.")
   listing=self.item(item_id)
   gear=copy.deepcopy(listing["gear"]) if listing.get("gear") else self.make_gear(item_id,"common")
  kind=BASE[gear["item_id"]][0]
  slot=slot or ("accessory1" if kind=="accessory" else kind)
  if slot not in self.state["loadout"] or ("accessory" if slot.startswith("accessory") else slot)!=kind:
   raise ValueError("Choose the matching equipment slot.")
  loadout=copy.deepcopy(self.state["loadout"]);loadout[slot]=gear
  failures=self.loadout_failures(loadout)
  if failures:
   failure=failures[0]
   raise ValueError(f"{failure['stat'].title()} {failure['required']} required ({failure['available']} available).")
  old_max=self.player_stats()["max_hp"]
  old=self.state["loadout"][slot]
  if old:self.state["equipment_bag"].append(old)
  if gear_id:self.state["equipment_bag"].remove(gear)
  else:self.state["warehouse"][item_id]-=1
  self.state["loadout"][slot]=gear
  self.shift_max_health(old_max)

 def unequip_gear(self,slot):
  self.require_peace()
  if slot not in self.state["loadout"]:raise ValueError("Unknown equipment slot.")
  gear=self.state["loadout"][slot]
  if not gear:return
  updated=copy.deepcopy(self.state["loadout"]);updated[slot]=None
  if self.loadout_failures(updated):raise ValueError("Other equipment depends on this item's attributes.")
  old_max=self.player_stats()["max_hp"]
  self.state["loadout"][slot]=None;self.state["equipment_bag"].append(gear)
  self.shift_max_health(old_max)

 def stock_gear(self,gear_id):
  self.require_peace()
  gear=next((g for g in self.state["equipment_bag"] if g["id"]==gear_id),None)
  if not gear:raise ValueError("Equipment is not in storage.")
  item_id="gear_"+gear["id"]
  listing=next((item for item in self.state["stock"] if item["id"]==item_id),None)
  if listing and (listing["quantity"] or self.state["warehouse"].get(item_id,0)):raise ValueError("This item is already stocked.")
  if listing is None:
   base=self.item(gear["item_id"])
   value=self.gear_value(gear)
   listing={"id":item_id,"base_id":gear["item_id"],"name":self.gear_public(gear,gear.get("identified",True))["name"],
      "mode":"bargain","price":value,"cost":value,"acquisition_cost":gear.get("paid_cost",gear.get("price",base["cost"])),
      "quantity":0,"category":base.get("category","weapon"),"gear":copy.deepcopy(gear)}
   self.state["stock"].append(listing)
  else:
   listing["gear"]=copy.deepcopy(gear)
   listing["name"]=self.gear_public(gear,gear.get("identified",True))["name"]
   listing["acquisition_cost"]=gear.get("paid_cost",gear.get("price",self.item(gear["item_id"])["cost"]))
  self.state["warehouse"][item_id]=1
  self.state["equipment_bag"].remove(gear)
  for c in self.state["customers"].values():c["willingness"][item_id]=min(c["budget"],listing["cost"]*2)

 def buy_gear(self,gear_id):
  self.require_peace()
  if not self.state["caravan"]["open"]:raise ValueError("The caravan has departed.")
  listing=next((g for g in self.state["caravan"]["gear_stock"] if g["id"]==gear_id),None)
  if not listing:raise ValueError("This equipment has been sold.")
  price=self.merchant_price(listing["price"])
  if self.state["gold"]<price:raise ValueError("Not enough gold.")
  self.state["gold"]-=price;self.state["caravan"]["gear_stock"].remove(listing)
  owned=copy.deepcopy(listing);owned["paid_cost"]=price
  self.state["equipment_bag"].append(owned)
  self.state["caravan"]["purchases"].append({"id":uuid.uuid4().hex,"item_id":listing["item_id"],"quantity":1,"unit_cost":price,"total":price})

 def ensure_belongings(self,c):
  if "belongings" not in c:
   source=random.Random(c["id"]+":belongings")
   prefs=self.professions[c["weapon_type"]]["preferred_items"]
   weapon=next((x for x in prefs if x in BASE and BASE[x][0]=="weapon"),"longsword")
   armour=next((x for x in prefs if x in BASE and BASE[x][0]=="armour"),"leather_armour")
   c["belongings"]=[self.make_gear(x,rng=source) for x in [weapon,armour,source.choice(["ring","amulet","charm"])]]
   for gear in c["belongings"]:gear["identified"]=gear["quality"]=="common"
  if "health" not in c:c["health"]=self.customer_stats(c)["max_hp"]

 def customer_stats(self,c):
  if c.get("final_boss"):return self.boss_stats(c)
  gear=c.get("belongings",[])
  mods={}
  for g in gear:
   for key,value in self.gear_modifiers(g).items():mods[key]=mods.get(key,0)+value
  weapon=next((g for g in gear if BASE[g["item_id"]][0]=="weapon"),None)
  attributes={stat:max([2]+[self.wear_requirements(g).get(stat,0) for g in gear])+mods.get(stat,0) for stat in ["strength","dexterity","wisdom"]}
  maximum=65+attributes["strength"]*10+mods.get("max_hp",0)
  return {**attributes,"max_hp":maximum,"hp":min(c.get("health",maximum),maximum),
          "attack":(BASE[weapon["item_id"]][1] if weapon else 5)+attributes["strength"]*2+mods.get("attack",0),
          "defense":2+sum(BASE[g["item_id"]][2] for g in gear)+mods.get("defense",0),
          "interval":round(max(.6,(BASE[weapon["item_id"]][3] if weapon else 2.2)/(1+mods.get("haste",0)/100)),2)}

 def inspect_belongings(self):
  self.require_peace();c=self.customer();self.ensure_belongings(c);c["belongings_seen"]=True
  c["actions"].append("Examined their belongings.")

 def can_buy_belongings(self,c):
  return (self.can_attempt_theft(c) and c.get("belongings_seen",False)
          and c.get("trade_blocked_visit")!=c["visits"])

 def belongings_price(self,c,gear):
  # A buyback cannot cost less than the amount the customer just paid.
  value=max(self.gear_value(gear),gear.get("customer_paid",0))
  percent={"patient":110,"proud":125,"impatient":120}[c["personality"]]
  return math.ceil(value*percent/100)

 def buy_belonging(self,gear_id):
  self.require_peace();c=self.customer();self.ensure_belongings(c)
  if not self.can_buy_belongings(c):raise ValueError("This customer is not offering equipment right now.")
  source=next((items for items in [c["belongings"],c.get("purchased_gear",[])] if any(g["id"]==gear_id for g in items)),None)
  if source is None:raise ValueError("That item is no longer carried.")
  gear=next(g for g in source if g["id"]==gear_id)
  price=self.belongings_price(c,gear)
  if self.state["gold"]<price:raise ValueError("Not enough gold.")
  source.remove(gear);gear["paid_cost"]=price
  self.state["gold"]-=price;c["budget"]+=price
  self.state["equipment_bag"].append(gear)
  c["health"]=min(c["health"],self.customer_stats(c)["max_hp"])
  name=self.gear_public(gear,gear.get("identified",False))["name"]
  c["actions"].append("Bought their "+name+" for "+str(price)+" gold.")
  self.state["message"]="Bought "+name+" for "+str(price)+" gold."

 def identify_gear(self,gear_id):
  """Reveal affixes when Wisdom is sufficient; wearing is validated separately."""
  self.require_peace()
  c=self.state["customers"].get(self.state["current_id"])
  stocked=[item["gear"] for item in self.state["stock"] if item.get("gear") and (item["quantity"] or self.state["warehouse"].get(item["id"],0))]
  candidates=self.state["equipment_bag"]+[g for g in self.state["loadout"].values() if g]+stocked+(c.get("belongings",[])+c.get("purchased_gear",[]) if c and c.get("belongings_seen") else [])
  gear=next((g for g in candidates if g["id"]==gear_id),None)
  if not gear:raise ValueError("No such equipment to identify.")
  if self.player_stats()["wisdom"]<QUALITY[gear["quality"]][1]:raise ValueError("You need more Wisdom to identify this equipment.")
  gear["identified"]=True
  for item in self.state["stock"]:
   if item.get("gear",{}).get("id")==gear_id:
    item["gear"]["identified"]=True
    item["name"]=self.gear_public(gear)["name"]

 def equipment_public(self):
  return {"notice":self.state.get("equipment_notice",""),"common_requirements":WEAR_REQUIREMENTS,"stats":dict(self.player_stats(),dodge=self.dodge_percent(self.player_stats(),True),block=min(100,self.player_stats()["defense"]*.5)),"loadout":{slot:self.gear_public(g,g.get("identified",True)) if g else None for slot,g in self.state["loadout"].items()},
          "bag":[self.gear_public(g,g.get("identified",True)) for g in self.state["equipment_bag"]]}

 def require_peace(self):
  if self.state.get("combat",{} ) and self.state["combat"]["status"] in ("threatened","ready","active"):raise ValueError("Finish the fight first.")
  if self.state.get("player_health",100)<=0:raise ValueError("Rest until the next day before taking action.")
