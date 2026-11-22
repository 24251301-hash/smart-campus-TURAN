'use strict';
const app = document.getElementById('app');
let activeSearch = '';
let activeFilter = 'all';
const riskNames = {high:'Высокий',medium:'Средний',normal:'Норма'};
const riskColors = {high:'#ef5559',medium:'#efbe37',normal:'#25ac67'};
const fmt = n => Number(n).toLocaleString('ru-RU');
const percent = n => `${Math.round(n)}%`;
const safe = input => String(input ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const initials = name => String(name).split(' ').map(s=>s[0]||'').slice(0,2).join('').toUpperCase();
const pill = (risk, text) => `<span class="pill ${safe(risk)}">${safe(text || riskNames[risk])}</span>`;
const mini = s => `<span class="mini-avatar ${s.risk==='high'?'high':''}">${safe(initials(s.name))}</span>`;
const title = (heading, sub) => `<div class="page-header"><h1>${safe(heading)}</h1><p>${safe(sub)}</p></div>`;
const notice = `<div class="info-note">Карточки построены по 480 строкам xAPI-Edu-Data. ФИО и группы с пометкой synthetic_demo созданы только для учебного интерфейса и не являются персональными данными. Прогнозы моделей не являются окончательной оценкой студента.</div>`;
const checkStatus = (s) => s.risk==='high' ? 'strong-red' : '';
function toast(message, isError=false, isSuccess=false) { const c=document.getElementById('toast-container'); c.replaceChildren(); const t=document.createElement('div'); t.className='toast'+(isError?' error':'')+(isSuccess?' success':'');t.textContent=message;c.appendChild(t);setTimeout(()=>{if(t.parentNode)t.remove()},4500); }
async function request(path, options={}) { const r=await fetch(path, {...options, headers:{...options.headers}}); let data;try{data=await r.json()}catch{throw new Error('Ответ сервера не является JSON')}if(r.status===401&&data.auth){me=null;showAuth('login');throw new Error('Сессия завершена, войдите снова');}if(!r.ok)throw new Error(data.error||`Ошибка HTTP ${r.status}`);return data; }
function showError(error){ app.innerHTML=`<div class="error-state"><h2>Не получилось загрузить данные</h2><p>${safe(error.message||error)}</p><p class="legend">Возможно, сервер ещё запускается. Подождите несколько секунд и нажмите «Повторить».</p><button class="btn" id="retry-btn">Повторить</button></div>`;document.getElementById('retry-btn').onclick=render; }
function markNav(route){document.querySelectorAll('#main-nav a').forEach(a=>{const type=a.dataset.route;const active=(type==='risks'&&location.hash.includes('section=alerts'))||(type===route&&!(route==='analytics'&&location.hash.includes('section=alerts')));a.classList.toggle('active',active);a.setAttribute('aria-current',active?'page':'false');});}
function navigate(hash){ location.hash=hash; }
function setContent(html){app.innerHTML=html;}
const hint = text => `<span class="hint" tabindex="0" role="note" aria-label="${safe(text)}" data-tip="${safe(text)}">?</span>`;
function chartMetric(label,value,line,caption,help=''){return `<div class="stat-card card" style="--line:${line}"><div class="stat-label">${safe(label)}${help?hint(help):''}</div><strong>${safe(value)}</strong><small>${safe(caption)}</small></div>`;}
function kpi(value,label,color,help=''){return `<div class="week-metric"><strong style="color:${color}">${safe(value)}</strong><small>${safe(label)}${help?hint(help):''}</small></div>`;}
function attention(s){return `<a href="#/student/${s.id}" class="attention-row">${mini(s)}<span class="attention-info"><strong class="attention-name">${safe(s.name)}</strong><small>Вовлечённость ${percent(s.engagement)}</small></span>${pill(s.risk)}</a>`;}
async function overview(){const d=await request('/api/dashboard');setContent(`${title(me&&me.role!=='teacher'?'Панель мониторинга':'Панель преподавателя',`Здравствуйте, ${me?firstName(me.full_name):''}! Интеллектуальный мониторинг посещаемости и вовлечённости студентов`)}${notice}
  <div class="summary-grid">${chartMetric('Средняя посещаемость',percent(d.avg_attendance),'#2f80ed','по всем студентам','Какую долю занятий в среднем посетили студенты. Выше 75% — хороший уровень.')}${chartMetric('Средняя вовлечённость',percent(d.avg_engagement),'#9b4de5','по всем студентам','Насколько активно студенты работают: поднимают руку, открывают материалы, участвуют в обсуждениях. Ниже 70% — повод присмотреться.')}${chartMetric('Студентов с риском',d.at_risk,'#ef5559',`из них ${d.high_risk} с высоким риском`,'Сколько студентов ИИ-модель (Random Forest) отнесла к среднему или высокому риску снижения успеваемости.')}${chartMetric('Учебных групп',d.active_courses,'#24ad67','в базе системы','Сколько учебных групп сейчас отслеживает система.')}</div>
  <div class="guide-note"><strong>Как читать панель:</strong> <span class="dot normal"></span>зелёный — норма, <span class="dot medium"></span>жёлтый — средний риск, <span class="dot high"></span>красный — высокий риск. Наведите курсор на <span class="hint static">?</span> рядом с показателем, чтобы узнать, что он означает.</div>
  <div class="dashboard-main"><section class="card quick-card"><h2>Что делать преподавателю</h2><p class="card-sub">От предупреждения к решению — три простых шага</p><div class="step-list">
  <a class="step-link" href="#/students"><span class="step-count">01</span><span class="step-copy"><strong>Найти студента</strong><small>Открыть список, отфильтровать по риску или найти по имени</small></span><span class="step-arrow">›</span></a>
  <a class="step-link" href="#/analytics"><span class="step-count">02</span><span class="step-copy"><strong>Разобрать причины риска</strong><small>Посмотреть распределение рисков и ключевые учебные факторы</small></span><span class="step-arrow">›</span></a>
  <a class="step-link" href="#/students"><span class="step-count">03</span><span class="step-copy"><strong>Определить меры поддержки</strong><small>Открыть профиль студента, изучить рекомендации и назначить консультацию</small></span><span class="step-arrow">›</span></a>
  </div></section>
  <section class="card attention-card"><h2>Требуют внимания</h2><p class="card-sub">Первые студенты из списка риска</p><div class="attention-list">${d.attention.map(attention).join('')||'<p class="legend">Нет предупреждений</p>'}</div></section></div>
  <section class="card week-card"><h2>Сводные показатели по группе</h2><p class="card-sub">Рассчитаны по строкам xAPI и карточкам, добавленным в локальную SQLite</p><div class="week-metrics">${kpi(d.overdue_total,'просроченных заданий','#ef5559','Сколько заданий студенты сдали с опозданием или не сдали.')}${kpi(d.on_time_total,'сдано вовремя','#24ad67','Сколько заданий сдано в срок.')}${kpi(d.anomalies,'нетипичных профилей','#2f80ed','Студенты, чья активность сильно отличается от остальных. Их находит модель Isolation Forest.')}${kpi(d.at_risk,'требуют внимания','#9152e8','Студенты со средним или высоким риском — с них стоит начать.')}</div><div class="week-recommend"><h3>Рекомендация</h3><p>Просмотрите профили студентов с высоким риском. Автоматический анализ только подсказывает возможные факторы; решение о поддержке принимает преподаватель.</p></div></section>`);}
function row(s){return `<tr role="link" tabindex="0" data-open-student="${s.id}" title="Открыть профиль студента"><td><div class="student-name">${mini(s)}<strong>${safe(s.name)}</strong></div></td><td class="muted">${safe(s.dataset_id)}</td><td class="muted">${safe(s.student_group)}</td><td class="${checkStatus(s)}">${percent(s.attendance)}</td><td class="${checkStatus(s)}">${percent(s.engagement)}</td><td><strong>${Number(s.grade).toFixed(1)}</strong></td><td>${pill(s.risk)}</td></tr>`;}
function bindTableClicks(){document.querySelectorAll('[data-open-student]').forEach(r=>{const go=()=>navigate(`#/student/${r.dataset.openStudent}`);r.addEventListener('click',go);r.addEventListener('keydown',ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();go()}});});}
function listMarkup(items,shown,total){return `<div class="card table-card"><table class="student-table"><thead><tr><th>Студент</th><th>ID</th><th>Группа</th><th>Посещаемость</th><th>Вовлечённость</th><th>Средний балл</th><th>Статус</th></tr></thead><tbody>${items.map(row).join('')}</tbody></table>${!shown?'<div class="empty-state">По вашему запросу студенты не найдены</div>':''}<div class="table-foot">Показано ${shown} из ${total} студентов. Нажмите строку для просмотра профиля.</div></div>`;}
let searchCounter=0;
async function refreshStudents(){const counter=++searchCounter;try{const qs=new URLSearchParams({search:activeSearch,risk:activeFilter});const d=await request('/api/students?'+qs);if(counter!==searchCounter)return;const slot=document.getElementById('list-slot');if(slot){slot.innerHTML=listMarkup(d.items,d.shown,d.total);bindTableClicks();}}catch(e){toast(e.message,true)}}
async function students(){activeSearch='';activeFilter='all';setContent(`${title('Студенты','Список обучающихся и ключевые показатели учебной активности')}${notice}
<div class="filters"><label class="search-box" aria-label="Поиск по ФИО или группе"><svg viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/></svg><input id="search" type="search" placeholder="Поиск по ФИО или группе…" autocomplete="off"></label>
<button class="chip active" data-filter="all">Все</button><button class="chip risk" data-filter="at-risk">Риск</button><button class="chip normal" data-filter="normal">Норма</button><button class="chip risk" data-filter="high">Высокий</button>${canEdit()?'<button class="btn add-student-btn" id="add-student-btn">+ Добавить студента</button>':'<span class="view-chip add-student-btn" title="Добавление студентов доступно преподавателям и работникам университета">Режим просмотра</span>'}</div><div id="list-slot"><div class="loading">Загружаем студентов…<p class="wake-note delayed">Сервер запускается после простоя — это может занять до минуты. Пожалуйста, не закрывайте страницу.</p></div></div>`);
 const search=document.getElementById('search');let timer;
 search.addEventListener('input',()=>{activeSearch=search.value;clearTimeout(timer);timer=setTimeout(refreshStudents,170)});
 document.querySelectorAll('[data-filter]').forEach(btn=>btn.addEventListener('click',()=>{activeFilter=btn.dataset.filter;document.querySelectorAll('[data-filter]').forEach(b=>b.classList.toggle('active',b===btn));refreshStudents();}));
 const addBtn=document.getElementById('add-student-btn');if(addBtn)addBtn.onclick=openAddStudent;
 await refreshStudents();}
function metric(label,value,caption,color){return `<div class="card student-metric" style="--bar:${color}"><p>${safe(label)}</p><strong>${safe(value)}</strong><small>${safe(caption)}</small></div>`;}
async function studentProfile(id,isNew=false){const d=await request('/api/students/'+id);const newBanner=isNew?`<div class="success-banner" role="status"><span>✓</span><div><strong>Студент добавлен в базу</strong><p>ИИ-модель уже проанализировала карточку: уровень риска — «${safe(riskNames[d.risk])}». Студент появился в общем списке.</p></div></div>`:'';const anomaly = d.is_anomaly ? '<span class="anomaly-badge">Isolation Forest: нетипичный профиль</span>':'<span class="anomaly-badge clear">Isolation Forest: обычный профиль</span>';
 const sourceBadge=d.name_source==='manual_entry'?'<span class="anomaly-badge clear">Добавлен вручную</span>':'<span class="anomaly-badge clear">Синтетическое ФИО xAPI</span>';
 setContent(`<a class="back-link" href="#/students">← К списку студентов</a>${title('Профиль студента','Показатели вовлечённости и объяснение факторов риска')}${newBanner}${notice}
 <section class="card student-banner"><span class="big-avatar">${safe(initials(d.name))}</span><div><h2>${safe(d.name)}</h2><p>${safe(d.student_group)} · ${safe(d.dataset_id)}${d.source_class?` · исходный класс ${safe(d.source_class)}`:''}</p><div class="tag-row">${pill(d.risk,d.risk==='high'?'Высокий риск':d.risk==='medium'?'Средний риск':'Норма')}${anomaly}${sourceBadge}</div></div></section>
 <div class="student-metrics">${metric('Посещаемость',percent(d.attendance),'за контрольный период',d.attendance<75?'#ef5559':'#2f80ed')}${metric('Вовлечённость',percent(d.engagement),'сравнить со средней по группе',d.engagement<70?'#ef5559':'#2f80ed')}${metric('Средний балл',`${Number(d.grade).toFixed(1)} / 4`,'учебная успеваемость','#2f80ed')}${metric('Просрочено',d.overdue,'заданий','#efb92c')}</div>
 <section class="card analysis-card"><div><h2>ИИ-анализ учебного риска</h2><p class="legend">Random Forest классифицирует риск, Isolation Forest ищет аномалии</p><h3>Выявленные факторы</h3><ul class="bullet-factors">${d.factors.map(x=>`<li>${safe(x)}</li>`).join('')}</ul><div class="meta-line"><span>RF: категория «${safe(riskNames[d.risk])}»</span><span>Уверенность модели: ${percent(d.confidence*100)}</span><span>Средняя вовлечённость группы: ${d.group_engagement}%</span></div></div>
 <div class="recommend-panel"><h3>Рекомендация преподавателю</h3><p>${safe(d.recommendation)}</p><p class="legend">Рекомендация формируется на основе прозрачных правил. Студента нельзя оценивать только по автоматическому прогнозу.</p><div class="recommend-actions">${canEdit()?'<button class="btn" id="consult-btn">Назначить консультацию</button>':'<button class="btn" id="consult-btn" disabled title="Доступно преподавателям и работникам университета">Назначить консультацию</button>'}<a class="btn outline" href="#/analytics">Смотреть аналитику</a></div></div></section>
 <section class="card consult-list"><h3>Запланированные консультации</h3>${d.consultations.length?d.consultations.map(c=>`<div class="consult-entry"><strong>${safe(c.appointment_at.replace('T',' '))}</strong> · ${safe(c.note)}<br><span>Сохранено локально: ${safe(c.created_at.replace('T',' '))}</span></div>`).join(''):'<p class="legend">Пока записей нет. Можно создать демонстрационную консультацию — она сохранится в SQLite.</p>'}</section>`);
 if(canEdit())document.getElementById('consult-btn').onclick=()=>openConsultation(d);}
function openAddStudent(){const shell=document.createElement('div');shell.className='modal-wrap';shell.setAttribute('role','dialog');shell.setAttribute('aria-modal','true');shell.setAttribute('aria-labelledby','add-student-heading');
 shell.innerHTML=`<form class="modal" id="add-student-form" novalidate><div class="modal-title"><h2 id="add-student-heading">Добавить студента</h2><button id="add-student-close" type="button" aria-label="Закрыть">×</button></div><p class="legend">Заполните карточку и нажмите «Добавить в базу». ИИ сразу определит уровень риска, и откроется профиль нового студента.</p><div class="form-grid">
 ${field('new-name','ФИО','text','','Например: Ахметов Алихан','Фамилия и имя, от 2 до 80 символов',true)}
 ${field('new-group','Группа','text','ИС-242(4)-2','','Например: ИС-242(4)-2',true)}
 ${field('new-attendance','Посещаемость, %','text','85','','Число от 0 до 100')}
 ${field('new-engagement','Вовлечённость, %','text','75','','Число от 0 до 100')}
 ${field('new-grade','Средний балл','text','3.2','','От 0 до 4, можно с запятой: 3,5')}
 ${field('new-overdue','Просрочено заданий','text','0','','Целое число от 0 до 50')}
 </div><div class="form-error" id="add-student-error" role="alert" hidden></div><div class="modal-actions"><button class="btn ghost" id="add-student-cancel" type="button">Отмена</button><button class="btn" type="submit" id="add-student-save">Добавить в базу</button></div></form>`;
 document.body.appendChild(shell);const close=()=>{shell.remove();document.removeEventListener('keydown',esc)};function esc(e){if(e.key==='Escape')close()}document.addEventListener('keydown',esc);shell.addEventListener('click',e=>{if(e.target===shell)close()});shell.querySelector('#add-student-close').onclick=close;shell.querySelector('#add-student-cancel').onclick=close;shell.querySelector('#new-name').focus();
 shell.querySelectorAll('.form-field').forEach(inp=>inp.addEventListener('input',()=>{inp.classList.remove('invalid');const m=shell.querySelector(`#${inp.id}-msg`);if(m)m.textContent='';}));
 shell.querySelector('#add-student-form').addEventListener('submit',async ev=>{ev.preventDefault();const box=shell.querySelector('#add-student-error');box.hidden=true;
  const v=id=>shell.querySelector('#'+id).value.trim();const num=id=>Number(v(id).replace(',','.'));
  const checks=[['new-name',v('new-name').length>=2&&v('new-name').length<=80,'Введите ФИО (от 2 до 80 символов)'],['new-group',v('new-group').length>=2&&v('new-group').length<=50,'Введите группу (от 2 до 50 символов)'],['new-attendance',v('new-attendance')!==''&&num('new-attendance')>=0&&num('new-attendance')<=100,'Посещаемость — число от 0 до 100'],['new-engagement',v('new-engagement')!==''&&num('new-engagement')>=0&&num('new-engagement')<=100,'Вовлечённость — число от 0 до 100'],['new-grade',v('new-grade')!==''&&num('new-grade')>=0&&num('new-grade')<=4,'Средний балл — число от 0 до 4'],['new-overdue',v('new-overdue')!==''&&Number.isInteger(num('new-overdue'))&&num('new-overdue')>=0&&num('new-overdue')<=50,'Просрочено — целое число от 0 до 50']];
  let firstBad=null;checks.forEach(([id,ok,msg])=>{const inp=shell.querySelector('#'+id);inp.classList.toggle('invalid',!ok);shell.querySelector(`#${id}-msg`).textContent=ok?'':msg;if(!ok&&!firstBad)firstBad=inp;});
  if(firstBad){box.textContent='Проверьте поля, выделенные красным.';box.hidden=false;firstBad.focus();return;}
  const btn=shell.querySelector('#add-student-save');btn.disabled=true;btn.textContent='Сохраняем…';
  try{const created=await request('/api/students',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:v('new-name'),student_group:v('new-group'),attendance:num('new-attendance'),engagement:num('new-engagement'),grade:num('new-grade'),overdue:num('new-overdue')})});close();toast(`✓ Студент «${v('new-name')}» добавлен. ИИ определил уровень риска.`,false,true);navigate(`#/student/${created.id}?new=1`);}
  catch(e){box.textContent='Не удалось сохранить: '+e.message;box.hidden=false;btn.disabled=false;btn.textContent='Добавить в базу';}});}
function field(id,label,type,value,placeholder,help,wide=false){return `<label class="form-label${wide?' form-wide':''}" for="${id}">${safe(label)}<input class="form-field" id="${id}" type="${type}" inputmode="${id==='new-name'||id==='new-group'?'text':'decimal'}" value="${safe(value)}" placeholder="${safe(placeholder)}" autocomplete="off"><span class="field-help">${safe(help)}</span><span class="field-msg" id="${id}-msg"></span></label>`;}
function openConsultation(student){const shell=document.createElement('div');shell.className='modal-wrap';shell.setAttribute('role','dialog');shell.setAttribute('aria-modal','true');shell.setAttribute('aria-labelledby','modal-heading');const date=new Date(Date.now()+86400000); const local=new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);
 shell.innerHTML=`<form class="modal" id="consult-form"><div class="modal-title"><h2 id="modal-heading">Назначить консультацию</h2><button id="modal-close" type="button" aria-label="Закрыть">×</button></div><p class="legend">${safe(student.name)} · ${safe(student.student_group)}</p><label class="form-label">Дата и время<input class="form-field" id="appointment" type="datetime-local" required value="${local}"></label><label class="form-label">Причина и план консультации<textarea class="form-field" id="reason" rows="3" required maxlength="400">Обсудить снижение вовлечённости и предложить учебную поддержку.</textarea></label><div class="modal-actions"><button class="btn ghost" id="cancel-btn" type="button">Отмена</button><button class="btn" type="submit" id="save-btn">Сохранить в базу</button></div><p class="legend">Запись хранится только на этом компьютере. Уведомления не отправляются.</p></form>`;
 document.body.appendChild(shell);
 function close(){shell.remove();document.removeEventListener('keydown',esc)}
 function esc(e){if(e.key==='Escape')close()}
 shell.addEventListener('click',e=>{if(e.target===shell)close()});document.addEventListener('keydown',esc);shell.querySelector('#modal-close').onclick=close;shell.querySelector('#cancel-btn').onclick=close;shell.querySelector('#appointment').focus();
 shell.querySelector('#consult-form').addEventListener('submit',async ev=>{ev.preventDefault();const btn=shell.querySelector('#save-btn');btn.disabled=true;try{await request('/api/consultations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({student_id:student.id,appointment_at:shell.querySelector('#appointment').value,note:shell.querySelector('#reason').value})});close();toast('Консультация сохранена в SQLite');await studentProfile(student.id);}catch(e){toast(e.message,true)}finally{btn.disabled=false}});
}
function progress(label,count,total,color){return `<div class="risk-progress-row"><span>${safe(label)}</span><div class="progress-bar"><span style="width:${total?Math.round(100*count/total):0}%;background:${color}"></span></div><small>${count} чел.</small></div>`;}
function factorBar(f,color){return `<div class="risk-progress-row"><span>${safe(f.label)}</span><div class="progress-bar"><span style="width:${Math.min(100,f.percent)}%;background:${color}"></span></div><small>${f.percent}%</small></div>`;}
function alertLine(s){const brief=s.overdue?`Просрочено заданий: ${s.overdue}. `:'';return `<a class="alert-item" href="#/student/${s.id}">${mini(s)}<strong>${safe(s.name)}</strong><p>Вовлечённость ${s.engagement}%. ${brief}${s.is_anomaly?'Обнаружен нетипичный профиль активности.':''}</p>${pill(s.risk,s.risk==='high'?'Высокий риск':'Средний риск')}</a>`;}
async function analytics(){const [a,d]=await Promise.all([request('/api/analytics'),request('/api/dashboard')]);setContent(`${title('Аналитика и риски','Сводная картина по группе и автоматические предупреждения')}${notice}
 <div class="analytics-top"><section class="card analytics-card"><h2>Распределение по уровню риска</h2><div class="risk-progress">${progress('Норма',a.distribution.normal,d.count,'#27ae66')}${progress('Средний риск',a.distribution.medium,d.count,'#f1c449')}${progress('Высокий риск',a.distribution.high,d.count,'#ef5559')}</div><p class="legend">Всего студентов: <strong>${d.count}</strong>. Категории вычислены моделью Random Forest.</p></section>
 <section class="card analytics-card factors-card"><h2>Ключевые факторы риска</h2><div class="risk-progress">${a.factors.map((f,i)=>factorBar(f,['#ef5559','#eebb3a','#2f80ed','#9851eb'][i])).join('')}</div><p class="legend">Доли срабатываний правил среди выявленных факторов группы риска; один студент может иметь несколько факторов.</p></section></div>
 <section class="card alerts-table" id="alerts"><h2>ИИ-предупреждения</h2><p class="card-sub">Нажмите на студента, чтобы увидеть факторы риска и рекомендации</p><div class="alerts-list">${a.alerts.map(alertLine).join('')||'<p class="legend">Нет активных предупреждений</p>'}</div><div class="model-footer"><b>Применённые ИИ-методы:</b> Random Forest (классификация), Isolation Forest (поиск аномалий).<br><b>Источник обучения:</b> ${safe(a.model.training_source)}.<br><b>Разделение:</b> обучение — ${a.model.training_rows} записей; тестирование — ${a.model.test_rows} записей.<br><b>Ограничение:</b> ${safe(a.model.warning)}<br><a href="#/students" style="color:#2f80ed">Открыть полный список студентов →</a></div></section>`);
 if(location.hash.includes('section=alerts'))document.getElementById('alerts')?.scrollIntoView({behavior:'smooth'});
}

/* ================= Учётные записи: вход, регистрация, «Мой профиль» ================= */
let me = null;
const ICONS = {
  teacher:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4M7 9h6M7 12h4"/></svg>',
  student:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 9l10-5 10 5-10 5z"/><path d="M6 11v5c0 1.5 3 3 6 3s6-1.5 6-3v-5M22 9v6"/></svg>',
  employee:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="3" width="16" height="18" rx="1.5"/><path d="M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2M10 21v-3h4v3"/></svg>',
  other:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/></svg>'
};
const ROLE_META = {
  teacher:{label:'Преподаватель',detail:'Кафедра или дисциплина',ph:'Например: Системы искусственного интеллекта',hint:'Полный доступ',required:false},
  student:{label:'Студент',detail:'Учебная группа',ph:'Например: ИС-242(4)-2',hint:'Просмотр аналитики',required:true},
  employee:{label:'Работник университета',detail:'Подразделение и должность',ph:'Например: Офис регистратора, специалист',hint:'Полный доступ',required:false},
  other:{label:'Другое',detail:'Кем вы являетесь',ph:'Например: абитуриент, родитель, гость',hint:'Просмотр аналитики',required:true}
};
const firstName = n => { const p = String(n||'').trim().split(/\s+/); return p.length > 1 ? p[1] : p[0]; };
const fmtDate = iso => { try { return new Date(iso).toLocaleDateString('ru-RU',{day:'numeric',month:'long',year:'numeric'}); } catch { return iso; } };
const canEdit = () => !!(me && me.can_edit);

function updateUserChrome(){
  if(!me) return;
  document.getElementById('top-user-name').textContent = me.full_name;
  document.getElementById('top-user-role').textContent = me.role_label + (me.detail ? ' · ' + me.detail : '');
  const av = document.getElementById('top-user-avatar'); av.textContent = initials(me.full_name); av.className = 'avatar-user role-' + me.role;
}
function showApp(){ document.getElementById('auth-root').hidden = true; document.getElementById('app-shell').hidden = false; updateUserChrome(); render(); }
async function logoutNow(){ try{ await fetch('/api/auth/logout',{method:'POST'}); }catch{} me = null; toast('Вы вышли из аккаунта'); showAuth('login'); }

function authField(id,label,type,placeholder,help='',attrs=''){return `<label class="form-label" for="${id}">${safe(label)}<input class="form-field" id="${id}" type="${type}" placeholder="${safe(placeholder)}" autocomplete="off" ${attrs}>${help?`<span class="field-help">${safe(help)}</span>`:''}<span class="field-msg" id="${id}-msg"></span></label>`;}
function setFieldError(root,id,msg){const inp=root.querySelector('#'+id);if(inp)inp.classList.toggle('invalid',!!msg);const m=root.querySelector(`#${id}-msg`);if(m)m.textContent=msg||'';}

function showAuth(mode='login'){
  document.getElementById('app-shell').hidden = true;
  const root = document.getElementById('auth-root'); root.hidden = false;
  const roleCards = Object.entries(ROLE_META).map(([key,r],i)=>`<label class="role-card role-${key}"><input type="radio" name="role" value="${key}" ${i===0?'':''}><span class="role-icon">${ICONS[key]}</span><span class="role-text"><strong>${safe(r.label)}</strong><small>${safe(r.hint)}</small></span></label>`).join('');
  root.innerHTML = `<div class="auth-wrap">
   <section class="auth-hero"><div class="brand auth-brand"><strong>SMART CAMPUS</strong><span>TURAN</span></div>
    <h1>Мониторинг учебного процесса с искусственным интеллектом</h1>
    <p>Посещаемость, вовлечённость и ранние предупреждения о рисках — в одной системе для университета «Туран».</p>
    <ul class="auth-features"><li><span>1</span>Сводная панель по группе и каждому студенту</li><li><span>2</span>ИИ-оценка риска: Random Forest и Isolation Forest</li><li><span>3</span>Понятные причины риска и рекомендации преподавателю</li></ul>
    <small class="auth-note">Учебный проект · демонстрационные данные xAPI-Edu-Data</small></section>
   <section class="auth-card card"><div class="auth-tabs" role="tablist"><button type="button" role="tab" data-mode="login" class="${mode==='login'?'active':''}">Вход</button><button type="button" role="tab" data-mode="register" class="${mode==='register'?'active':''}">Регистрация</button></div>
   ${mode==='login' ? `<form id="login-form" novalidate><h2>С возвращением!</h2><p class="legend">Войдите, чтобы открыть панель мониторинга.</p>
     ${authField('login-email','Email','email','name@turan-edu.kz')}
     ${authField('login-password','Пароль','password','Ваш пароль')}
     <label class="check-line"><input type="checkbox" id="login-show"> Показать пароль</label>
     <div class="form-error" id="auth-error" role="alert" hidden></div>
     <button class="btn auth-submit" type="submit" id="auth-submit">Войти</button>
     <p class="auth-switch">Нет аккаунта? <a href="#" data-mode="register">Зарегистрируйтесь</a></p>
     <p class="auth-hint">Демо-сервер периодически перезапускается, и созданные аккаунты при этом удаляются. Если войти не получается — просто зарегистрируйтесь заново.</p></form>`
   : `<form id="register-form" novalidate><h2>Создание аккаунта</h2><p class="legend">Регистрация займёт меньше минуты.</p>
     ${authField('reg-name','ФИО','text','Например: Садыкова Динара')}
     ${authField('reg-email','Email','email','name@turan-edu.kz')}
     <fieldset class="role-set"><legend>Кто вы?</legend><div class="role-grid">${roleCards}</div><span class="field-msg" id="reg-role-msg"></span></fieldset>
     <div id="reg-detail-slot"></div>
     <div class="form-grid">${authField('reg-password','Пароль','password','Минимум 8 символов','Буквы и хотя бы одна цифра')}${authField('reg-password2','Повторите пароль','password','Ещё раз')}</div>
     <label class="check-line"><input type="checkbox" id="reg-agree"> Я понимаю, что это учебный проект с демонстрационными данными</label><span class="field-msg" id="reg-agree-msg"></span>
     <div class="form-error" id="auth-error" role="alert" hidden></div>
     <button class="btn auth-submit" type="submit" id="auth-submit">Зарегистрироваться</button>
     <p class="auth-switch">Уже есть аккаунт? <a href="#" data-mode="login">Войти</a></p></form>`}
   </section></div>`;
  root.querySelectorAll('[data-mode]').forEach(el=>el.addEventListener('click',e=>{e.preventDefault();showAuth(el.dataset.mode)}));
  root.querySelectorAll('.form-field').forEach(inp=>inp.addEventListener('input',()=>setFieldError(root,inp.id,'')));
  const errBox = root.querySelector('#auth-error');
  const fail = msg => { errBox.textContent = msg; errBox.hidden = false; };
  const submitBtn = root.querySelector('#auth-submit');
  async function send(path, body, label){
    submitBtn.disabled = true; const old = submitBtn.textContent; submitBtn.textContent = label;
    try{ const r = await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); const d = await r.json().catch(()=>({error:'Сервер недоступен, попробуйте ещё раз'}));
      if(!r.ok) throw new Error(d.error||'Ошибка'); me = d.user; history.replaceState(null,'','#/overview'); showApp(); toast(`Добро пожаловать, ${firstName(me.full_name)}!`,false,true);
    }catch(e){ fail(e.message); submitBtn.disabled=false; submitBtn.textContent=old; }
  }
  if(mode==='login'){
    root.querySelector('#login-email').focus();
    root.querySelector('#login-show').addEventListener('change',e=>{root.querySelector('#login-password').type=e.target.checked?'text':'password'});
    root.querySelector('#login-form').addEventListener('submit',ev=>{ev.preventDefault();errBox.hidden=true;
      const email=root.querySelector('#login-email').value.trim(), pw=root.querySelector('#login-password').value; let bad=false;
      if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)){setFieldError(root,'login-email','Введите email, например name@turan-edu.kz');bad=true;}
      if(!pw){setFieldError(root,'login-password','Введите пароль');bad=true;}
      if(bad){fail('Проверьте поля, выделенные красным.');return;}
      send('/api/auth/login',{email,password:pw},'Входим…');});
  } else {
    root.querySelector('#reg-name').focus();
    root.querySelector('#reg-agree').addEventListener('change',e=>{if(e.target.checked)root.querySelector('#reg-agree-msg').textContent='';});
    const slot = root.querySelector('#reg-detail-slot');
    root.querySelectorAll('input[name="role"]').forEach(r=>r.addEventListener('change',()=>{
      root.querySelectorAll('.role-card').forEach(c=>c.classList.toggle('selected',c.querySelector('input').checked)); setFieldError(root,'reg-role','');
      const meta = ROLE_META[r.value];
      slot.innerHTML = authField('reg-detail', meta.detail + (meta.required?'':' (необязательно)'), 'text', meta.ph);
      slot.querySelector('.form-field').addEventListener('input',()=>setFieldError(root,'reg-detail',''));
    }));
    root.querySelector('#register-form').addEventListener('submit',ev=>{ev.preventDefault();errBox.hidden=true;
      const v=id=>(root.querySelector('#'+id)?.value||'').trim(); const role=root.querySelector('input[name="role"]:checked')?.value; let bad=false;
      const pw=root.querySelector('#reg-password').value, pw2=root.querySelector('#reg-password2').value;
      if(v('reg-name').length<2){setFieldError(root,'reg-name','Укажите ФИО');bad=true;}
      if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v('reg-email'))){setFieldError(root,'reg-email','Введите корректный email');bad=true;}
      if(!role){root.querySelector('#reg-role-msg').textContent='Выберите один из вариантов';bad=true;}
      else if(ROLE_META[role].required && v('reg-detail').length<2){setFieldError(root,'reg-detail',`Заполните поле «${ROLE_META[role].detail}»`);bad=true;}
      if(pw.length<8||!/\d/.test(pw)||!/[A-Za-zА-Яа-яЁё]/.test(pw)){setFieldError(root,'reg-password','Минимум 8 символов, буквы и цифра');bad=true;}
      else if(pw!==pw2){setFieldError(root,'reg-password2','Пароли не совпадают');bad=true;}
      if(!root.querySelector('#reg-agree').checked){root.querySelector('#reg-agree-msg').textContent='Подтвердите, пожалуйста';bad=true;} else root.querySelector('#reg-agree-msg').textContent='';
      if(bad){fail('Проверьте поля, выделенные красным.');return;}
      send('/api/auth/register',{full_name:v('reg-name'),email:v('reg-email'),role,detail:v('reg-detail'),password:pw},'Создаём аккаунт…');});
  }
}

function accessRow(ok,text){return `<li class="${ok?'ok':'no'}"><span>${ok?'✓':'✕'}</span>${safe(text)}</li>`;}
async function profilePage(){
  const r = await fetch('/api/auth/me'); if(r.status===401){ showAuth('login'); return; } me = (await r.json()).user; updateUserChrome();
  const meta = ROLE_META[me.role] || ROLE_META.other;
  setContent(`${title('Мой профиль','Личные данные, роль и настройки учётной записи')}
  <section class="card profile-hero"><span class="profile-avatar role-${me.role}">${safe(initials(me.full_name))}</span><div class="profile-main"><h2>${safe(me.full_name)}</h2><p>${safe(me.email)}</p><div class="tag-row"><span class="role-pill role-${me.role}">${ICONS[me.role]||''}${safe(me.role_label)}</span>${me.detail?`<span class="anomaly-badge clear">${safe(me.detail)}</span>`:''}<span class="anomaly-badge clear">В системе с ${safe(fmtDate(me.created_at))}</span></div></div><div class="access-badge ${me.can_edit?'full':'view'}">${me.can_edit?'Полный доступ':'Режим просмотра'}</div></section>
  <div class="profile-grid">
   <section class="card profile-card"><h2>Личные данные</h2><p class="card-sub">Эти данные видны только вам</p>
    <form id="profile-form" novalidate>
     <label class="form-label">ФИО<input class="form-field" id="pf-name" value="${safe(me.full_name)}" maxlength="80"><span class="field-msg" id="pf-name-msg"></span></label>
     <div class="form-grid"><label class="form-label">Роль<input class="form-field" value="${safe(me.role_label)}" disabled></label><label class="form-label">Email<input class="form-field" value="${safe(me.email)}" disabled></label></div>
     <label class="form-label">${safe(meta.detail)}<input class="form-field" id="pf-detail" value="${safe(me.detail)}" maxlength="100" placeholder="${safe(meta.ph)}"><span class="field-msg" id="pf-detail-msg"></span></label>
     <label class="form-label">О себе<textarea class="form-field" id="pf-about" rows="3" maxlength="500" placeholder="Коротко о себе: интересы, дисциплины, контакты для связи">${safe(me.about)}</textarea><span class="field-help" id="pf-about-count">${(me.about||'').length} / 500</span></label>
     <div class="form-error" id="pf-error" role="alert" hidden></div>
     <div class="modal-actions"><button class="btn" type="submit" id="pf-save">Сохранить изменения</button></div>
    </form></section>
   <section class="card profile-card"><h2>Права доступа</h2><p class="card-sub">Определяются ролью «${safe(me.role_label)}»</p>
    <ul class="access-list">${accessRow(true,'Панель мониторинга и аналитика по группам')}${accessRow(true,'Профили студентов и ИИ-анализ риска')}${accessRow(me.can_edit,'Добавление студентов в базу')}${accessRow(me.can_edit,'Назначение консультаций')}</ul>
    ${me.can_edit?'':'<p class="legend">Добавление студентов и консультации доступны преподавателям и работникам университета.</p>'}
    <h3 class="sub-h">Смена пароля</h3>
    <form id="password-form" novalidate>
     <label class="form-label">Текущий пароль<input class="form-field" id="pw-old" type="password"><span class="field-msg" id="pw-old-msg"></span></label>
     <div class="form-grid"><label class="form-label">Новый пароль<input class="form-field" id="pw-new" type="password" placeholder="Минимум 8 символов"><span class="field-msg" id="pw-new-msg"></span></label><label class="form-label">Повторите<input class="form-field" id="pw-new2" type="password"><span class="field-msg" id="pw-new2-msg"></span></label></div>
     <div class="form-error" id="pw-error" role="alert" hidden></div>
     <div class="modal-actions"><button class="btn outline" type="submit" id="pw-save">Изменить пароль</button></div>
    </form>
    <div class="logout-row"><button class="btn ghost danger" type="button" id="profile-logout">Выйти из аккаунта</button></div>
   </section></div>`);
  const root = app;
  root.querySelectorAll('.form-field').forEach(inp=>inp.addEventListener('input',()=>setFieldError(root,inp.id,'')));
  const about = root.querySelector('#pf-about'); about.addEventListener('input',()=>{root.querySelector('#pf-about-count').textContent=`${about.value.length} / 500`;});
  root.querySelector('#profile-logout').onclick = logoutNow;
  root.querySelector('#profile-form').addEventListener('submit',async ev=>{ev.preventDefault();const box=root.querySelector('#pf-error');box.hidden=true;
    const name=root.querySelector('#pf-name').value.trim(), detail=root.querySelector('#pf-detail').value.trim(); let bad=false;
    if(name.length<2){setFieldError(root,'pf-name','Укажите ФИО');bad=true;}
    if(meta.required&&detail.length<2){setFieldError(root,'pf-detail',`Заполните поле «${meta.detail}»`);bad=true;}
    if(bad)return; const btn=root.querySelector('#pf-save'); btn.disabled=true;
    try{const d=await request('/api/profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({full_name:name,detail,about:about.value})});me=d.user;toast('✓ Профиль сохранён',false,true);await profilePage();}
    catch(e){box.textContent=e.message;box.hidden=false;btn.disabled=false;}});
  root.querySelector('#password-form').addEventListener('submit',async ev=>{ev.preventDefault();const box=root.querySelector('#pw-error');box.hidden=true;
    const o=root.querySelector('#pw-old').value,n=root.querySelector('#pw-new').value,n2=root.querySelector('#pw-new2').value;let bad=false;
    if(!o){setFieldError(root,'pw-old','Введите текущий пароль');bad=true;}
    if(n.length<8||!/\d/.test(n)||!/[A-Za-zА-Яа-яЁё]/.test(n)){setFieldError(root,'pw-new','Минимум 8 символов, буквы и цифра');bad=true;}
    else if(n!==n2){setFieldError(root,'pw-new2','Пароли не совпадают');bad=true;}
    if(bad)return; const btn=root.querySelector('#pw-save'); btn.disabled=true;
    try{await request('/api/profile/password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({old_password:o,new_password:n})});toast('✓ Пароль изменён',false,true);ev.target.reset();}
    catch(e){box.textContent=e.message;box.hidden=false;}finally{btn.disabled=false;}});
}

async function boot(){
  document.getElementById('logout-btn').addEventListener('click', logoutNow);
  try{ const r = await fetch('/api/auth/me'); if(r.status===401){ showAuth('login'); return; } me = (await r.json()).user; showApp(); }
  catch(e){ showError(e); }
}

async function render(){if(!me)return;const path=decodeURI(location.hash.slice(1)||'/overview');const view=path.startsWith('/profile')?'me':path.startsWith('/student/')?'profile':path.startsWith('/students')?'students':path.startsWith('/analytics')?'analytics':'overview';markNav(view==='me'?'profile':view==='profile'?'students':view);app.innerHTML='<div class="loading"><div class="spinner"></div>Загрузка…<p class="wake-note delayed">Сервер запускается после простоя — это может занять до минуты. Пожалуйста, не закрывайте страницу.</p></div>';try{if(view==='me')await profilePage();else if(view==='students')await students();else if(view==='profile')await studentProfile(parseInt(path.split('/')[2],10),path.includes('new=1'));else if(view==='analytics')await analytics();else await overview();}catch(e){showError(e)} }
window.addEventListener('hashchange',()=>{if(me)render();});if(!location.hash)history.replaceState(null,'','#/overview');boot();
