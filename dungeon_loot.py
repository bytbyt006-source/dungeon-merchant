"""Region-exclusive rare equipment; identities and artwork survive transfers."""
import copy,uuid
SPECIAL_DROP_PERCENT=8
# Each piece uses an existing equipment family and its normal wearing attributes.
DUNGEON_GEAR={
 "cinderbreaker":{"name":"Cinderbreaker","region":"mine","base":"hammer","value":260,"affixes":[("Furnace-Forged","attack",12,"Attack +12"),("Balanced","haste",10,"Attack speed +10%"),("Ironbound","defense",4,"Defense +4")]},
 "deepwarden":{"name":"Deepwarden Plate","region":"mine","base":"plate_armour","value":310,"affixes":[("Bedrock","defense",8,"Defense +8"),("Enduring","max_hp",50,"Maximum health +50"),("Tempered","strength",2,"Strength +2")]},
 "fenfang":{"name":"Fenfang Bow","region":"marsh","base":"bow","value":275,"affixes":[("Venom-Tipped","attack",8,"Attack +8"),("Reedlight","haste",20,"Attack speed +20%"),("Stalker","dexterity",3,"Dexterity +3")]},
 "witch_eye":{"name":"Witch's Eye","region":"marsh","base":"amulet","value":290,"affixes":[("Foresight","dexterity",3,"Dexterity +3"),("Quicksilver","haste",15,"Attack speed +15%"),("Mistwalk","talent_footwork",1,"Evasive Footwork +1")]},
 "grave_lantern":{"name":"Grave Lantern","region":"crypt","base":"staff","value":330,"affixes":[("Soulfire","attack",14,"Attack +14"),("Ancestral","wisdom",3,"Wisdom +3"),("Sanctuary","defense",5,"Defense +5")]},
 "dawn_testament":{"name":"Dawn Testament","region":"crypt","base":"book","value":350,"affixes":[("Consecrated","attack",10,"Attack +10"),("Martyr","max_hp",40,"Maximum health +40"),("Renewal","talent_second_wind",1,"Second Wind +1")]},
}
def reward_view(key):
 item=DUNGEON_GEAR[key]
 return {"id":key,"name":item["name"],"src":"assets/items/"+key+".png","quality":"rare"}
def make_dungeon_gear(key):
 item=DUNGEON_GEAR[key]
 return {"id":uuid.uuid4().hex,"item_id":item["base"],"signature_id":key,"signature_name":item["name"],"signature_src":reward_view(key)["src"],"signature_value":item["value"],"quality":"rare","paid_cost":0,"identified":True,
  "affixes":[{"name":name,"stat":stat,"value":value,"text":text} for name,stat,value,text in item["affixes"]]}
