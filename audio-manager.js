// Music and effects have independent switches and volumes.
const ambientMusic=$('#ambientMusic'),battleMusic=$('#battleMusic'),diceRollAudio=$('#diceRollAudio');
const musicTracks=[ambientMusic,battleMusic];
// Release packages may omit recordings whose redistribution is unconfirmed.
const musicAvailable=document.documentElement.dataset.musicAvailable!=='false';
let musicUnlocked=false,musicTarget=null,musicFrame=0,musicLevels=[0,0];
function musicVolume(){return Math.max(0,Math.min(1,gameOptions.musicVolume/100));}
function applyMusicLevels(){musicTracks.forEach((track,i)=>track.volume=Math.max(0,Math.min(1,musicLevels[i]*musicVolume())));}
function stopMusic(){
 cancelAnimationFrame(musicFrame);musicFrame=0;musicTarget=null;musicLevels=[0,0];
 musicTracks.forEach(track=>track.pause());applyMusicLevels();
}
function syncMusic(){
 $('#musicToggle').hidden=!musicAvailable;
 $('#musicToggle').textContent='Music: '+(gameOptions.music?'on':'off');$('#musicToggle').setAttribute('aria-pressed',String(gameOptions.music));
 if(!musicAvailable||!gameOptions.music||!musicUnlocked||document.hidden||gameOptions.musicVolume===0){stopMusic();return;}
 const desired=state?.combat?.status==='active'?battleMusic:ambientMusic;
 if(musicTarget===desired){applyMusicLevels();return;}
 cancelAnimationFrame(musicFrame);musicTarget=desired;
 const startLevels=musicLevels.slice(),started=performance.now();
 // Calling play in the gesture handler unlocks media before later combat changes.
 desired.play().catch(()=>{});
 const tick=now=>{
  const progress=Math.max(0,Math.min(1,(now-started)/650));
  musicLevels=startLevels.map((level,i)=>level+((musicTracks[i]===desired?1:0)-level)*progress);applyMusicLevels();
  if(progress<1)musicFrame=requestAnimationFrame(tick);
  else{musicTracks.forEach(track=>{if(track!==desired)track.pause();});musicFrame=0;}
 };
 musicFrame=requestAnimationFrame(tick);
}
function unlockMusic(){
 if(!musicAvailable||musicUnlocked||typeof gameOptions==='undefined')return;
 musicUnlocked=true;
 // Prime both music elements under the same user gesture for browser autoplay rules.
 for(const track of musicTracks){track.volume=0;const pending=track.play();if(pending)pending.then(()=>{if(track!==musicTarget)track.pause();}).catch(()=>{});}
 syncMusic();
}
function playDiceSound(){
 if(!sound)return;diceRollAudio.volume=gameOptions.effectsVolume/100;diceRollAudio.currentTime=0;diceRollAudio.play().catch(()=>{});
}
function stopDiceSound(){diceRollAudio.pause();diceRollAudio.currentTime=0;}
document.addEventListener('pointerdown',unlockMusic,{capture:true});
document.addEventListener('keydown',event=>{if(['Enter',' ','ArrowLeft','ArrowRight'].includes(event.key))unlockMusic();},{capture:true});
document.addEventListener('visibilitychange',syncMusic);
