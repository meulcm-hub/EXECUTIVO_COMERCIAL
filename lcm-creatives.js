/* Campanhas e criativos: projeção pública da coleta Meta, sem credenciais no navegador. */
(function (root) {
  'use strict';
  const DATE = /^\d{4}-\d{2}-\d{2}$/;
  const MEDIA_HOST = /(^|\.)(fbcdn\.net|facebook\.com|fbsbx\.com|cdninstagram\.com|instagram\.com)$/i;
  const LINKED = new Set(['347253318197280','626593228944023','332967835423799','1183301460107081']);
  const PROJECT_NAMES = {'347253318197280':'Jacarandá','626593228944023':'Village Lagoas','332967835423799':'Arraial Costa Verde','1183301460107081':'Jatobá'};
  const STATUS = {ACTIVE:'Ativo',PAUSED:'Pausado',CAMPAIGN_PAUSED:'Campanha pausada',ADSET_PAUSED:'Conjunto pausado',PENDING_REVIEW:'Em análise',IN_PROCESS:'Em processamento',DISAPPROVED:'Reprovado',ARCHIVED:'Arquivado',DELETED:'Excluído',WITH_ISSUES:'Com pendências',PENDING_BILLING_INFO:'Pagamento pendente'};
  const nf = new Intl.NumberFormat('pt-BR');
  const money = new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'});
  const percent = new Intl.NumberFormat('pt-BR',{maximumFractionDigits:2});
  function safeUrl(value, media) {
    if (typeof value !== 'string' || !value || /\s/.test(value)) return '';
    try {
      const url = new URL(value);
      if (url.protocol !== 'https:' || url.port || url.username || url.password || !MEDIA_HOST.test(url.hostname)) return '';
      for (const key of url.searchParams.keys()) if (/(token|auth|secret|password)/i.test(key)) return '';
      if (!media && !/(^|\.)(facebook\.com|instagram\.com)$/i.test(url.hostname)) return '';
      return url.href;
    } catch (_) { return ''; }
  }
  function nonnegative(value) {
    return value !== null && value !== '' && Number.isFinite(Number(value)) && Number(value) >= 0;
  }
  function validSource(source) {
    if (!source || source.schema_version !== 1 || !DATE.test(source.period?.since || '') || !DATE.test(source.period?.until || '') || source.period.since > source.period.until || !Array.isArray(source.ads)) return false;
    const ids = new Set();
    return source.ads.every(ad => {
      if (!ad || !/^\d+$/.test(String(ad.ad_id || '')) || !/^\d+$/.test(String(ad.account_id || '')) || !Array.isArray(ad.daily)) return false;
      const id = ad.account_id + '/' + ad.ad_id;
      if (ids.has(id)) return false;
      ids.add(id);
      const dates = new Set();
      return ad.daily.every(day => {
        if (!day || !DATE.test(day.date || '') || day.date < source.period.since || day.date > source.period.until || dates.has(day.date)) return false;
        dates.add(day.date);
        return ['impressions','clicks','spend'].every(k => nonnegative(day[k])) && ['impressions','clicks','form_leads','messages'].every(k => day[k] === undefined || (nonnegative(day[k]) && Number.isInteger(Number(day[k]))));
      });
    });
  }
  function totals(days, since, until) {
    const total = {impressions:0,clicks:0,spend:0,form_leads:0,messages:0};
    for (const day of days || []) if (day.date >= since && day.date <= until) for (const key of Object.keys(total)) total[key] += Number(day[key] || 0);
    total.cpc = total.clicks ? total.spend / total.clicks : null;
    total.ctr = total.impressions ? total.clicks / total.impressions * 100 : null;
    return total;
  }
  function matchesProject(ad, project, accountIds) {
    if (Array.isArray(accountIds)) return accountIds.map(String).includes(String(ad.account_id));
    if (!project || project === 'all') return LINKED.has(String(ad.account_id));
    return String(ad.account_id) === String(project) || ad.project === project;
  }
  function query(source, options) {
    options = options || {};
    if (!validSource(source)) return null;
    const since = options.since || source.period.since, until = options.until || source.period.until;
    if (!DATE.test(since) || !DATE.test(until) || since > until) return null;
    const overlap = since <= source.period.until && until >= source.period.since;
    const ads = source.ads.filter(ad => matchesProject(ad, options.project, options.accountIds) && (ad.daily.some(day=>day.date>=since && day.date<=until) || (ad.status==='ACTIVE' && ad.daily.length===0)) && (!options.campaign || options.campaign === 'all' || ad.account_id + '/' + ad.campaign_id === options.campaign) && (!options.media || options.media === 'all' || ad.media_type === options.media) && (!options.status || options.status === 'all' || ad.status === options.status)).map(ad => ({...ad,metrics:totals(ad.daily,since,until)}));
    const total = {impressions:0,clicks:0,spend:0,form_leads:0,messages:0};
    for (const ad of ads) for (const key of Object.keys(total)) total[key] += ad.metrics[key];
    total.cpc = total.clicks ? total.spend / total.clicks : null;
    total.ctr = total.impressions ? total.clicks / total.impressions * 100 : null;
    return {ads,total,since,until,overlap,partial:since < source.period.since || until > source.period.until};
  }
  function campaignRows(ads) {
    const groups = new Map();
    for (const ad of ads) {
      const key = ad.account_id + '/' + ad.campaign_id;
      if (!groups.has(key)) groups.set(key,{name:ad.campaign_name || 'Campanha',account_name:ad.account_name,ads:0,impressions:0,clicks:0,spend:0,form_leads:0,messages:0});
      const row = groups.get(key);row.ads++;
      for (const metric of ['impressions','clicks','spend','form_leads','messages']) row[metric] += ad.metrics[metric];
    }
    return [...groups.values()].map(row=>({...row,cpc:row.clicks?row.spend/row.clicks:null,ctr:row.impressions?row.clicks/row.impressions*100:null})).sort((a,b)=>b.spend-a.spend || a.name.localeCompare(b.name,'pt-BR'));
  }
  const api = {query,validSource,safeUrl,campaignRows};
  if (typeof document === 'undefined') { root.LcmCreatives = api; return; }
  const svgNS = 'http://www.w3.org/2000/svg';
  const paths = {
    megaphone:['M3 10v4h4l11 5V5L7 10H3Z','m7 14 2 6h3l-2-5','M21 9v6'],
    calendar:['M4 5h16v16H4z','M8 3v4M16 3v4M4 10h16'],
    impressions:['M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z','M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0'],
    clicks:['m5 3 14 9-7 2-3 7L5 3Z','m14 14 5 5'],
    spend:['M4 6c0-2 16-2 16 0s-16 2-16 0Z','M4 6v12c0 3 16 3 16 0V6M4 12c0 3 16 3 16 0'],
    leads:['M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2','M12 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0','M16 4a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-3.87'],
    cpc:['M21 11v1a9 9 0 1 1-5.34-8.23','m21 3-9 9','M16 3h5v5'],
    image:['M3 4h18v16H3z','m3 17 5-6 4 4 3-3 6 6','M9 8h.01'],
    video:['M3 5h18v14H3z','m10 9 5 3-5 3V9Z'],
    chart:['M4 20V10h4v10M10 20V4h4v16M16 20v-7h4v7'],
    compare:['M7 4v16M17 4v16M4 7h6M14 17h6','m14 7 3-3 3 3M4 17l3 3 3-3'],
    filter:['M3 4h18l-7 8v7l-4 2v-9L3 4Z'],
    close:['m6 6 12 12M18 6 6 18'],
    external:['M14 3h7v7M10 14 21 3','M21 14v7H3V3h7'],
    play:['m9 5 11 7-11 7V5Z']
  };
  function icon(name) {
    const svg=document.createElementNS(svgNS,'svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');
    for (const d of paths[name] || paths.image) {const path=document.createElementNS(svgNS,'path');path.setAttribute('d',d);svg.append(path);}
    return svg;
  }
  function el(tag, cls, value) {const node=document.createElement(tag);if(cls)node.className=cls;if(value!==undefined)node.textContent=String(value);return node;}
  function button(cls, text, handler) {const node=el('button',cls,text);node.type='button';if(handler)node.addEventListener('click',handler);return node;}
  function option(select,value,label) {const node=el('option','',label);node.value=value;select.append(node);}
  function dateLabel(date) {return DATE.test(date || '')?date.slice(8)+'/'+date.slice(5,7)+'/'+date.slice(0,4):'—';}
  function labelStatus(status) {return STATUS[status] || 'Não informado';}
  function mediaName(type) {return {video:'Vídeo',image:'Imagem',carousel:'Carrossel',unknown:'Mídia indisponível'}[type] || 'Mídia indisponível';}
  let activeController=null;
  function mount(container, settings) {
    if (typeof container === 'string') container=document.querySelector(container);
    if (!container) throw new Error('Contêiner de criativos não encontrado');
    if (container.lcmCreatives) return container.lcmCreatives;
    settings=settings || {};
    const state={source:null,error:false,loading:false,project:'all',since:null,until:null,accountIds:null,campaign:'all',media:'all',status:'ACTIVE',tab:'creatives',limit:12,sequence:0};
    container.classList.add('lcm-creatives');
    const heading=el('header','lc-header'),headingText=el('div','lc-heading-text'),title=el('h2','','Campanhas e Criativos');
    const headingIcon=el('span','lc-heading-icon');headingIcon.append(icon('megaphone'));
    headingText.append(title,el('p','','Imagens, vídeos e desempenho dos anúncios por empreendimento.'));
    const period=el('span','lc-period'),periodText=el('span');period.append(icon('calendar'),periodText);heading.append(headingIcon,headingText,period);
    const form=el('form','lc-filters');form.setAttribute('aria-label','Filtrar campanhas e criativos');
    function field(text, name) {const wrap=el('label','lc-field'),label=el('span','',text),select=el('select');select.name=name;wrap.append(label,select);form.append(wrap);return select;}
    const projectSelect=field('Empreendimento','creative-project');option(projectSelect,'all','Todos os 4 empreendimentos vinculados');
    const campaignSelect=field('Campanha','creative-campaign');option(campaignSelect,'all','Todas as campanhas');
    const mediaSelect=field('Tipo de mídia','creative-media');[['all','Todos os tipos'],['image','Imagem'],['video','Vídeo'],['carousel','Carrossel']].forEach(x=>option(mediaSelect,...x));
    const statusSelect=field('Status atual','creative-status');[['ACTIVE','Ativo'],['all','Todos os status']].forEach(x=>option(statusSelect,...x));
    const apply=button('lc-filter-button','');apply.append(icon('filter'),el('span','','Filtrar'));apply.type='submit';form.append(apply);
    const kpis=el('div','lc-kpis');
    const metrics={};
    for (const [key,label,ico] of [['impressions','Impressões','impressions'],['clicks','Cliques','clicks'],['spend','Investimento','spend'],['form_leads','Leads formulário','leads'],['cpc','CPC médio','cpc']]) {
      const card=el('div','lc-kpi'),labelEl=el('span','lc-kpi-label'),value=el('strong','','—');labelEl.append(icon(ico),el('span','',label));card.append(labelEl,value);kpis.append(card);metrics[key]=value;
    }
    const tabs=el('div','lc-tabs');tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','Visão de campanhas e criativos');
    const tabButtons={};
    for (const [key,label,ico] of [['creatives','Criativos','image'],['campaigns','Desempenho por campanha','chart'],['compare','Comparativo de criativos','compare']]) {
      const node=button('lc-tab','',()=>{state.tab=key;draw();});node.id='lc-tab-'+key;node.setAttribute('role','tab');node.setAttribute('aria-controls','lc-creative-view');node.append(icon(ico),el('span','',label));tabs.append(node);tabButtons[key]=node;
    }
    tabs.addEventListener('keydown',event=>{
      if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
      event.preventDefault();const keys=Object.keys(tabButtons);let at=keys.indexOf(state.tab);
      at=event.key==='Home'?0:event.key==='End'?keys.length-1:(at+(event.key==='ArrowRight'?1:-1)+keys.length)%keys.length;
      state.tab=keys[at];draw();tabButtons[state.tab].focus();
    });
    const message=el('p','lc-message');message.setAttribute('role','status');message.setAttribute('aria-live','polite');
    const view=el('div','lc-view');view.id='lc-creative-view';view.setAttribute('role','tabpanel');
    const footnote=el('p','lc-footnote','Status informado na coleta, não na data histórica. Anúncios ativos sem entrega também podem aparecer com zero. Impressões e cliques não representam pessoas únicas. CPC médio = investimento ÷ cliques totais.');
    container.replaceChildren(heading,form,kpis,tabs,message,view,footnote);
    let modal=null;
    function closeModal() {
      if (!modal) return;
      const previous=modal.previousFocus;modal.node.querySelectorAll('video').forEach(video=>{video.pause();video.removeAttribute('src');video.load();});
      modal.node.close();modal.node.remove();modal=null;if(previous?.isConnected)previous.focus();
    }
    function openMedia(ad, trigger) {
      closeModal();
      const dialog=el('dialog','lc-media-dialog'),dialogHeader=el('div','lc-modal-header'),dialogTitle=el('h3','',ad.name || 'Criativo'),close=button('lc-modal-close','',closeModal);
      dialogTitle.id='lc-media-title';dialog.setAttribute('aria-labelledby',dialogTitle.id);close.setAttribute('aria-label','Fechar mídia');close.append(icon('close'));dialogHeader.append(dialogTitle,close);dialog.append(dialogHeader);
      const assets=Array.isArray(ad.media)&&ad.media.length?ad.media:[{type:ad.media_type,image_url:ad.image_url,video_url:ad.video_url,permalink_url:ad.permalink_url}];
      const body=el('div','lc-modal-body');let renderable=false;
      for (const asset of assets) {
        const imageUrl=safeUrl(asset.image_url || ad.image_url,true),videoUrl=safeUrl(asset.video_url,true);
        if (asset.type==='video' && videoUrl) {
          const video=el('video','lc-modal-media');video.controls=true;video.preload='none';video.playsInline=true;if(imageUrl)video.poster=imageUrl;video.src=videoUrl;video.setAttribute('aria-label',ad.name || 'Vídeo da campanha');
          video.addEventListener('error',()=>{if(!body.querySelector('.lc-playback-note'))body.append(el('p','lc-playback-note','O vídeo está indisponível no momento. Use o link do anúncio, se disponível.'));});body.append(video);renderable=true;
        } else if (imageUrl) {const image=el('img','lc-modal-media');image.src=imageUrl;image.alt=ad.name || 'Imagem do anúncio';image.loading='lazy';image.addEventListener('error',()=>{image.hidden=true;body.append(el('p','lc-playback-note','A imagem está temporariamente indisponível.'));});body.append(image);renderable=true;}
      }
      if (!renderable || (ad.media_type==='video' && !assets.some(asset=>safeUrl(asset.video_url,true)))) body.append(el('p','lc-playback-note','A Meta não disponibilizou a reprodução direta desta mídia.'));
      if (ad.body) body.append(el('p','lc-ad-copy',ad.body));
      const link=safeUrl(ad.permalink_url,false) || assets.map(asset=>safeUrl(asset.permalink_url,false)).find(Boolean);
      if (link) {const external=el('a','lc-external-link');external.href=link;external.target='_blank';external.rel='noopener noreferrer';external.append(el('span','','Abrir anúncio na Meta'),icon('external'));body.append(external);}
      dialog.append(body);dialog.addEventListener('cancel',event=>{event.preventDefault();closeModal();});dialog.addEventListener('click',event=>{if(event.target===dialog){const rect=dialog.getBoundingClientRect();if(event.clientX<rect.left || event.clientX>rect.right || event.clientY<rect.top || event.clientY>rect.bottom)closeModal();}});
      document.body.append(dialog);modal={node:dialog,previousFocus:trigger};dialog.showModal();close.focus();
    }
    function updateOptions() {
      const source=state.source;if(!source)return;
      const previousProject=state.project;projectSelect.replaceChildren();option(projectSelect,'all','Todos os 4 empreendimentos vinculados');
      for (const id of LINKED) option(projectSelect,id,PROJECT_NAMES[id]);
      // Outras contas só surgem se a tela principal permitir sua seleção explícita.
      if(previousProject!=='all' && !LINKED.has(String(previousProject))) {
        const ad=source.ads.find(item=>String(item.account_id)===String(previousProject) || item.project===previousProject);
        if(ad)option(projectSelect,previousProject,ad.account_name || previousProject);
      }
      projectSelect.value=previousProject;
      const selected=source.ads.filter(ad=>matchesProject(ad,state.project,state.accountIds));
      const campaigns=new Map(selected.map(ad=>[ad.account_id+'/'+ad.campaign_id,ad.campaign_name || 'Campanha']));
      campaignSelect.replaceChildren();option(campaignSelect,'all','Todas as campanhas');
      [...campaigns].sort((a,b)=>a[1].localeCompare(b[1],'pt-BR')).forEach(([id,name])=>option(campaignSelect,id,name));
      if(!campaigns.has(state.campaign))state.campaign='all';campaignSelect.value=state.campaign;
      const statuses=[...new Set(selected.map(ad=>ad.status).filter(Boolean))].filter(status=>status!=='ACTIVE').sort();
      statusSelect.replaceChildren();option(statusSelect,'ACTIVE','Ativo');option(statusSelect,'all','Todos os status');statuses.forEach(status=>option(statusSelect,status,labelStatus(status)));
      if(state.status!=='ACTIVE' && state.status!=='all' && !statuses.includes(state.status))state.status='all';statusSelect.value=state.status;
    }
    function applyFilters(event) {
      if(event)event.preventDefault();state.campaign=campaignSelect.value;state.media=mediaSelect.value;state.status=statusSelect.value;state.limit=12;draw();
    }
    form.addEventListener('submit',applyFilters);[campaignSelect,mediaSelect,statusSelect].forEach(select=>select.addEventListener('change',applyFilters));
    projectSelect.addEventListener('change',()=>{const value=projectSelect.value;state.project=value;state.accountIds=null;state.limit=12;updateOptions();draw();if(settings.onProjectChange)settings.onProjectChange(value);});
    function empty(title, description, retry) {
      const node=el('div','lc-empty');node.append(icon('image'),el('strong','',title),el('p','',description));if(retry)node.append(button('lc-text-button',typeof retry==='string'?retry:'Tentar novamente',refresh));view.replaceChildren(node);
    }
    function card(ad) {
      const node=el('article','lc-creative-card'),preview=button('lc-preview',''),imageUrl=safeUrl(ad.image_url,true);
      preview.setAttribute('aria-label',(ad.media_type==='video'?'Reproduzir vídeo: ':'Ampliar criativo: ')+(ad.name || 'Anúncio'));
      if(imageUrl) {const image=el('img','lc-creative-thumb');image.src=imageUrl;image.alt=ad.name || 'Criativo da campanha';image.loading='lazy';image.decoding='async';image.addEventListener('error',()=>{image.hidden=true;preview.classList.add('lc-preview-unavailable');const placeholder=el('span','lc-media-placeholder');placeholder.append(icon(ad.media_type==='video'?'video':'image'),el('span','','Prévia indisponível'));preview.prepend(placeholder);});preview.append(image);}
      else {const placeholder=el('span','lc-media-placeholder');placeholder.append(icon(ad.media_type==='video'?'video':'image'),el('span','','Prévia indisponível'));preview.append(placeholder);}
      if(ad.media_type==='video'){const play=el('span','lc-play');play.append(icon('play'));preview.append(play);}
      if(ad.media_type==='carousel'){const count=el('span','lc-carousel-count','Carrossel'+(ad.media?.length?' · '+ad.media.length+' peças':''));preview.append(count);}
      preview.addEventListener('click',()=>openMedia(ad,preview));node.append(preview);
      const body=el('div','lc-card-body'),heading=el('div','lc-card-heading'),name=el('h3','',ad.name || 'Anúncio');name.title=ad.name || 'Anúncio';heading.append(name);body.append(heading);
      const campaign=el('p','lc-card-campaign',ad.campaign_name || 'Campanha');campaign.title=ad.campaign_name || 'Campanha';body.append(campaign);
      const status=el('span','lc-status'+(ad.status==='ACTIVE'?' is-active':''),labelStatus(ad.status));body.append(status);
      const values=el('dl','lc-card-metrics');for(const [label,value] of [['Impressões',nf.format(ad.metrics.impressions)],['Cliques',nf.format(ad.metrics.clicks)],['Investimento',money.format(ad.metrics.spend)]]){const cell=el('div');cell.append(el('dt','',label),el('dd','',value));values.append(cell);}body.append(values);
      const footer=el('div','lc-card-footer');footer.append(icon(ad.media_type==='video'?'video':'image'),el('span','',mediaName(ad.media_type)),el('span','lc-card-project',PROJECT_NAMES[ad.account_id] || ad.account_name || ''));body.append(footer);node.append(body);return node;
    }
    function table(headers, rows) {
      const wrap=el('div','lc-table-scroll'),node=el('table','lc-table'),head=el('thead'),tr=el('tr');
      for(const text of headers){const cell=el('th','',text);cell.scope='col';tr.append(cell);}head.append(tr);const body=el('tbody');
      for(const row of rows){const line=el('tr');row.forEach((value,index)=>{const cell=el(index===0?'th':'td','',value);if(index===0)cell.scope='row';line.append(cell);});body.append(line);}node.append(head,body);wrap.append(node);return wrap;
    }
    function draw() {
      periodText.textContent='Período: '+dateLabel(state.since)+' – '+dateLabel(state.until);
      for(const [key,node] of Object.entries(tabButtons)){node.setAttribute('aria-selected',String(key===state.tab));node.tabIndex=key===state.tab?0:-1;node.classList.toggle('is-selected',key===state.tab);}view.setAttribute('aria-labelledby',tabButtons[state.tab].id);
      message.textContent='';Object.values(metrics).forEach(node=>node.textContent='—');
      if(state.loading && !state.source){empty('Carregando campanhas e criativos','Consultando a última atualização automática.');return;}
      if(!state.source){empty(state.error?'Não foi possível carregar os criativos':'Criativos aguardando sincronização',state.error?'Tente novamente em instantes.':'As imagens, os vídeos e os indicadores aparecerão após a primeira coleta automática.',state.error?true:'Atualizar criativos');return;}
      const result=query(state.source,state);
      if(!result || !result.overlap){empty('Período sem cobertura de criativos','Histórico disponível de '+dateLabel(state.source.period.since)+' a '+dateLabel(state.source.period.until)+'.');return;}
      for(const key of Object.keys(metrics))metrics[key].textContent=key==='spend'?money.format(result.total[key]):key==='cpc'?(result.total.cpc===null?'—':money.format(result.total.cpc)):nf.format(result.total[key]);
      const count=result.ads.length;tabButtons.creatives.lastChild.textContent='Criativos ('+nf.format(count)+')';
      const sync=new Date(state.source.generated_at_utc);const synced=Number.isNaN(sync.getTime())?'':' · Atualizado em '+sync.toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo',dateStyle:'short',timeStyle:'short'});
      message.textContent=(result.partial?'Cobertura parcial: '+dateLabel(state.source.period.since)+' a '+dateLabel(state.source.period.until)+'. ':'')+nf.format(count)+' anúncio(s) nesta seleção'+synced+'.';
      if(state.error)message.textContent+=' A atualização falhou; exibindo a última coleta disponível.';
      if(!count){empty('Nenhum anúncio nesta seleção','Altere a campanha, o tipo de mídia ou o status atual para consultar outros criativos.');return;}
      const ads=[...result.ads].sort((a,b)=>b.metrics.spend-a.metrics.spend || String(a.name||'').localeCompare(String(b.name||''),'pt-BR'));
      if(state.tab==='creatives'){
        const grid=el('div','lc-creative-grid');ads.slice(0,state.limit).forEach(ad=>grid.append(card(ad)));view.replaceChildren(grid);
        if(ads.length>state.limit){const more=button('lc-load-more','Mostrar mais criativos',()=>{state.limit+=12;draw();});view.append(more);}
      } else if(state.tab==='campaigns') {
        view.replaceChildren(table(['Campanha','Anúncios','Impressões','Cliques','Investimento','Leads formulário','CPC médio'],campaignRows(ads).map(row=>[row.name,nf.format(row.ads),nf.format(row.impressions),nf.format(row.clicks),money.format(row.spend),nf.format(row.form_leads),row.cpc===null?'—':money.format(row.cpc)])));
      } else {
        view.replaceChildren(el('p','lc-comparison-note','Ordenado por investimento no período selecionado.'),table(['Criativo','Campanha','Tipo','Impressões','Cliques','CTR','Investimento','Leads formulário','CPC médio'],ads.map(ad=>[ad.name || 'Anúncio',ad.campaign_name || 'Campanha',mediaName(ad.media_type),nf.format(ad.metrics.impressions),nf.format(ad.metrics.clicks),ad.metrics.ctr===null?'—':percent.format(ad.metrics.ctr)+'%',money.format(ad.metrics.spend),nf.format(ad.metrics.form_leads),ad.metrics.cpc===null?'—':money.format(ad.metrics.cpc)])));
      }
    }
    async function readSource() {
      const urls=['https://raw.githubusercontent.com/meulcm-hub/EXECUTIVO_COMERCIAL/main/data/marketing-creatives.json',new URL('data/marketing-creatives.json',document.baseURI).href];
      let missing=true;
      for(const url of urls){
        try{
          const response=await fetch(url,{cache:'no-store'});
          if(response.status===404)continue;
          missing=false;if(!response.ok)continue;
          const source=await response.json();if(validSource(source))return source;
        }catch(_){missing=false;}
      }
      if(missing)return null;
      throw new Error('Coleta indisponível');
    }
    async function refresh() {
      const sequence=++state.sequence;state.loading=true;state.error=false;draw();
      try{
        const source=await readSource();
        if(!source){if(sequence!==state.sequence)return;state.loading=false;draw();return;}
        if(sequence!==state.sequence)return;state.source=source;
        if(!state.since)state.since=source.period.since;if(!state.until)state.until=source.period.until;updateOptions();
      }catch(_){if(sequence===state.sequence)state.error=true;}
      if(sequence===state.sequence){state.loading=false;draw();}
    }
    const controller={update(options){options=options || {};const changed=options.project!==undefined && String(options.project)!==String(state.project);for(const key of ['project','since','until','accountIds'])if(options[key]!==undefined)state[key]=options[key];if(changed){state.campaign='all';state.limit=12;}updateOptions();draw();},refresh,destroy(){closeModal();state.sequence++;container.replaceChildren();delete container.lcmCreatives;if(activeController===controller)activeController=null;}};
    container.lcmCreatives=controller;activeController=controller;draw();refresh();return controller;
  }
  root.LcmCreatives={...api,mount,update(options){if(activeController)activeController.update(options);},refresh(){return activeController?.refresh();}};
})(typeof globalThis!=='undefined'?globalThis:window);
