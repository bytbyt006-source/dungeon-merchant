// Consume server strike events once; polling never creates an extra strike.
let battleFeedbackId=null,battleFeedbackSeq=0,portraitHit=null;
function strikeSound(event){
 if(!sound)return;
 prepareAudio();if(!audio)return;
 const now=audio.currentTime,bus=soundDestination(),gain=audio.createGain();
 gain.connect(bus);gain.gain.setValueAtTime(.0001,now);gain.gain.exponentialRampToValueAtTime(.16,now+.008);gain.gain.exponentialRampToValueAtTime(.0001,now+.19);
 const buffer=audio.createBuffer(1,Math.ceil(audio.sampleRate*.2),audio.sampleRate),samples=buffer.getChannelData(0);
 for(let i=0;i<samples.length;i++)samples[i]=Math.random()*2-1;
 const noise=audio.createBufferSource(),filter=audio.createBiquadFilter();noise.buffer=buffer;filter.type='bandpass';filter.frequency.value=event.outcome==='block'?2200:event.weapon==='hammer'?380:1100;noise.connect(filter);filter.connect(gain);noise.start(now);noise.stop(now+.2);
 const tone=audio.createOscillator();tone.type='triangle';tone.frequency.setValueAtTime(event.outcome==='block'?780:180,now);tone.frequency.exponentialRampToValueAtTime(65,now+.15);tone.connect(gain);tone.start(now);tone.stop(now+.2);
 tone.onended=()=>{tone.disconnect();noise.disconnect();filter.disconnect();gain.disconnect();};
}
function animateBattleNode(node,frames,options){
 const animation=node.animate(frames,options);animation.finished.then(()=>node.remove()).catch(()=>node.remove());return animation;
}
function showStrike(event){
 const layer=$('#combatEffects');if(!layer||!state.customer)return;
 strikeSound(event);
 const player=event.side==='player',outcome=event.outcome||'hit',reduced=prefersReducedMotion();
 const x=50,y=player?43:81;
 const mark=element('span',outcome==='hit'?(event.critical?'Critical −':'−')+event.damage:outcome==='dodge'?'Dodge':'Block','battle-number '+outcome);
 mark.style.left=x+'%';mark.style.top=y+'%';layer.append(mark);
 animateBattleNode(mark,[{opacity:1,transform:'translate(-50%,0)'},{opacity:0,transform:`translate(-50%,${reduced?0:-48}px)`}],{duration:950,easing:'ease-out'});
 if(outcome==='hit'){
  if(player){
   portraitHit?.cancel();const actor=$('#actor');
   const frames=reduced?[{filter:'sepia(1) saturate(4)'},{filter:'brightness(1)'}]:[{transform:'translate(-50%,0)',filter:'sepia(1) saturate(5) hue-rotate(320deg)'},{transform:'translate(calc(-50% + 9px),0)',filter:'brightness(1.7)'},{transform:'translate(calc(-50% - 6px),0)'},{transform:'translate(-50%,0)',filter:'brightness(1)'}];
   portraitHit=actor.animate(frames,{duration:300,easing:'ease-out'});
  }else $('#playerCombatHud').animate([{boxShadow:'0 0 28px #d82616',background:'#651c18'},{boxShadow:'0 0 0 transparent',background:'#171810f2'}],{duration:350});
 }
 const fx=element('div',undefined,'strike-effect '+(outcome==='block'?'blocked':''));fx.style.left=x+'%';fx.style.top=y+'%';
 const ranged=['bow','staff','book'].includes(event.weapon);
 fx.innerHTML=ranged?'<svg viewBox="0 0 160 160"><path d="M80 20 L98 80 L80 140 L62 80 Z"/><circle cx="80" cy="80" r="20"/></svg>':'<svg viewBox="0 0 160 160"><path d="M12 142 Q38 40 148 12 Q72 64 12 142Z"/><path d="M35 130 Q70 76 134 39"/></svg>';
 if(event.weapon==='staff')fx.classList.add('arcane');layer.append(fx);
 animateBattleNode(fx,reduced?[{opacity:.7},{opacity:0}]:ranged?[{opacity:0,transform:`translate(-50%,${player?160:-160}px) scale(.3)`},{opacity:1,offset:.6,transform:'translate(-50%,-50%) scale(.8)'},{opacity:0,transform:'translate(-50%,-50%) scale(1.3)'}]:[{opacity:0,transform:'translate(-50%,-50%) rotate(-30deg) scale(.4)'},{opacity:1,offset:.3},{opacity:0,transform:'translate(-50%,-50%) rotate(20deg) scale(1.2)'}],{duration:reduced?180:400,easing:'ease-out'});
}
function syncInjury(stats){
 const overlay=$('#injuryOverlay');if(!overlay)return;
 const loss=1-Math.max(0,Math.min(1,stats.hp/stats.max_hp));
 const hidden=loss<.02||$('#titleScreen')?.open||$('#storyDialog')?.open;
 overlay.hidden=hidden;overlay.style.setProperty('--injury',loss.toFixed(3));
 const svg=$('#bloodSpatters');
 if(!svg.children.length){
  // Stable edge stains; the inner ring appears only with severe injuries.
  for(let i=0;i<48;i++){
   const angle=i*2.39996,depth=28+(i%6)*24,cx=500+Math.cos(angle)*(650-depth),cy=500+Math.sin(angle)*(650-depth);
   const group=document.createElementNS('http://www.w3.org/2000/svg','g');group.dataset.threshold=String(.05+(i%8)*.105);
   for(let j=0;j<5;j++){const dot=document.createElementNS('http://www.w3.org/2000/svg','ellipse');dot.setAttribute('cx',cx+Math.sin(i*7+j*13)*(j?65:0));dot.setAttribute('cy',cy+Math.cos(i*11+j*9)*(j?65:0));dot.setAttribute('rx',j?5+(i+j)%12:25+i%27);dot.setAttribute('ry',j?4+(i+j)%10:18+i%21);group.append(dot);}
   svg.append(group);
  }
 }
 for(const group of svg.children)group.style.opacity=String(Math.max(0,Math.min(.64,(loss-Number(group.dataset.threshold))*3)));
}
function syncBattleFeedback(next){
 syncInjury(next.equipment.stats);
 const fight=next.combat;if(!fight){battleFeedbackId=null;battleFeedbackSeq=0;return;}
 if(battleFeedbackId!==fight.id){battleFeedbackId=fight.id;battleFeedbackSeq=fight.event_seq||0;return;}
 for(const event of fight.events||[])if(event.id>battleFeedbackSeq){battleFeedbackSeq=event.id;showStrike(event);}
}
