// Small interface symbols complement the generated pixel-art assets.
const UI_SYMBOLS={
 check:'<path d="m5 12 4 4L19 6"/>',
 cross:'<path d="m6 6 12 12M18 6 6 18"/>',
 clock:'<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/>',
 lock:'<rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v2"/>',
 map:'<path d="m3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2ZM9 3v16M15 5v16"/>',
 chest:'<path d="M4 10V7a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3v3M3 10h18v10H3ZM3 14h7m4 0h7"/><rect x="10" y="11" width="4" height="6"/>',
 shield:'<path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6Z"/><path d="m8 12 3 3 5-6"/>',
 star:'<path d="m12 2 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1Z"/>',
 relic:'<path d="m12 2 7 10-7 10-7-10Z"/><path d="M5 12h14M12 2v20"/>',
 scroll:'<path d="M6 4h13v14a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3v-2h11v2a3 3 0 0 0 6 0M6 4a3 3 0 0 0-3 3v2h3ZM6 4v12M10 8h6m-6 4h6"/>',
 arrow:'<path d="M3 12h17m-6-6 6 6-6 6"/>',
 warehouse:'<path d="m3 9 9-6 9 6v12H3ZM7 21V11h10v10M7 15h10M7 18h10"/>',
 hand:'<path d="M3 16h4l4 3h8l3-5-2-1-4 3h-4m-5 0 3-6h5a2 2 0 0 1 0 4h-3M3 12h4v9H3"/>',
 gear:'<path d="m14 3 7 7-9 9-7-7ZM4 16l4 4M2 22l4-4"/>',
 trophy:'<path d="M7 3h10v5a5 5 0 0 1-10 0ZM7 5H3v3a4 4 0 0 0 5 4m9-7h4v3a4 4 0 0 1-5 4M12 13v5m-4 3h8m-6-3h4v3h-4Z"/>'
};
function uiIcon(name){
 if(name==='coin'||name==='d20'){
  const image=document.createElement('img');image.src='assets/ui/'+(name==='coin'?'gold_coin':'d20')+'.png';image.alt='';image.className='ui-art ui-icon';image.setAttribute('aria-hidden','true');return image;
 }
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('class','ui-symbol ui-icon');svg.setAttribute('aria-hidden','true');svg.setAttribute('fill','none');svg.setAttribute('stroke','currentColor');svg.setAttribute('stroke-width','1.7');svg.setAttribute('stroke-linecap','round');svg.setAttribute('stroke-linejoin','round');svg.innerHTML=UI_SYMBOLS[name]||UI_SYMBOLS.relic;return svg;
}
function iconStat(name,value,label){
 const span=document.createElement('span');span.className='icon-stat';span.title=label;span.setAttribute('aria-label',label+': '+value);span.append(uiIcon(name),document.createTextNode(String(value)));return span;
}
function iconAction(button,name,label,amount=null,confirmation=false){
 button.replaceChildren(uiIcon(name));if(amount!==null){const span=document.createElement('span');span.className='action-amount';span.textContent=amount;button.append(span);}if(confirmation)button.append(uiIcon('check'));
 button.classList.add('icon-action');button.setAttribute('aria-label',label);button.title=label;
}
