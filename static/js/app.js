
function copyBlock(){
  const el=document.getElementById('copyBlock');
  if(!el) return;
  navigator.clipboard.writeText(el.innerText).then(()=>alert('Copied!'));
}
