
(function(){
  var m=document.getElementById('menu');
  window.alternarMenu=function(e){
    if(e)e.preventDefault();
    var abriu=m.classList.toggle('aberto');
    document.body.classList.toggle('travado',abriu);
  };
  if(m)m.addEventListener('click',function(e){if(e.target===m)alternarMenu();});
  document.addEventListener('keydown',function(e){
    if(e.key==='Escape'&&m&&m.classList.contains('aberto'))alternarMenu();
  });
  var ini=document.querySelector('.faq.aberto .faq-i');
  if(ini)ini.textContent='\u2013';
  if(matchMedia('(prefers-reduced-motion: reduce)').matches){
    document.querySelectorAll('video[autoplay]').forEach(function(v){
      v.removeAttribute('autoplay');v.pause();
    });
  }
  var faixa=document.querySelector('[data-carrossel]');
  if(faixa&&!matchMedia('(prefers-reduced-motion: reduce)').matches){
    var pausaAte=0,visivel=true;
    var pausar=function(){pausaAte=Date.now()+9000;};
    ['pointerdown','touchstart','wheel','mouseenter','focusin'].forEach(function(ev){
      faixa.addEventListener(ev,pausar,{passive:true});
    });
    if(window.IntersectionObserver){
      new IntersectionObserver(function(es){visivel=es[0].isIntersecting;},
        {threshold:0.35}).observe(faixa);
    }
    setInterval(function(){
      if(!visivel||document.hidden||Date.now()<pausaAte)return;
      var cs=faixa.children;if(cs.length<2)return;
      var base=cs[0].offsetLeft,alvo=0;
      for(var i=0;i<cs.length;i++){
        var x=cs[i].offsetLeft-base;
        if(x>faixa.scrollLeft+8){alvo=x;break;}
      }
      if(faixa.scrollLeft+faixa.clientWidth>=faixa.scrollWidth-8)alvo=0;
      faixa.scrollTo({left:alvo,behavior:'smooth'});
    },4000);
  }
  document.querySelectorAll('[data-faq]').forEach(function(b){
    b.addEventListener('click',function(e){
      e.preventDefault();
      var c=b.closest('.faq'),aberto=c.classList.contains('aberto');
      document.querySelectorAll('.faq').forEach(function(o){
        o.classList.remove('aberto');
        var i=o.querySelector('.faq-i'); if(i)i.textContent='+';
      });
      if(!aberto){c.classList.add('aberto');
        var i=c.querySelector('.faq-i'); if(i)i.textContent='\u2013';}
    });
  });
})();
