"""Authoritative sale-price bounds shared by labels and negotiation."""
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING

class PricingMixin:
 def sale_reference(self,item):
  # Zero-cost finds use their appraised wholesale value for price bounds.
  return item.get("acquisition_cost",item["cost"]) or item["cost"]

 def sale_cap(self,item,mode=None):
  percent=115 if (mode or item["mode"])=="fixed" else 150
  return max(1,int((Decimal(str(self.sale_reference(item)))*percent/100).to_integral_value(rounding=ROUND_FLOOR)))

 def bargain_base_difficulty(self,item,price):
  """At base Eloquence +3: 15-20% markup is 90%, 50% is 60%."""
  markup=max(Decimal(0),Decimal(price)/Decimal(str(self.sale_reference(item)))-1)
  if markup>Decimal("0.50"):
   return 12+int(((markup-Decimal("0.50"))*8).to_integral_value(rounding=ROUND_CEILING))
  if markup<=Decimal("0.15"):
   return 4+int((markup*2/Decimal("0.15")).to_integral_value(rounding=ROUND_CEILING))
  return 6+int((max(Decimal(0),markup-Decimal("0.20"))*20).to_integral_value(rounding=ROUND_CEILING))

 def quote_cap(self,item,customer=None):
  cap=min(99999,max(1,int(Decimal(str(self.sale_reference(item)))*20)))
  if not customer:return cap
  deal=self.state.get("deal")
  if not deal or deal["status"]!="negotiating":return min(cap,customer["budget"]+1)
  def impossible(price):
   return price>customer["budget"] or (price>deal["offer"] and self.difficulty(price)>20+self.effective_eloquence())
  if not impossible(cap):return cap
  low,high=1,cap
  while low<high:
   middle=(low+high)//2
   if impossible(middle):high=middle
   else:low=middle+1
  return low

 def validate_quote_price(self,item,price):
  cap=self.quote_cap(item)
  if price>cap:raise ValueError("Maximum offer: "+str(cap)+" gold.")

 def validate_sale_price(self,item,price,mode=None):
  cap=self.sale_cap(item,mode)
  if price>cap:raise ValueError("Maximum price: "+str(cap)+" gold.")

 def normalize_sale_prices(self):
  deal=self.state.get("deal")
  for item in self.state["stock"]:
   cap=self.sale_cap(item)
   item["price"]=min(item["price"],cap)
   saved=self.state["shelf_settings"].get(item["id"])
   if saved:saved["price"]=min(saved["price"],self.sale_cap(item,saved["mode"]))
   if deal and deal["item_id"]==item["id"] and deal["status"] not in ("sold","payment","declined"):
    changed=False
    for key in ["offer","last_quote","agreed"]:
     deal_cap=cap if key=="offer" or item["mode"]=="fixed" else self.quote_cap(item)
     if deal.get(key) and deal[key]>deal_cap:deal[key]=deal_cap;changed=True
    if changed:self.state["last_roll"]=None
    if changed:self.state["message"]=("Agreed. "+str(deal["agreed"])+" gold." if deal.get("agreed") else "My offer is "+str(deal["offer"])+" gold.")
