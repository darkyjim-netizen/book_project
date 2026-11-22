<template>
<section class="account-support support-page"><header><span class="support-eyebrow">고객지원</span><h1>{{ activeHeading.title }}</h1><p>{{ activeHeading.description }}</p></header>
<nav class="as-tabs" aria-label="고객지원 메뉴"><button v-for="t in tabs" :key="t.id" :aria-current="tab===t.id?'page':null" @click="chooseTab(t.id)">{{ t.label }}</button></nav>
<p v-if="error" class="as-error" role="alert">{{ error }}</p><p v-if="message" class="as-success" role="status">{{ message }}</p>
<section v-if="tab==='notices'" class="as-card"><h2>공지사항 <small class="notice-total">총 {{ noticeTotal }}건</small></h2><p v-if="!notices.length && !loading">등록된 공지사항이 없습니다.</p><ul class="as-list notice-list"><li v-for="n in notices" :key="n.notice_id"><button class="as-link notice-trigger" :aria-expanded="notice?.notice_id===n.notice_id" @click="openNotice(n.notice_id)"><span class="notice-badge" :class="noticeInfo(n).kind">{{ noticeInfo(n).label }}</span><span class="notice-title">{{ noticeInfo(n).title }}</span><span class="notice-arrow" aria-hidden="true">›</span></button><time class="notice-date" :datetime="n.published_at">{{ date(n.published_at) }}</time><p v-if="notice?.notice_id===n.notice_id" class="as-content">{{ notice.content }}</p></li></ul><div class="as-pagination"><button v-if="noticePage>1" @click="loadNotices(noticePage-1)">이전</button>{{ noticePage }} / {{ noticePages }}<button v-if="noticePage<noticePages" @click="loadNotices(noticePage+1)">다음</button></div></section>
<section v-else-if="tab==='faq'" class="as-card"><h2>자주 묻는 질문 <small class="notice-total">총 {{ faqs.length }}건</small></h2><p v-if="!faqs.length && !loading">등록된 질문이 없습니다.</p><ul class="as-list notice-list faq-list"><li v-for="f in faqs" :key="f.faq_id"><button type="button" class="as-link notice-trigger faq-trigger" :id="`faq-question-${f.faq_id}`" :aria-expanded="openedFaq===f.faq_id" :aria-controls="`faq-answer-${f.faq_id}`" @click="openedFaq=openedFaq===f.faq_id?null:f.faq_id"><span class="notice-badge">질문</span><span class="notice-title">{{ f.question }}</span><span class="notice-arrow faq-arrow" :class="{expanded:openedFaq===f.faq_id}" aria-hidden="true">›</span></button><div v-if="openedFaq===f.faq_id" :id="`faq-answer-${f.faq_id}`" class="faq-answer" role="region" :aria-labelledby="`faq-question-${f.faq_id}`"><span class="notice-badge faq-answer-badge">답변</span><p class="as-content">{{ f.answer }}</p></div></li></ul></section>
<section v-else-if="!auth.isAuthenticated" class="as-card"><h2>로그인이 필요합니다</h2><p>1:1 문의는 로그인 후 이용할 수 있습니다.</p><RouterLink :to="{name:'login',query:{redirect: route.fullPath}}">로그인하기 →</RouterLink></section>
<section v-else-if="tab==='qna'" class="qna-layout">
  <section class="as-card qna-compose"><div class="qna-heading"><span class="notice-badge">비공개 문의</span><h2>무엇을 도와드릴까요?</h2><p>문의 내용을 남겨 주시면 이곳에서 답변을 확인할 수 있어요.</p></div><form class="qna-form" @submit.prevent="submitQuestion"><label for="question-title">문의 제목</label><input id="question-title" v-model.trim="question.title" required maxlength="250" placeholder="문의하실 내용을 간단히 적어 주세요" :disabled="busy"><label for="question-content">문의 내용</label><textarea id="question-content" v-model.trim="question.content" required rows="7" placeholder="확인이 필요한 내용을 자세히 알려 주세요." :disabled="busy"></textarea><div class="qna-form-footer"><small>작성한 문의는 본인과 관리자만 확인할 수 있습니다.</small><button type="submit" :disabled="busy || !question.title.trim() || !question.content.trim()">{{ busy ? '처리 중…' : '문의 등록하기' }}</button></div></form></section>
  <section class="as-card qna-history"><h2>내 문의 <small class="notice-total">총 {{ questionTotal }}건</small></h2><div v-if="!questions.length && !loading" class="qna-empty"><span aria-hidden="true">Q</span><h3>아직 등록한 문의가 없어요</h3><p>궁금한 점을 남기면 답변을 여기서 확인할 수 있어요.</p></div><ul class="as-list notice-list"><li v-for="q in questions" :key="q.question_id"><button type="button" class="as-link notice-trigger faq-trigger" :aria-expanded="selectedQuestion?.question_id===q.question_id" @click="openQuestion(q.question_id)"><span class="notice-badge" :class="{'event':q.status==='ANSWERED'}">{{ questionStatus(q.status) }}</span><span class="notice-title">{{ q.title }}</span><span class="notice-arrow" aria-hidden="true">›</span></button><time class="notice-date" :datetime="q.created_at">{{ date(q.created_at) }}</time><div v-if="selectedQuestion?.question_id===q.question_id" class="qna-thread"><div class="qna-original"><span class="notice-badge">내 문의</span><p class="as-content">{{ selectedQuestion.content }}</p></div><p v-if="!selectedQuestion.answers.length" class="qna-waiting">답변을 기다리고 있습니다.</p><div v-for="a in selectedQuestion.answers" :key="a.answer_id" class="faq-answer"><span class="notice-badge faq-answer-badge">답변</span><p class="as-content">{{ a.content }}</p></div><button type="button" class="qna-delete" :disabled="busy" @click="deleteQuestion(q.question_id)">문의 삭제</button></div></li></ul><div v-if="qPages>1" class="as-pagination"><button :disabled="qPage<=1" @click="loadQuestions(qPage-1)">이전</button>{{ qPage }} / {{ qPages }}<button :disabled="qPage>=qPages" @click="loadQuestions(qPage+1)">다음</button></div></section>
</section></section>
</template>
<script setup>
import { computed,onMounted,reactive,ref,watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import http from '../../api/http';
import { useAuthStore } from '../../stores/authStore';
const auth=useAuthStore(), route=useRoute(), router=useRouter(), tabs=[{id:'notices',label:'공지사항'},{id:'faq',label:'FAQ'},{id:'qna',label:'1:1 문의'}];
const noticeTotal=ref(0),openedFaq=ref(null),questionTotal=ref(0);
const tab=ref('notices'),notices=ref([]),faqs=ref([]),questions=ref([]),notice=ref(null),selectedQuestion=ref(null),error=ref(''),message=ref(''),loading=ref(false),busy=ref(false),noticePage=ref(1),noticePages=ref(1),qPage=ref(1),qPages=ref(1),question=reactive({title:'',content:''});
const supportHeadings={
  notices:{title:'공지사항',description:'북적북적의 새로운 소식과 이용 안내를 확인해 보세요.'},
  faq:{title:'자주 묻는 질문',description:'궁금한 점이 있으신가요? 자주 묻는 질문에서 답을 찾아보세요.'},
  qna:{title:'1:1 문의',description:'해결되지 않은 궁금한 점을 남겨 주세요. 내 문의와 답변을 확인할 수 있어요.'}
};
const activeHeading=computed(()=>supportHeadings[tab.value]||supportHeadings.notices);
function noticeInfo(n){
  const prefixes=[...n.title.matchAll(/^((?:\[[^\]]+\]\s*)+)/g)];
  const title=n.title.replace(/^(?:\[[^\]]+\]\s*)+/, '');
  const text=prefixes[0]?.[0]||'';
  if(n.category==='SYSTEM'||text.includes('점검'))return {title,label:'점검',kind:'maintenance'};
  if(n.category==='EVENT'||text.includes('이벤트'))return {title,label:'이벤트',kind:'event'};
  return {title,label:n.is_pinned?'공지':text.includes('배송')?'배송':'안내',kind:'general'};
}
const date=s=>s?new Date(s).toLocaleDateString('ko-KR',{timeZone:'Asia/Seoul'}):'';
function fail(e){error.value=e.userMessage||'요청을 처리하지 못했습니다.'}
async function run(fn,success=''){if(busy.value)return;busy.value=true;error.value='';message.value='';try{await fn();message.value=success}catch(e){fail(e)}finally{busy.value=false}}
async function loadNotices(page=1){try{const {data}=await http.get('/api/v1/notices',{params:{page,size:10}});notices.value=data.items;noticeTotal.value=data.meta.total;noticePage.value=page;noticePages.value=data.meta.total_pages||1;notice.value=null}catch(e){fail(e)}}
async function loadQuestions(page=1){try{const {data}=await http.get('/api/v1/qna',{params:{page,size:10,only_mine:true}});questions.value=data.items;questionTotal.value=data.meta.total;selectedQuestion.value=null;qPage.value=page;qPages.value=data.meta.total_pages||1}catch(e){fail(e)}}
async function select(id){openedFaq.value=null;tab.value=id;error.value='';message.value='';loading.value=true;try{if(id==='notices')await loadNotices();if(id==='faq')faqs.value=(await http.get('/api/v1/faqs')).data;if(id==='qna'&&auth.isAuthenticated)await loadQuestions()}catch(e){fail(e)}finally{loading.value=false}}
async function openNotice(id){try{notice.value=(await http.get(`/api/v1/notices/${id}`)).data}catch(e){fail(e)}}
async function openQuestion(id){if(selectedQuestion.value?.question_id===id){selectedQuestion.value=null;return}try{selectedQuestion.value=(await http.get(`/api/v1/qna/${id}`)).data}catch(e){fail(e)}}
const questionStatus=s=>({WAITING:'답변 대기',ANSWERED:'답변 완료',CLOSED:'종료'}[s]||s);
function submitQuestion(){if(!question.title.trim()||!question.content.trim())return;run(async()=>{await http.post('/api/v1/qna',{...question,category:'ETC',is_secret:true});question.title='';question.content='';await loadQuestions()},'문의가 등록되었습니다.')}
function deleteQuestion(id){if(!window.confirm('문의를 삭제하시겠습니까?'))return;run(async()=>{await http.delete(`/api/v1/qna/${id}`);selectedQuestion.value=null;await loadQuestions()},'문의를 삭제했습니다.')}
function routeTab(){return tabs.some(t=>t.id===route.query.tab)?route.query.tab:'notices'}
function chooseTab(id){if(routeTab()===id)select(id);else router.replace({name:'support',query:{...route.query,tab:id}})}
let ready=false;watch(()=>route.query.tab,()=>{if(ready)select(routeTab())});
onMounted(async()=>{if(!auth.initialized)await auth.fetchMe();ready=true;await select(routeTab())});
</script>

<style scoped>
.account-support.support-page{box-sizing:border-box;width:100%;max-width:1440px;margin:44px auto 80px;padding:0 28px}
.account-support.support-page .as-tabs{display:flex;flex-wrap:wrap;gap:8px;margin:26px 0 24px}
.account-support.support-page .as-tabs button{padding:10px 18px;border:0;border-radius:999px;background:#f4effb;color:#5b34a8;font-weight:500;transition:background .15s,color .15s}
.account-support.support-page .as-tabs button:hover{background:#ebe1f8}
.account-support.support-page .as-tabs button[aria-current=page]{background:#6b3fc4;color:#fff;font-weight:600}
.notice-total{margin-left:8px;color:#82758d;font-size:14px;font-weight:400}
.account-support .notice-list>li{display:block;padding:20px 12px;transition:background .15s}
.account-support .notice-list>li:hover{background:#faf8fd}
.account-support .notice-trigger{display:flex;align-items:center;gap:8px;width:100%;text-align:left;white-space:normal;text-decoration:none}
.notice-title{flex:1;min-width:0;overflow-wrap:anywhere}.notice-arrow{font-size:24px;color:#9a80b3}
.notice-badge{flex:none;font-size:12px;padding:2px 8px;border-radius:6px;background:#f4effb;color:#6b3fc4;font-weight:600}
.notice-badge.maintenance{background:#fff1e6;color:#a95300}.notice-badge.event{background:#e8f7ee;color:#1f8049}
.notice-date{display:block;margin-top:8px;color:#867c8d;font-family:inherit;font-size:14px;font-variant-numeric:tabular-nums}
@media(max-width:600px){.account-support.support-page{padding:0 14px;margin-top:28px}.account-support .notice-list>li{padding:16px 0}.notice-trigger{flex-wrap:wrap}}
</style>

<style scoped>
.account-support .faq-trigger{padding:0;background:transparent;color:inherit;font:inherit;font-weight:600;border:0;border-radius:0;min-height:32px}
.account-support .faq-trigger:hover{background:transparent;color:#6841a4}
.account-support .faq-trigger:focus-visible{outline:2px solid #8664c0;outline-offset:5px;border-radius:4px}
.faq-arrow{display:inline-block;transform:rotate(90deg);transition:transform .15s ease}
.faq-arrow.expanded{transform:rotate(-90deg)}
.faq-answer{display:flex;align-items:flex-start;gap:12px;margin-top:18px;padding:18px 20px;border-radius:10px;background:#f7f3fc}
.faq-answer .as-content{flex:1;min-width:0;margin:0;line-height:1.8;color:#65556f}
.faq-answer-badge{margin-top:3px;background:#e9def7;color:#603794}
@media(max-width:600px){.faq-answer{gap:8px;padding:14px 12px}}
@media(prefers-reduced-motion:reduce){.faq-arrow{transition:none}}
</style>

<style scoped>
.qna-layout{display:grid;grid-template-columns:minmax(0,1fr);gap:24px}.qna-layout .as-card{margin:0;padding:28px;border:1px solid #e9e1f0;border-radius:16px;background:white;min-width:0}.qna-heading h2{margin:12px 0 8px;font-size:23px}.qna-heading p{color:#85758e;line-height:1.6;margin:0}.qna-form{display:grid;gap:10px;margin-top:26px}.qna-form>label{font-size:14px;font-weight:700;color:#554160;margin-top:6px}.qna-form input,.qna-form textarea{box-sizing:border-box;width:100%;border:1px solid #ded2e9;border-radius:10px;background:#fdfcfe;padding:13px 15px;font:inherit;color:#44324f}.qna-form textarea{resize:vertical;min-height:170px}.qna-form input:focus,.qna-form textarea:focus{outline:2px solid #d8c7ee;border-color:#9672c1}.qna-form-footer{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;margin-top:8px}.qna-form-footer small{color:#8b7b95;font-size:13px}.account-support .qna-form-footer button{min-height:46px;padding:0 24px;border:0;border-radius:10px;background:#6b3fc4;color:#fff;font-weight:600}.qna-form-footer button:disabled{opacity:.45;cursor:default}.qna-history h2{margin:0 0 18px}.qna-empty{text-align:center;padding:32px 16px;color:#8b7a95}.qna-empty>span{display:inline-grid;place-items:center;width:48px;height:48px;background:#f2ebfa;border-radius:50%;color:#8a65b7;font-size:24px}.qna-empty h3{font-size:17px;color:#665170;margin:14px 0 8px}.qna-empty p{font-size:14px}.qna-thread{margin-top:18px}.qna-original{padding:18px 20px;background:#faf8fc;border-radius:10px}.qna-original p{margin:12px 0 0;line-height:1.8}.qna-waiting{padding:16px;color:#8a7a93;font-size:14px}.account-support .qna-delete{display:block;margin:16px 0 0 auto;padding:8px 12px;border:1px solid #e5d8e0;border-radius:8px;background:white;color:#9a607a;font-size:13px}@media(max-width:600px){.qna-layout .as-card{padding:20px 16px}.qna-form-footer{align-items:stretch;flex-direction:column}}
</style>

<style scoped>
.support-eyebrow{display:block;margin-bottom:8px;color:#927ba4;font-size:13px;font-weight:600;letter-spacing:.04em}.support-page>header h1{margin-top:0}
</style>
