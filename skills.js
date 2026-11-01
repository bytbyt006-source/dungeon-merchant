// Talents use server-validated ranks, points and experience.
let skillGroup='Trading';
function renderSkills(){
 if(!state?.skills)return;
 const s=state.skills,open=$('#skillsOpen');open.replaceChildren(uiIcon('star'),document.createTextNode('Talents'+(s.points?' · '+s.points:'')));open.classList.add('label-icon-button');
 if(!$('#skillsDialog').open)return;
 const progress=element('progress');progress.max=100;progress.value=s.progress;progress.setAttribute('aria-label','Experience');progress.title='Sale +10 XP · Successful expedition +35 XP · Failed expedition +5 XP · Combat victory +25 XP';
 $('#skillProgress').replaceChildren(element('strong','Level '+s.level),iconStat('star',s.points,'Talent points'),element('span',s.progress+' / 100 XP'),progress);
 let tabs=$('#skillGroups');if(!tabs){tabs=element('div',undefined,'skill-groups');tabs.id='skillGroups';tabs.setAttribute('aria-label','Talent disciplines');$('#skillBranches').before(tabs);}tabs.replaceChildren();
 s.groups.forEach((group,i)=>{
  const selected=group===skillGroup,button=element('button',undefined,'label-icon-button');
  button.setAttribute('aria-pressed',String(selected));button.append(uiIcon(['hand','coin','map','shield','gear'][i]),document.createTextNode(group));
  const total=s.talents.filter(t=>t.group===group).reduce((sum,t)=>sum+s.ranks[t.id],0);button.append(element('small',total+' / '+s.talents.filter(t=>t.group===group).length*3));
  button.onclick=()=>{skillGroup=group;renderSkills();controls();};tabs.append(button);
 });
 const branches=$('#skillBranches');branches.replaceChildren();
 const talents=s.talents.filter(t=>t.group===skillGroup);branches.dataset.count=talents.length;
 talents.forEach(t=>{
  const branch=element('section',undefined,'skill-branch');branch.append(uiIcon(t.icon),element('h3',t.name));
  const allowed=!t.requires||s.ranks[t.requires]>=1,requirement=element('span',undefined,'skill-requirement');
  if(t.requires){const required=s.talents.find(x=>x.id===t.requires);requirement.append(uiIcon(allowed?'check':'lock'),document.createTextNode(required.name+' I'));}
  branch.append(requirement);
  t.effects.forEach((effect,index)=>{
   const rank=index+1,learned=s.ranks[t.id]>=rank,next=s.ranks[t.id]===index&&allowed;
   const node=element('button',undefined,'skill-node'+(learned?' learned':''));node.type='button';
   node.dataset.unavailable=String(!next||s.points<1);node.disabled=busy||!next||s.points<1;
   node.setAttribute('aria-label',t.name+' '+rank+' · '+effect+(learned?' · Learned':''));
   node.append(element('span',['I','II','III'][index],'skill-rank'),element('strong',t.nodes[index],'skill-node-name'),element('span',effect,'skill-effect'),uiIcon(learned?'check':next?'star':'lock'));
   if((s.effective_ranks?.[t.id]||0)>s.ranks[t.id])node.title='Equipment grants +'+(s.effective_ranks[t.id]-s.ranks[t.id]);
   else node.title=t.id==='pathfinder'?'Minimum journey: 1 day':t.id==='appraisal'?'Inspect equipment, accessories or manner before negotiating':t.id==='salvage'?'Loss chance when an expedition fails':effect;
   node.onclick=()=>act('learn_skill',{skill:t.id});branch.append(node);
  });branches.append(branch);
 });
}
$('#skillsOpen').onclick=()=>{$('#skillStatus').textContent='';$('#skillsDialog').showModal();renderSkills();controls();};
$('#skillsClose').onclick=()=>$('#skillsDialog').close();

function captureInventoryFlight(id){
 const mission=state.commission_board.missions.find(m=>m.id===id);
 const card=Array.from(document.querySelectorAll('[data-mission-id]')).find(c=>c.dataset.missionId===id);
 return (mission?.collectible_items||[]).map(drop=>{
  const view=Array.from(card?.querySelectorAll('[data-collectible-key]')||[]).find(v=>v.dataset.collectibleKey===drop.key);
  const rect=(view?.querySelector('img')||card||$('#commissionDialog')).getBoundingClientRect();
  return {...drop,x:rect.left+rect.width/2,y:rect.top+rect.height/2};
 });
}
async function animateInventoryCollection(items){
 if(!items.length)return;
 const layer=$('#inventoryFlights'),target=$('#warehouseOpen'),rect=target.getBoundingClientRect();
 const reduced=prefersReducedMotion(),animations=[];
 try{
  layer.showPopover();
  const beacon=target.cloneNode(true);beacon.removeAttribute('id');beacon.tabIndex=-1;beacon.classList.add('warehouse-beacon');
  Object.assign(beacon.style,{left:rect.left+'px',top:rect.top+'px',width:rect.width+'px',height:rect.height+'px'});layer.append(beacon);
  items.slice(0,12).forEach((item,index)=>{
   const art=element('img',undefined,'flying-item');art.src=item.src;art.alt='';art.style.left=item.x+'px';art.style.top=item.y+'px';layer.append(art);
   const dx=rect.left+rect.width/2-item.x,dy=rect.top+rect.height/2-item.y;
   const frames=reduced?[{opacity:1},{opacity:0}]:[{transform:'translate(-50%,-50%) scale(1)',opacity:1},{offset:.4,transform:`translate(${dx*.35}px,${dy*.5-65}px) scale(1.15)`,opacity:1},{transform:`translate(${dx}px,${dy}px) scale(.2)`,opacity:0}];
   animations.push(art.animate(frames,{duration:reduced?180:800,delay:reduced?0:index*70,easing:'ease-in-out',fill:'forwards'}).finished);
  });
  await Promise.allSettled(animations);
 }finally{layer.hidePopover();layer.replaceChildren();target.animate([{filter:'brightness(1.8)'},{filter:'brightness(1)'}],{duration:450});}
}
