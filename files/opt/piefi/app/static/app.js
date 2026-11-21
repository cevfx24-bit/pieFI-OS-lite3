(()=>{
 const root=document.documentElement;
 const saved=localStorage.getItem('piefi-theme');
 root.dataset.theme=saved==='dark'?'dark':'light';
 const theme=document.getElementById('themeToggle');
 if(theme) theme.addEventListener('click',()=>{root.dataset.theme=root.dataset.theme==='dark'?'light':'dark';localStorage.setItem('piefi-theme',root.dataset.theme);});
 const menu=document.getElementById('menuToggle'),side=document.getElementById('sidebar');
 if(menu&&side) menu.addEventListener('click',()=>side.classList.toggle('open'));
 const coinToday=document.getElementById('coinTodayValue');
 if(coinToday){
  const refreshCoin=async()=>{try{const r=await fetch('/admin/api/status',{cache:'no-store'});if(!r.ok)return;const d=await r.json();if(!d.ok||!d.coin)return;const c=d.coin;
   const today=document.getElementById('coinTodayValue'),total=document.getElementById('coinTotalValue'),pending=document.getElementById('coinPendingValue'),state=document.getElementById('coinControllerStatus');
   if(today)today.textContent='₱'+(c.coin_today_cents/100).toFixed(2);if(total)total.textContent='₱'+(c.coin_revenue_cents/100).toFixed(2);if(pending)pending.textContent=c.coin_waiting;
   if(state)state.textContent=c.coin_primary_online?'ONLINE':(c.coin_backup_online?'BACKUP':'OFFLINE');
  }catch(e){}}
  refreshCoin();setInterval(refreshCoin,5000);
 }
 document.querySelectorAll('[data-filter]').forEach(input=>input.addEventListener('input',()=>{const table=document.getElementById(input.dataset.filter);if(!table)return;const q=input.value.toLowerCase();table.querySelectorAll('tbody tr').forEach(row=>row.hidden=!row.innerText.toLowerCase().includes(q));}));
})();
