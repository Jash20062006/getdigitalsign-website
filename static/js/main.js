(function(){
"use strict";
var nav=document.getElementById("navbar");
if(nav){var ck=function(){nav.classList.toggle("scrolled",window.scrollY>30)};window.addEventListener("scroll",ck,{passive:true});ck()}

var tog=document.getElementById("navToggle"),lnk=document.getElementById("navLinks");
if(tog&&lnk){
  tog.addEventListener("click",function(){var o=lnk.classList.toggle("open");tog.classList.toggle("on",o)});
  lnk.querySelectorAll("a").forEach(function(a){a.addEventListener("click",function(){lnk.classList.remove("open");tog.classList.remove("on")})});
  document.addEventListener("click",function(e){if(!tog.contains(e.target)&&!lnk.contains(e.target)){lnk.classList.remove("open");tog.classList.remove("on")}});
}

var els=document.querySelectorAll(".reveal");
if(els.length&&"IntersectionObserver"in window){
  var obs=new IntersectionObserver(function(en){en.forEach(function(e){if(e.isIntersecting){e.target.classList.add("visible");obs.unobserve(e.target)}})},{threshold:.1,rootMargin:"0px 0px -40px 0px"});
  els.forEach(function(el){obs.observe(el)});
}else{els.forEach(function(el){el.classList.add("visible")})}

document.querySelectorAll(".flash").forEach(function(el){
  setTimeout(function(){el.style.transition="opacity .35s,transform .35s";el.style.opacity="0";el.style.transform="translateY(-10px)";setTimeout(function(){el.remove()},350)},5000);
});
})();