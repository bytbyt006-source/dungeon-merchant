// A title screen, illustrated prologue, and persistent accessibility/audio options.
const OPTION_KEY='dungeonMerchant.options.v1';
let gameOptions={sound:true,effectsVolume:75,music:true,musicVolume:35,reduceMotion:false,largeText:false};
try{
 const saved=JSON.parse(localStorage.getItem(OPTION_KEY)||'null');
 if(saved&&typeof saved==='object'){
  for(const key of ['sound','music','reduceMotion','largeText'])if(typeof saved[key]==='boolean')gameOptions[key]=saved[key];
  const oldVolume=saved.effectsVolume??saved.volume;
  if(Number.isFinite(oldVolume))gameOptions.effectsVolume=Math.max(0,Math.min(100,Math.round(oldVolume)));
  if(Number.isFinite(saved.musicVolume))gameOptions.musicVolume=Math.max(0,Math.min(100,Math.round(saved.musicVolume)));
 }
}catch(e){}
function applyGameOptions(){
 if(!musicAvailable){gameOptions.music=false;$('#optionMusic').closest('label').hidden=true;$('#optionMusicVolume').closest('.numeric-field').hidden=true;}
 sound=gameOptions.sound;
 [paymentPouchAudio,coinRattleAudio,customerArrivalAudio,buttonAudio,diceRollAudio].forEach(clip=>{clip.volume=gameOptions.effectsVolume/100;if(!sound){clip.pause();clip.currentTime=0;}});
 if(audioBus)audioBus.gain.value=gameOptions.effectsVolume/100;
 if(!sound)audio?.suspend().catch(()=>{});else if(audio)prepareAudio();
 document.documentElement.dataset.motion=gameOptions.reduceMotion?'reduced':'normal';
 document.documentElement.dataset.largeText=String(gameOptions.largeText);
 syncMusic();
 $('#sound').textContent='Sound: '+(sound?'on':'off');$('#sound').setAttribute('aria-pressed',String(sound));
 $('#optionSound').checked=sound;$('#optionMotion').checked=gameOptions.reduceMotion;$('#optionText').checked=gameOptions.largeText;$('#optionVolume').value=gameOptions.effectsVolume;$('#optionMusic').checked=gameOptions.music;$('#optionMusicVolume').value=gameOptions.musicVolume;refreshNumberControls();
}
function setGameOption(key,value){gameOptions[key]=value;try{localStorage.setItem(OPTION_KEY,JSON.stringify(gameOptions));}catch(e){}applyGameOptions();}
addNumberStepper($('#optionVolume'),'sound effects volume');
addNumberStepper($('#optionMusicVolume'),'music volume');
$('#optionMusic').onchange=e=>setGameOption('music',e.target.checked);
$('#optionMusicVolume').oninput=e=>setGameOption('musicVolume',Number(e.target.value));
$('#musicToggle').onclick=()=>setGameOption('music',!gameOptions.music);
$('#optionSound').onchange=e=>setGameOption('sound',e.target.checked);
$('#optionVolume').oninput=e=>setGameOption('effectsVolume',Number(e.target.value));
$('#optionMotion').onchange=e=>setGameOption('reduceMotion',e.target.checked);
$('#optionText').onchange=e=>setGameOption('largeText',e.target.checked);
$('#optionsClose').onclick=()=>$('#optionsDialog').close();
$('#titleOptions').onclick=()=>{$('#optionsDialog').showModal();applyGameOptions();};
applyGameOptions();

const PROLOGUE=[
 {art:'fall',chapter:'I · THE FALL',heading:'A name turned to ash.',
  alt:'A cloaked heir watches the family estate burn in the rain.',
  copy:'Rival factions built your ruin in secret. Forged accusations stripped your house of its fortune; hired blades finished the work. You escaped the burning estate with a family signet, a handful of contacts, and a debt that survived the fire.'},
 {art:'shop',chapter:'II · THE COUNTER',heading:'No steward. No inheritance.',
  alt:'The fallen heir begins work behind the counter of a modest equipment shop.',
  copy:'There is no one left to bargain in your name. You must stand behind the counter yourself. Buy from the Monday caravan, read the people at your door, and turn equipment into enough gold to repay the loan. Adventurers may bring back opportunities no noble court ever offered.'},
 {art:'threat',chapter:'III · THE SHADOW',heading:'Your enemies remember.',
  alt:'A watchful figure waits outside while the heir works by candlelight.',
  copy:'The powers that ruined your family have not forgotten the surviving heir. Rebuild your fortune, sharpen your judgment, and learn whom to trust. A shop can become a refuge, a network, and the first step toward defending your name. Every coin buys another day.'}
];
let storyPage=0,storyExit='game',openingBusy=false;
function showTitleScreen(){
 if(!state||busy||openingBusy)return;
 document.querySelectorAll('dialog[open]').forEach(dialog=>dialog.close());
 if(state.equipment?.stats.hp<=0&&!state.ending){renderConfrontation();return;}
 $('#titleContinue').hidden=!state.has_progress;$('#titleContinue').textContent=state.ending?'View ending':'Continue';
 $('#titleStart').textContent=state.has_progress?'New game':'Start game';
 $('#titlePrologue').hidden=!state.has_progress;
 $('#titleSaveInfo').textContent=state.has_progress?formatDate(state.calendar)+' · '+state.gold+' gold':'A new beginning awaits.';
 $('#titleStatus').textContent='';$('#titleScreen').showModal();
 (state.has_progress?$('#titleContinue'):$('#titleStart')).focus();
}
async function enterCampaign(){
 $('#titleScreen').close();$('#storyDialog').close();
 if(state.creation&&!state.creation.completed){openCharacterCreation();return;}
 if(!state.intro_seen){playPrologue();return;}
 render();controls();await openRequestedTrade();
}
function renderStory(){
 const page=PROLOGUE[storyPage];$('#storyArt').src='assets/story/'+page.art+'.png';$('#storyArt').alt=page.alt;
 $('#storyChapter').textContent=page.chapter;$('#storyHeading').textContent=page.heading;$('#storyCopy').textContent=page.copy;
 $('#storyBack').disabled=storyPage===0||openingBusy;
 $('#storyNext').textContent=storyPage===PROLOGUE.length-1?(storyExit==='menu'?'Back to title':'Open the shop'):'Next';
 $('#storyDots').replaceChildren();PROLOGUE.forEach((_,index)=>{const dot=element('span','',index===storyPage?'story-dot active':'story-dot');dot.setAttribute('aria-label','Chapter '+(index+1));$('#storyDots').append(dot);});
}
function playPrologue(exit='game'){
 storyPage=0;storyExit=exit;$('#titleScreen').close();$('#storyStatus').textContent='';renderStory();$('#storyDialog').showModal();$('#storyNext').focus();
}
async function finishPrologue(){
 if(openingBusy)return;
 if(storyExit==='menu'){$('#storyDialog').close();showTitleScreen();return;}
 openingBusy=true;$('#storyNext').disabled=true;$('#storySkip').disabled=true;
 try{const response=await request({action:'finish_intro'});state=response.state;await enterCampaign();}
 catch(e){$('#storyStatus').textContent=e.message;}
 finally{openingBusy=false;$('#storyNext').disabled=false;$('#storySkip').disabled=false;}
}
$('#titleContinue').onclick=()=>enterCampaign();
$('#titleStart').onclick=()=>{if(state.has_progress){$('#newGameStatus').textContent='';$('#newGameDialog').showModal();}else openCharacterCreation();};
$('#titlePrologue').onclick=()=>playPrologue('menu');
$('#menuOpen').onclick=showTitleScreen;
$('#newGameCancel').onclick=()=>$('#newGameDialog').close();
$('#newGameConfirm').onclick=async()=>{
 if(openingBusy)return;openingBusy=true;$('#newGameConfirm').disabled=true;$('#newGameCancel').disabled=true;
 try{const response=await request({action:'new_game'});state=response.state;phase='idle';actor.hidden=true;actor.className='actor';journalOpen=false;waresOpen=false;warehouseSlot=0;warehouseItem=null;warehouseMode=null;commissionRegion='mine';commissionAdventurer=null;commissionWeapon=null;commissionArmour=null;commissionRelic=false;commissionDeep=false;commissionPreviewVersion++;relicActionRegion='mine';clearTimeout(previewTimer);previewVersion++;$('#newGameDialog').close();render();openCharacterCreation();}
 catch(e){$('#newGameStatus').textContent=e.message;}
 finally{openingBusy=false;$('#newGameConfirm').disabled=false;$('#newGameCancel').disabled=false;}
};
$('#storyBack').onclick=()=>{if(storyPage>0){storyPage--;renderStory();}};
$('#storyNext').onclick=()=>{if(storyPage<PROLOGUE.length-1){storyPage++;renderStory();}else finishPrologue();};
$('#storySkip').onclick=finishPrologue;
$('#titleScreen').addEventListener('cancel',e=>e.preventDefault());
$('#storyDialog').addEventListener('cancel',e=>{e.preventDefault();if(!openingBusy){$('#storyDialog').close();showTitleScreen();}});
window.addEventListener('merchant-ready',showTitleScreen);
if(state)showTitleScreen();
