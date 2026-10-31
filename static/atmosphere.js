'use strict';
// Decorative scenery is created once per visit and stays still across app views.
(()=>{
 const layer=document.querySelector('#scenery');
 const drawings=['coil','loop','wave','cloud','fold','sprig','curl','tangle'];
 let timer;
 const texture=new Image();
 texture.onerror=()=>document.documentElement.classList.add('texture-unavailable');
 texture.src='/assets/pearl-texture.png';
 function arrange(){
   const small=innerWidth<760, count=small?12:28;
   const fragment=document.createDocumentFragment();
   for(let i=0;i<count;i++){
     const img=document.createElement('img');
     img.src='/assets/doodle-'+drawings[i%drawings.length]+'.svg';img.alt='';
     // Confine scenery to the edges; controls and reading areas stay clear.
     const left=i%2===0;
     img.style.left=(small?(left?-2:97):(left?16+Math.random()*1.7:98+Math.random()))+'%';
     img.style.top=((i+Math.random()*.7)/count*96)+'%';
     img.style.width=(20+Math.random()*20)+'px';
     img.style.transform=`rotate(${Math.random()*160-80}deg)`;
     img.style.opacity=String(.17+Math.random()*.1);
     fragment.append(img);
   }
   layer.replaceChildren(fragment);
 }
 arrange();
 let narrow=innerWidth<760;
 addEventListener('resize',()=>{clearTimeout(timer);timer=setTimeout(()=>{if(narrow!==(innerWidth<760)){narrow=innerWidth<760;arrange()}},150)});
 document.addEventListener('click',event=>{
   const target=event.target.closest('nav [data-page]');
   if(!target)return;
   document.querySelectorAll('nav [data-page]').forEach(item=>{
     if(item===target)item.setAttribute('aria-current','page');else item.removeAttribute('aria-current');
   });
 });
})();
