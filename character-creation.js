// Five one-time starting points; the Python rules validate and persist confirmation.
const START_ATTRIBUTES=[['strength','Strength','gear','Health and attack'],['dexterity','Dexterity','hand','Dodge and theft'],['wisdom','Wisdom','scroll','Identification and equipment'],['eloquence','Eloquence','d20','Bargaining and mercy'],['luck','Luck','star','Theft rolls']];
let startingAllocation={},creationSubmitting=false;
function openCharacterCreation(){
 if(state.creation?.completed){playPrologue();return;}
 startingAllocation=Object.fromEntries(START_ATTRIBUTES.map(([key])=>[key,0]));
 document.querySelectorAll('dialog[open]').forEach(dialog=>dialog.close());$('#creationStatus').textContent='';
 const host=$('#creationAttributes');host.replaceChildren();
 for(const [key,label,icon,description] of START_ATTRIBUTES){
  const row=element('section',undefined,'creation-attribute'),heading=element('div',undefined,'creation-attribute-label');heading.append(uiIcon(icon),element('strong',label),element('small',description));
  const value=element('strong',undefined,'creation-total');value.id='startingTotal-'+key;
  const input=element('input');input.id='starting-'+key;input.type='range';input.min='0';input.max='5';input.step='1';input.value='0';input.setAttribute('aria-label',label+' points');
  row.append(heading,value,input);host.append(row);addNumberStepper(input,label+' points');
  input.oninput=()=>{const other=Object.entries(startingAllocation).reduce((sum,[name,value])=>sum+(name===key?0:value),0);startingAllocation[key]=Math.max(0,Math.min(Number(input.value),state.creation.points-other));updateCharacterCreation();};
 }
 updateCharacterCreation();$('#creationDialog').showModal();
}
function updateCharacterCreation(){
 const used=Object.values(startingAllocation).reduce((sum,value)=>sum+value,0),left=state.creation.points-used;
 $('#creationRemaining').textContent=left+' points remaining';
 for(const [key] of START_ATTRIBUTES){
  const input=$('#starting-'+key);input.max='5';input.value=String(startingAllocation[key]);input.disabled=creationSubmitting;
  $('#startingTotal-'+key).textContent=state.creation.base[key]+startingAllocation[key];
 }
 const strength=state.creation.base.strength+startingAllocation.strength,dexterity=state.creation.base.dexterity+startingAllocation.dexterity;
 $('#creationPreview').replaceChildren(element('span',(80+strength*10)+' HP'),element('span','Dodge '+(dexterity*.5)+'%'),element('span','Eloquence +'+(state.creation.base.eloquence+startingAllocation.eloquence)));
 $('#creationConfirm').disabled=creationSubmitting||left!==0;$('#creationBack').disabled=creationSubmitting;refreshNumberControls();
 for(const [key] of START_ATTRIBUTES){const host=$('#starting-'+key).parentElement;host.querySelectorAll('button[data-delta]').forEach(button=>button.disabled=creationSubmitting||(Number(button.dataset.delta)>0?left===0:startingAllocation[key]===0));}
}
$('#creationConfirm').onclick=async()=>{
 if(creationSubmitting)return;creationSubmitting=true;updateCharacterCreation();
 try{const data=await request({action:'allocate_attributes',allocation:{...startingAllocation}});state=data.state;$('#creationDialog').close();render();playPrologue();}
 catch(error){$('#creationStatus').textContent=error.message;}
 finally{creationSubmitting=false;if($('#creationDialog').open)updateCharacterCreation();}
};
$('#creationBack').onclick=()=>{$('#creationDialog').close();showTitleScreen();};
$('#creationDialog').addEventListener('cancel',event=>event.preventDefault());
