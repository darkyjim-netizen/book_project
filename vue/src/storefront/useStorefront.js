import { kyoboBestsellerSnapshot } from "./bestsellerSnapshot.js";
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { storefrontApi } from "./api.js";
import { publishedContentsByIsbn } from "./bookContents.js";
import { useAuthStore } from "../stores/authStore.js";
import http from "../api/http.js";
import { getCartStorage } from "./cartStorage.js";

const categoryGroups = [
  {
    name: "소설",
    subcategories: ["한국소설", "번역소설", "추리", "SF", "로맨스", "역사소설"],
  },
  { name: "시·에세이", subcategories: ["시", "에세이", "여행", "인생·명상"] },
  { name: "인문", subcategories: ["철학", "심리학", "역사", "종교", "문화"] },
  {
    name: "사회·정치",
    subcategories: ["정치", "사회문제", "법률", "교육", "사회학"],
  },
  {
    name: "경제·경영",
    subcategories: ["경영", "마케팅", "경제", "재테크", "투자"],
  },
  {
    name: "자기계발",
    subcategories: ["성공·처세", "시간관리", "인간관계", "습관"],
  },
  {
    name: "과학·기술",
    subcategories: ["과학", "수학", "공학", "자연과학", "환경"],
  },
  {
    name: "컴퓨터·IT",
    subcategories: [
      "프로그래밍",
      "웹 개발",
      "프로그래밍 언어",
      "데이터베이스",
      "AI",
    ],
  },
  {
    name: "어린이·청소년",
    subcategories: ["유아", "어린이 문학", "청소년 문학", "학습"],
  },
  { name: "예술·대중문화", subcategories: ["미술", "음악", "디자인", "영화"] },
  {
    name: "건강·취미·실용",
    subcategories: ["건강", "요리", "운동", "취미·생활"],
  },
  {
    name: "외국어·수험",
    subcategories: ["영어", "제2외국어", "자격증", "취업·수험"],
  },
  { name: "만화·웹툰", subcategories: ["만화", "웹툰", "그래픽노블"] },
];

const bookCategories = {
  "불편한 편의점": ["소설", "한국소설"],
  "작별하지 않는다": ["소설", "한국소설"],
  모순: ["소설", "한국소설"],
  "아주 작은 습관의 힘": ["자기계발", "습관"],
  "나는 나로 살기로 했다": ["시·에세이", "에세이"],
  역행자: ["자기계발", "성공·처세"],
  "물고기는 존재하지 않는다": ["과학·기술", "자연과학"],
  "세이노의 가르침": ["자기계발", "성공·처세"],
  "달러구트 꿈 백화점": ["소설", "한국소설"],
  "나는 메트로폴리탄 미술관의 경비원입니다": ["시·에세이", "에세이"],
  "Vue 3 풀스택 실전 웹 프로젝트": ["컴퓨터·IT", "웹 개발"],
  "인공지능을 위한 파이썬 첫 걸음": ["컴퓨터·IT", "프로그래밍 언어"],
  "Spring Boot 3 첫 걸음": ["컴퓨터·IT", "웹 개발"],
  "인공지능을 위한 PostgreSQL": ["컴퓨터·IT", "데이터베이스"],
};
// DB의 분야명과 화면에서 사용하는 분야명을 연결한다.
const databaseCategoryMap = {
  "소설/시/희곡": ["소설", ""],
  "만화/라이트노벨": ["만화·웹툰", ""],
  "수험서/자격증": ["외국어·수험", ""],
  인문학: ["인문", ""],
  어린이: ["어린이·청소년", ""],
  에세이: ["시·에세이", "에세이"],
  경제경영: ["경제·경영", ""],
  자기계발: ["자기계발", ""],
  외국어: ["외국어·수험", ""],
  "종교/역학": ["인문", "종교"],
  청소년: ["어린이·청소년", ""],
  과학: ["과학·기술", "과학"],
  유아: ["어린이·청소년", "유아"],
  "컴퓨터/모바일": ["컴퓨터·IT", ""],
  "예술/대중문화": ["예술·대중문화", ""],
  역사: ["인문", "역사"],
  사회과학: ["사회·정치", ""],
  좋은부모: ["건강·취미·실용", ""],
  "건강/취미": ["건강·취미·실용", ""],
  "요리/살림": ["건강·취미·실용", "요리"],
  여행: ["시·에세이", "여행"],
};

const bookDetails = {
  "불편한 편의점": {
    intro:
      "서울의 한 동네, 사람들이 오가며 하루를 이어가는 작은 편의점에 낯선 손님이 찾아옵니다. 기억을 잃은 채 편의점 앞을 지키던 그는 어느 날 야간 아르바이트를 맡게 되고, 계산대와 진열대 사이에서 다양한 이웃들과 마주합니다.\n\n각자의 사정으로 지쳐 있던 사람들은 서툴지만 진심 어린 대화와 예상 밖의 도움을 주고받으며 조금씩 달라집니다. 거창한 해결책 대신 따뜻한 도시락 한 끼, 누군가의 이야기를 들어주는 시간처럼 작고 구체적인 친절이 사람의 하루를 바꿀 수 있음을 보여줍니다.\n\n웃음이 번지는 장면 사이로 일과 가족, 생계에 대한 고민도 함께 흐릅니다. 평범한 동네의 여러 삶을 따라가며 서로를 이해하는 일이 얼마나 큰 위로가 되는지 그려내는 작품입니다. 바쁜 하루 끝에 마음을 잠시 쉬게 하고 싶은 독자에게 편안한 온기를 건넵니다.",
    contents: ["산해진미 도시락", "제이에스 오브 제이에스", "삼각김밥의 용도"],
    formats: ["종이책", "eBook", "오디오북"],
  },
  "작별하지 않는다": {
    intro:
      "한강의 장편소설 『작별하지 않는다』는 한 사람의 기억과 꿈을 따라가며, 제주에 남겨진 역사적 비극과 그 시간을 견뎌 온 이들의 삶을 바라봅니다. 눈과 바람이 깊게 내려앉은 풍경 속에서 소설은 과거의 상처가 현재의 사람들에게 어떻게 이어지는지 조심스럽게 묻습니다.\n\n주인공은 친구의 부탁을 받고 눈보라 속으로 향합니다. 그 여정에서 마주하는 것은 단순한 사건의 기록이 아니라, 오래 침묵해야 했던 이들의 목소리와 서로를 향한 간절한 마음입니다. 현실과 꿈, 기억과 상상이 겹쳐지며 독자는 무엇을 기억하고 어떻게 애도할 것인지 생각하게 됩니다.\n\n고통을 쉽게 설명하거나 지워버리지 않고, 끝내 곁에 남아 바라보려는 마음을 섬세한 문장으로 그려냅니다. 깊은 슬픔 속에서도 타인을 향한 사랑과 연대가 어떻게 이어지는지 오래 되새기게 하는 작품입니다.",
    contents: ["새", "밤", "불빛"],
    formats: ["종이책", "eBook"],
  },
  모순: {
    intro:
      "양귀자의 장편소설 『모순』은 스물다섯 살 안진진의 시선을 통해 가족과 사랑, 그리고 삶의 선택을 들여다봅니다. 주인공은 서로 다른 방식으로 살아가는 두 여성의 모습을 가까이에서 지켜보며, 행복과 불행을 가르는 기준이 무엇인지 고민합니다.\n\n소설은 한쪽이 옳고 다른 쪽이 틀렸다고 쉽게 결론 내리지 않습니다. 익숙한 일상 속에서 서로 반대처럼 보이는 삶의 모습이 어떻게 함께 존재하는지, 사람은 어떤 경험과 마음으로 자신의 길을 고르는지 생생한 인물과 대화로 풀어냅니다.\n\n사랑과 결혼, 가족이라는 현실적인 주제에 유머와 날카로운 관찰을 더해 읽는 재미를 줍니다. 선택의 순간마다 정답을 찾으려는 독자에게 삶의 아이러니를 돌아보게 하고, 각자의 선택을 이해하는 여지를 남기는 소설입니다.",
    contents: ["두 어머니", "두 남자", "선택의 시간"],
    formats: ["종이책", "eBook", "오디오북"],
  },
  "아주 작은 습관의 힘": {
    intro:
      "큰 목표를 세우고도 꾸준히 이어가기 어려웠다면, 이 책은 변화의 출발점을 아주 작은 행동에서 찾도록 안내합니다. 제임스 클리어는 \n습관이 만들어지고 반복되는 과정을 설명하며, 의지만 다그치기보다 행동을 시작하기 쉬운 환경을 설계하는 방법을 소개합니다.\n\n좋은 습관은 눈에 띄고 매력적이며 실행하기 쉽게 만들고, 줄이고 싶은 습관은 그 반대가 되도록 주변 조건을 조정할 수 있습니다. 매일의 작은 행동이 쌓여 결과를 만들 뿐 아니라 자신을 어떤 사람으로 여기는지에도 영향을 준다는 점을 짚습니다.\n\n완벽한 계획보다 오늘 반복할 수 있는 작고 구체적인 실천을 찾는 데 초점을 둡니다. 운동이나 공부, 업무처럼 꾸준함이 필요한 일을 바꾸고 싶은 독자가 자신의 생활에 적용해 볼 수 있는 원칙과 사례를 담은 실용서입니다.",
    contents: [
      "작은 습관의 힘",
      "정체성 중심 습관",
      "좋은 습관을 만드는 네 단계",
    ],
    formats: ["종이책", "eBook", "오디오북"],
  },
  "나는 나로 살기로 했다": {
    intro:
      "남들의 속도와 기준에 맞추느라 정작 자신의 마음을 놓치고 있지는 않을까요? 『나는 나로 살기로 했다』는 타인의 시선과 사회가 정해 둔 답에서 잠시 물러나, 내가 어떤 사람인지 차분히 돌아보도록 이끄는 에세이입니다.\n\n누군가의 평가에 흔들릴 때 마음을 지키는 방법, 모든 사람에게 이해받으려 애쓰지 않는 태도, 관계 속에서 나를 함부로 내어주지 않는 경계에 대해 이야기합니다. 불안과 부족함을 감추기보다 있는 그대로 바라보고, 자신에게 필요한 선택을 천천히 찾아가도록 돕습니다.\n\n책은 거창한 성공이나 완벽한 변화를 약속하기보다 오늘의 나를 존중하는 작은 연습을 건넵니다. 비교와 눈치에 지친 순간마다 잠시 펼쳐 읽으며, 내 삶의 방향을 다른 사람의 기준이 아닌 나의 마음에 비추어 생각해 볼 수 있습니다.\n\n따뜻한 그림과 짧은 글을 따라가다 보면 나답게 산다는 것이 무엇인지 스스로 질문하게 됩니다. 자신을 돌보는 일이 이기적인 선택이 아니라 더 건강하게 살아가기 위한 출발점임을 일깨우며, 각자의 속도로 자기 삶을 꾸려가도록 조용히 응원하는 책입니다.",
    contents: [
      "나를 존중하는 법",
      "세상과 건강하게 거리 두기",
      "나답게 살아가기",
    ],
    formats: ["종이책", "eBook"],
  },
  역행자: {
    intro:
      "『역행자』는 원하는 삶을 상상하는 데서 멈추지 않고, 생각과 행동의 반복을 바꾸는 방법을 다루는 자기계발서입니다. 저자는 사람들이 익숙한 판단과 두려움에 머무르는 이유를 살펴보고, 그 틀을 알아차리는 일이 변화의 시작이라고 설명합니다.\n\n책은 자신을 바라보는 관점을 점검하고, 원하는 모습에 맞춰 정체성과 환경을 설계하며, 배움과 실행을 꾸준히 이어가는 과정을 제안합니다. 독서와 글쓰기, 작은 도전처럼 일상에서 시작할 수 있는 행동을 통해 생각의 폭을 넓히고 경험을 쌓는 흐름을 소개합니다.\n\n경제적 자유를 향한 구체적인 목표와 함께 실패를 해석하고 다음 시도를 준비하는 태도도 강조합니다. 제시된 방법을 자신의 상황에 맞게 검토하고 실천하며, 삶의 선택지를 넓히고 싶은 독자에게 생각할 거리와 실행의 단서를 주는 책입니다.",
    contents: ["자의식 해체", "정체성 만들기", "실행과 반복"],
    formats: ["종이책", "eBook", "오디오북"],
  },
  "물고기는 존재하지 않는다": {
    intro:
      "룰루 밀러는 과학자 데이비드 스타 조던의 삶을 추적하며, 세상을 질서 있게 나누고 이름 붙이려는 인간의 욕구를 돌아봅니다. 물고기를 분류하는 일에 평생을 바친 한 과학자의 이야기는 자연을 이해하려는 열정과 그 믿음의 한계를 함께 보여줍니다.\n\n저자는 개인적인 상실과 혼란 속에서 조던의 기록을 따라가고, 분류 체계가 무너지는 순간에도 세계가 계속된다는 사실과 마주합니다. 과학의 역사, 생명의 다양성, 인간이 만들어 온 위계에 대한 질문이 한 사람의 탐구와 교차합니다.\n\n이 책은 지식과 믿음을 무조건 부정하거나 찬양하는 대신, 우리가 당연하게 여기는 기준이 누구에게 어떤 영향을 주는지 살펴보게 합니다. 예상하지 못한 전개와 사적인 성찰이 어우러진 논픽션으로, 불확실한 세계를 바라보는 시선을 넓혀 줍니다.",
    contents: ["분류의 세계", "삶의 궤적", "질서 너머의 질문"],
    formats: ["종이책", "eBook", "오디오북"],
  },
  "세이노의 가르침": {
    intro:
      "『세이노의 가르침』은 돈과 일, 시간과 관계를 대하는 현실적인 태도를 여러 글을 통해 전합니다. 저자는 막연한 위로나 성공담에 기대기보다 자신의 선택과 습관을 점검하고, 필요한 일을 직접 배우며 삶의 기반을 다져야 한다고 말합니다.\n\n사회생활과 경제적 자립, 공부와 자기관리처럼 일상에서 부딪히는 주제를 단호하고 구체적인 관점으로 다룹니다. 때로는 거친 표현으로 익숙한 생각을 흔들고, 독자가 자신의 상황을 냉정하게 살펴보도록 질문을 던집니다.\n\n모든 조언을 그대로 받아들이기보다 자신의 환경과 가치관에 비추어 읽을 때 실질적인 생각거리를 얻을 수 있습니다. 삶을 바꾸고 싶지만 어디서부터 시작할지 막막한 독자에게 행동과 책임의 의미를 돌아보게 하는 글 모음입니다.",
    contents: ["삶의 자세", "일과 성장", "돈을 대하는 태도"],
    formats: ["종이책", "eBook"],
  },
  "달러구트 꿈 백화점": {
    intro:
      "잠든 사람만 들어갈 수 있는 신비한 백화점, 달러구트 꿈 백화점에는 저마다 다른 마음을 품은 손님들이 찾아옵니다. 신입 직원 페니는 꿈을 고르고 판매하는 일을 배우며 여러 손님의 사연과 꿈을 마주합니다.\n\n누군가는 용기를 얻고 싶어 하고, 누군가는 지나간 시간을 다시 만나고 싶어 합니다. 꿈을 둘러싼 기발한 설정과 에피소드가 이어지는 가운데, 인물들은 자신이 무엇을 바라고 어떤 마음을 외면해 왔는지 조금씩 깨닫습니다.\n\n현실의 걱정과 소망을 판타지의 언어로 풀어내어 가볍게 읽히면서도 따뜻한 여운을 남깁니다. 상상력 가득한 세계를 여행하고 싶은 독자에게 즐거움을 주고, 잠시 멈춰 자신의 바람을 돌아보게 하는 이야기입니다.",
    contents: ["꿈 백화점에 오신 것을 환영합니다", "단골손님", "꿈과 마음"],
    formats: ["종이책", "eBook", "오디오북"],
  },
  "나는 메트로폴리탄 미술관의 경비원입니다": {
    intro:
      "패트릭 브링리의 에세이는 뉴욕 메트로폴리탄 미술관에서 경비원으로 일한 시간을 돌아봅니다. 가까운 이를 잃은 뒤 일상의 속도를 늦추고자 미술관에 들어선 저자는, 작품을 지키며 매일 같은 공간을 오래 바라보게 됩니다.\n\n방과 방을 오가며 마주한 그림과 조각, 동료와 관람객의 모습은 상실 이후의 시간을 천천히 채웁니다. 작품에 담긴 역사와 아름다움뿐 아니라 그 앞에 머무는 사람들의 표정과 사소한 대화가 조용히 기록됩니다.\n\n미술관은 슬픔을 단번에 없애 주는 장소라기보다, 감정을 서두르지 않고 살아갈 수 있도록 시간을 내어주는 공간으로 그려집니다. 예술을 바라보는 경험과 회복의 과정을 함께 따라가며, 바쁜 일상에서 잠시 멈춰 주변을 새롭게 보는 기쁨을 전하는 에세이입니다.",
    contents: ["미술관에서의 하루", "작품 앞에 머무는 시간", "상실과 회복"],
    formats: ["종이책", "eBook", "오디오북"],
  },
  "Vue 3 풀스택 실전 웹 프로젝트": {
    intro:
      "Vue 3를 활용해 실제 웹 애플리케이션을 만들어 가며 프런트엔드와 서버 개발의 흐름을 익히는 실습형 안내서입니다. 기본 문법을 살펴본 뒤 컴포넌트와 Composition API를 사용해 화면을 구성하고, 필요한 기능을 단계적으로 구현하도록 돕습니다.\n\n개발 환경과 도구 설정부터 데이터 처리, 화면과 서버의 연결까지 프로젝트에서 자주 만나는 과정을 따라갑니다. 개념 설명에 그치지 않고 코드 작성과 실행을 반복해 결과를 확인할 수 있도록 구성되어 있습니다.\n\nVue를 처음 접하거나 배운 내용을 하나의 서비스로 연결해 보고 싶은 독자는 예제를 변형하며 자신의 프로젝트로 확장할 수 있습니다. 실전 개발 과정과 문제 해결 경험을 쌓고 포트폴리오의 토대를 마련하는 데 활용할 수 있는 책입니다.",
    contents: [
      "Vue 3 기초와 핵심 개념",
      "Composition API와 개발 도구",
      "실전 웹 프로젝트와 포트폴리오",
    ],
    formats: ["종이책"],
  },
  "인공지능을 위한 파이썬 첫 걸음": {
    intro:
      "파이썬을 처음 배우는 독자가 기초 문법부터 데이터와 인공지능을 다루는 단계까지 차근차근 익히도록 돕는 입문서입니다. 변수와 자료형, 조건문과 반복문 같은 핵심 개념을 실습으로 확인하고, 작은 프로그램을 직접 작성하며 코딩의 기본기를 다집니다.\n\n기초를 익힌 뒤에는 데이터 처리와 분석에 필요한 도구를 살펴보고, 인공지능과 자연어 처리의 기본 원리를 파이썬 코드로 경험합니다. 각 주제를 실제 입력과 결과를 확인하는 흐름으로 접해, 문법이 활용되는 맥락을 이해할 수 있도록 구성했습니다.\n\n처음부터 모든 내용을 암기하기보다 직접 실행하고 수정하는 연습에 초점을 둡니다. 파이썬으로 데이터와 인공지능 분야를 시작하려는 학습자가 다음 단계의 프로젝트로 나아갈 수 있도록 기초를 다져 주는 책입니다.",
    contents: [
      "파이썬 문법과 자료 구조",
      "데이터 분석 라이브러리 실습",
      "자연어 처리와 인공지능 기초",
    ],
    formats: ["종이책"],
  },
  "Spring Boot 3 첫 걸음": {
    intro:
      "Spring과 Spring Boot를 처음 접하는 개발자를 위해 웹 애플리케이션의 구성 원리와 구현 과정을 단계별로 설명하는 입문서입니다. 객체를 관리하는 방식과 의존성 주입 등 핵심 개념을 이해한 뒤, Spring Boot 프로젝트를 만들고 기능을 연결하는 흐름을 익힙니다.\n\n웹 요청과 응답, 데이터베이스 연동, 인증과 보안 같은 서비스 개발의 기본 요소를 코드로 다룹니다. JPA를 이용한 데이터 처리와 필요한 확장 기술도 소개해, 각각의 기능이 애플리케이션 안에서 어떤 역할을 하는지 살펴볼 수 있습니다.\n\n기능을 하나씩 구현하면서 프레임워크의 구조를 익히고, 오류가 발생했을 때 원인을 좁혀 가는 개발 흐름을 연습할 수 있습니다. Java 기반 백엔드 개발을 시작하거나 기존 지식을 실제 프로젝트 형태로 정리하고 싶은 독자에게 적합한 안내서입니다.",
    contents: [
      "IoC·DI와 Spring 핵심",
      "Spring Boot 웹 애플리케이션",
      "JPA·Security·WebFlux 실습",
    ],
    formats: ["종이책"],
  },
  "인공지능을 위한 PostgreSQL": {
    intro:
      "PostgreSQL을 처음 다루는 독자가 데이터베이스의 기본 원리부터 실제 서비스 운영까지 익힐 수 있도록 안내하는 실습형 도서입니다. 테이블과 관계를 설계하고 SQL로 데이터를 조회·수정하는 기초를 다진 뒤, 애플리케이션에서 데이터베이스를 활용하는 방법을 살펴봅니다.\n\n데이터를 안전하게 관리하기 위한 권한과 보안, 백업과 복구, 성능 점검 등 운영에 필요한 주제도 다룹니다. 이어서 Python과 FastAPI 기반 서비스가 PostgreSQL과 연결되는 흐름을 따라가며, 인공지능 기능을 사용하는 애플리케이션에서 데이터가 어떻게 저장되고 전달되는지 경험합니다.\n\n개념 설명과 실행 과정을 함께 익혀 데이터베이스를 단순한 저장소가 아닌 서비스의 기반으로 이해하도록 돕습니다. PostgreSQL을 활용한 웹 서비스나 인공지능 프로젝트를 직접 구성하고 싶은 학습자에게 실무적인 출발점을 제공합니다.",
    contents: [
      "데이터 모델링과 SQL",
      "운영·보안·백업 및 성능 관리",
      "FastAPI와 AI 서비스 연동",
    ],
    formats: ["종이책"],
  },
};

const bannerTones = ["sage", "mist", "sun"];

const defaultHomeCategories = [
  {
    name: "전체",
    icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="6" height="6" rx="1.5"/><rect x="14" y="4" width="6" height="6" rx="1.5"/><rect x="4" y="14" width="6" height="6" rx="1.5"/><rect x="14" y="14" width="6" height="6" rx="1.5"/></svg>',
  },
  {
    name: "소설",
    icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4.5h10a3 3 0 0 1 3 3v12H8a3 3 0 0 1-3-3z"/><path d="M8 19.5a3 3 0 0 1-3-3v-12M9 9h6M9 13h6"/></svg>',
  },
  {
    name: "시·에세이",
    icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5c-2 0-3 1.5-3 3.5S6 12 8 12h2v7H5M16 5c-2 0-3 1.5-3 3.5s1 3.5 3 3.5h2v7h-5"/></svg>',
  },
  {
    name: "인문",
    icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 20h18M5 20V9l7-5 7 5v11M9 20v-6h6v6M8 10h.01M16 10h.01"/></svg>',
  },
  {
    name: "경제·경영",
    icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 19V5M4 19h17M7 15l4-4 3 2 6-7M16 6h4v4"/></svg>',
  },
  {
    name: "자기계발",
    icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><path d="m12 12 6-6M15 6h3v3"/></svg>',
  },
  {
    name: "컴퓨터·IT",
    icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4M8 9l-2 2 2 2M16 9l2 2-2 2M13.5 8l-3 6"/></svg>',
  },
];

const curationNotes = {
  "불편한 편의점":
    "따뜻한 이야기와 익숙한 일상으로 소설을 처음 읽는 분도 편하게 시작할 수 있어요.",
  "나는 나로 살기로 했다":
    "짧은 문장으로 자기 마음을 돌아보게 하는 에세이입니다.",
  모순: "가족과 삶의 선택을 흥미롭게 따라가는 한국 소설 입문작입니다.",
  "아주 작은 습관의 힘":
    "일상에 바로 적용할 수 있는 작은 실천을 알려주는 책입니다.",
  "물고기는 존재하지 않는다":
    "과학과 삶을 연결해 생각할 거리를 건네는 논픽션입니다.",
};

export function bookCoverUrl(book) {
  if (!book) return "";
  if (book.cover_image) return book.cover_image;
  if (book.isDatabaseBook) return "/assets/covers/category-default.png";
  if (book.id >= 1 && book.id <= 10)
    return `/assets/covers/book-${book.id}.jpg`;
  const addedBookCovers = {
    11: "book-11.png",
    12: "book-12.png",
    13: "book-13.png",
    14: "book-14.png",
  };
  return addedBookCovers[book.id]
    ? `/assets/covers/${addedBookCovers[book.id]}`
    : "";
}

let tossScriptPromise;
function loadTossPayments() {
  if (window.TossPayments) return Promise.resolve();
  if (tossScriptPromise) return tossScriptPromise;
  tossScriptPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://js.tosspayments.com/v2/standard";
    script.async = true;
    const timeout = setTimeout(() => fail(), 15000);
    function fail() {
      clearTimeout(timeout);
      script.remove();
      reject(
        new Error(
          "토스 결제창을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.",
        ),
      );
    }
    script.onerror = fail;
    script.onload = () => {
      if (!window.TossPayments) return fail();
      clearTimeout(timeout);
      resolve();
    };
    document.head.appendChild(script);
  }).catch((error) => {
    tossScriptPromise = null;
    throw error;
  });
  return tossScriptPromise;
}

export function useStorefront() {
  const route = useRoute();
  const router = useRouter();
  const auth = useAuthStore();
  const postalOpen = ref(false),
    postalKeyword = ref(""),
    postalResults = ref([]),
    postalPage = ref(1),
    postalSubmitted = ref(""),
    postalLoading = ref(false),
    postalMessage = ref("");
  async function searchPostal(nextPage) {
    const query = nextPage ? postalSubmitted.value : postalKeyword.value.trim();
    if (query.length < 2 || postalLoading.value) return;
    postalLoading.value = true;
    postalMessage.value = "";
    postalResults.value = [];
    try {
      postalSubmitted.value = query;
      postalPage.value = nextPage || 1;
      postalResults.value = await storefrontApi.searchAddresses(
        query,
        postalPage.value,
      );
      if (!postalResults.value.length)
        postalMessage.value = "검색 결과가 없습니다.";
    } catch (error) {
      postalMessage.value = error.message || "주소 검색에 실패했습니다.";
    } finally {
      postalLoading.value = false;
    }
  }
  function selectPostal(item) {
    delivery.value.postalCode = item.zip_code;
    delivery.value.address = item.road_address || item.jibun_address;
    delivery.value.addressDetail = "";
    postalOpen.value = false;
    nextTick(() => document.getElementById("checkout-address-detail")?.focus());
  }
  const view = computed(() => route.meta.storefrontView);
  const searchQuery = ref("");
  const selectedHomeCategory = ref("전체");
  const selectedMajor = ref("");
  const selectedSub = ref("");
  const activeBanner = ref(0);
  const wishlist = ref(new Set());
  const wishPending = new Set();
  let wishGeneration = 0;
  let wishesReady = false;
  const guestWishKey = "bookjjeok-guest-wishlist";
  const canWish = computed(() => auth.initialized && !auth.isAdmin);
  watch(
    () => [auth.initialized, auth.user?.id, auth.isAdmin],
    async ([initialized, memberId, isAdmin]) => {
      const generation = ++wishGeneration;
      wishesReady = false;
      wishlist.value = new Set();
      if (!initialized) return;
      if (isAdmin) return;
      if (!memberId) {
        try {
          wishlist.value = new Set(
            JSON.parse(localStorage.getItem(guestWishKey) || "[]"),
          );
        } catch {
          wishlist.value = new Set();
        }
        wishesReady = true;
        return;
      }
      try {
        const first = await storefrontApi.wishlist();
        const rest = await Promise.all(
          Array.from(
            { length: Math.max(0, (first.meta?.total_pages || 1) - 1) },
            (_, i) => storefrontApi.wishlist(i + 2),
          ),
        );
        if (generation !== wishGeneration) return;
        wishlist.value = new Set(
          [first, ...rest].flatMap((page) =>
            page.items.map((book) => String(book.book_id)),
          ),
        );
        wishesReady = true;
      } catch {
        if (generation === wishGeneration)
          showToast("찜 목록을 불러오지 못했어요. 새로고침해 주세요.");
      }
    },
    { immediate: true },
  );
  const cartStorage = getCartStorage();
  const cart = ref([]);
  const selectedCart = ref(new Set());
  let cartOwner;
  function persistCart() {
    cartStorage.save(cartOwner, cart.value);
  }
  watch(
    () => [auth.initialized, auth.user?.id ?? null],
    ([initialized, memberId]) => {
      if (!initialized) return;
      if (cartOwner !== undefined && cartOwner !== memberId)
        cartStorage.resetGuest();
      cartOwner = memberId;
      cart.value = cartStorage.load(memberId);
      selectedCart.value = new Set(cart.value.map((_, index) => index));
    },
    { immediate: true, flush: "sync" },
  );
  const lastOrder = ref(null);
  const orderHistory = ref(
    JSON.parse(localStorage.getItem("bookjjeok-orders") || "[]"),
  );
  const myProfile = ref({
    name: "",
    phone: "",
    postalCode: "",
    address: "",
    addressDetail: "",
    ...JSON.parse(localStorage.getItem("bookjjeok-profile") || "{}"),
  });
  if (myProfile.value.addressDetail) {
    myProfile.value.address = [
      myProfile.value.address,
      myProfile.value.addressDetail,
    ]
      .filter(Boolean)
      .join(" ");
    myProfile.value.addressDetail = "";
  }
  const profileDraft = ref({ ...myProfile.value });
  const delivery = ref({
    name: "",
    phone: "",
    postalCode: "",
    address: "",
    addressDetail: "",
  });
  const isEditingProfile = ref(false);
  const adminExtra = ref(
    JSON.parse(localStorage.getItem("bookjjeok-admin-books") || "[]"),
  );
  const adminOverrides = ref(
    JSON.parse(localStorage.getItem("bookjjeok-book-overrides") || "{}"),
  );
  const adminDeletedIds = ref(
    JSON.parse(localStorage.getItem("bookjjeok-deleted-books") || "[]"),
  );
  const databaseBooks = ref(null);
  const productBook = ref(null);
  const catalogLoading = ref(true),
    catalogError = ref("");
  const productPanel = ref("intro");
  const productDetail = ref(null);
  const publishedContents = computed(
    () => publishedContentsByIsbn[productBook.value?.isbn13],
  );
  const productDetailStatus = ref("");
  const productIntroduction = computed(() => {
    const detail = productDetail.value;
    const clean = (value) => (value || "").trim();
    const comparable = (value) => clean(value).replace(/\s+/g, " ");
    const summary = clean(detail?.summary);
    const description = clean(detail?.description);
    const review = clean(detail?.publisher_review);
    const contains = (a, b) => b && comparable(a).includes(comparable(b));
    const showSummary = summary && !contains(description, summary);
    const showDescription = description && !contains(summary, description);
    const intro = [
      showSummary ? summary : "",
      showDescription ? description : "",
    ].filter(Boolean);
    if (!intro.length && (summary || description))
      intro.push(description || summary);
    const showReview = review && !intro.some((text) => contains(text, review));
    return { intro, review: showReview ? review : "" };
  });
  const productReviews = ref(null);
  const reviewStats = ref(null);
  const reviewSort = ref("recent");
  const reviewRating = ref("");
  const ratingCount = computed(() =>
    Object.values(reviewStats.value?.rating_distribution || {}).reduce(
      (total, count) => total + count,
      0,
    ),
  );
  const reviewCount = computed(
    () =>
      reviewStats.value?.review_count ??
      productDetail.value?.review_count ??
      (!reviewRating.value ? productReviews.value?.meta.total : undefined),
  );
  const reviewPage = ref(1);
  const reviewsStatus = ref("");
  const reviewDraft = ref({ rating: 0, content: "" });
  const reviewMessage = ref("");
  const reviewSubmitting = ref(false);

  watch(productBook, async (book, _, onCleanup) => {
    let current = true;
    onCleanup(() => {
      current = false;
    });
    productPanel.value = "intro";
    productDetail.value = null;
    productDetailStatus.value = "";
    productReviews.value = null;
    reviewStats.value = null;
    reviewSort.value = "recent";
    reviewRating.value = "";
    reviewsStatus.value = "";
    reviewPage.value = 1;
    reviewDraft.value = { rating: 0, content: "" };
    reviewMessage.value = "";
    reviewSubmitting.value = false;
    if (!book?.isDatabaseBook) return;
    productDetailStatus.value = "loading";
    loadProductReviews(book);
    loadReviewStats(book);
    try {
      const detail = await storefrontApi.getBook(book.id);
      if (current) {
        productDetail.value = detail;
        productDetailStatus.value = "";
      }
    } catch {
      if (current) productDetailStatus.value = "error";
    }
  });

  async function loadProductReviews(book, page = 1) {
    if (!book?.isDatabaseBook || reviewsStatus.value === "loading") return;
    reviewPage.value = page;
    reviewsStatus.value = "loading";
    try {
      const response = await storefrontApi.listBookReviews(
        book.id,
        page,
        reviewSort.value,
        reviewRating.value,
      );
      if (productBook.value !== book) return;
      productReviews.value = response;
      reviewsStatus.value = "";
    } catch {
      if (productBook.value === book) reviewsStatus.value = "error";
    }
  }

  async function loadReviewStats(book) {
    try {
      const stats = await storefrontApi.getBookReviewStats(book.id);
      if (productBook.value === book) reviewStats.value = stats;
    } catch {
      if (productBook.value === book) reviewStats.value = null;
    }
  }

  async function submitProductReview() {
    const book = productBook.value;
    const { rating, content } = reviewDraft.value;
    if (
      !book?.isDatabaseBook ||
      !rating ||
      content.trim().length < 10 ||
      reviewSubmitting.value ||
      reviewsStatus.value === "loading"
    )
      return;
    reviewSubmitting.value = true;
    reviewMessage.value = "";
    try {
      await storefrontApi.createReview({
        book_id: book.id,
        rating,
        content: content.trim(),
      });
      if (productBook.value !== book) return;
      reviewDraft.value = { rating: 0, content: "" };
      reviewMessage.value = "리뷰를 등록했습니다.";
      await Promise.all([loadProductReviews(book), loadReviewStats(book)]);
    } catch (error) {
      if (productBook.value === book)
        reviewMessage.value =
          error.status === 401
            ? "로그인 후 리뷰를 작성할 수 있습니다."
            : error.message;
    } finally {
      if (productBook.value === book) reviewSubmitting.value = false;
    }
  }
  const productSourcePath = ref("/domestic");
  const toastMessage = ref("");
  const toastWishLink = ref(false);
  const addedCartTitle = ref("");
  const cartAlreadyAdded = ref(false);
  const cartDialog = ref(null);
  const cartDeleteTargets = ref(null);
  const cartDeleteMode = ref("selected");
  const cartDeleteComplete = ref(false);
  let cartDialogTrigger = null;
  const showBookForm = ref(false);
  const editingBookId = ref(null);
  const adminQuery = ref("");
  const adminCategory = ref("전체");
  const adminStock = ref("전체 상태");
  const bookForm = ref({
    title: "",
    author: "",
    major: "소설",
    subcategory: "한국소설",
    price: 0,
    stock: 10,
    publisher: "",
  });
  const adminUserId = ref(localStorage.getItem("book-saved-id") || "");
  const adminPassword = ref("");
  const rememberAdminId = ref(Boolean(adminUserId.value));
  const showAdminPassword = ref(false);
  const adminLoginError = ref("");
  const signupConsent = ref(false);
  const signupError = ref("");
  const signupForm = ref({
    id: "",
    password: "",
    name: "",
    phone: "",
    email: "",
  });
  const adminTodayLabel = new Intl.DateTimeFormat("ko-KR", {
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(new Date());
  const adminMetrics = [
    {
      title: "총 매출",
      value: "₩12,840,000",
      change: "↗ 12.8%",
      caption: "이번 달 누적",
      icon: "₩",
      tone: "mint",
    },
    {
      title: "누적 회원 수",
      value: "1,284명",
      change: "↗ 34명",
      caption: "이번 달 신규 가입",
      icon: "♙",
      tone: "lavender",
    },
    {
      title: "일별 주문 건수",
      value: "86건",
      change: "↗ 12건",
      caption: "어제 대비",
      icon: "▤",
      tone: "blue",
    },
  ];
  const adminProfile = [
    { label: "사용자명", value: "시스템 관리자" },
    { label: "사용자 유형", value: "시스템 관리 사용자" },
    {
      label: "사용 목적",
      value: "시스템 사용자·권한 및 북스토어 플랫폼 공통 코드 관리",
    },
    {
      label: "주요 업무",
      value: "회원·임직원 계정 관리, 권한 관리, 시스템 기본정보·공통 코드 관리",
    },
    { label: "주요 권한", value: "사용자·권한 C/R/U/D, 시스템 기본정보 관리" },
    {
      label: "주요 입력정보",
      value: "사용자(임직원) 정보, 권한 정보, 시스템 공통 코드",
    },
    {
      label: "주요 활용정보",
      value: "사용자 목록, 권한 정보, 시스템 기본정보",
    },
    {
      label: "업무 목표",
      value: "계정과 권한을 체계적으로 관리하고 안정적인 플랫폼 운영 지원",
    },
    { label: "시스템 사용빈도", value: "상시·반복적 사용" },
  ];
  const workload = [
    { label: "서울", value: 38, note: "주문 비중 38%", tone: "mint" },
    { label: "경기", value: 27, note: "주문 비중 27%", tone: "lavender" },
    { label: "부산", value: 13, note: "주문 비중 13%", tone: "blue" },
    { label: "인천", value: 12, note: "주문 비중 12%", tone: "peach" },
    { label: "기타 지역", value: 10, note: "주문 비중 10%", tone: "mint" },
  ];
  const workloadMix = [
    { label: "10대 이하", count: 12, value: 12, tone: "mint" },
    { label: "20대", count: 28, value: 28, tone: "lavender" },
    { label: "30대", count: 31, value: 31, tone: "blue" },
    { label: "40대", count: 19, value: 19, tone: "peach" },
    { label: "50대 이상", count: 10, value: 10, tone: "mint" },
  ];
  const adminDonutStyle = {
    background:
      "conic-gradient(#52b9a1 0 12%, #8064c9 12% 40%, #4882ba 40% 71%, #dc874c 71% 90%, #8bbba7 90% 100%)",
  };
  let toastTimer;
  let refreshTimer;
  const refreshBooks = () => {
    if (
      !document.hidden &&
      !["adminDashboard", "adminOrderDetail"].includes(route.name)
    )
      loadDatabaseBooks();
  };

  const allBooks = computed(() => databaseBooks.value || []);
  const bestSellerBooks = computed(() => {
    const normalize = (value) =>
      (value || "").replace(/[\s:：]/g, "").toLowerCase();
    const query = searchQuery.value.trim().toLowerCase();
    return kyoboBestsellerSnapshot
      .map((entry, index) => ({
        ...entry,
        rank: index + 1,
        book:
          allBooks.value.find((book) => book.isbn13 === entry.isbn) ||
          allBooks.value.find(
            (book) =>
              normalize(book.title) === normalize(entry.title) &&
              normalize(book.author).includes(normalize(entry.author)),
          ),
      }))
      .filter(
        (entry) =>
          !query ||
          `${entry.title} ${entry.author} ${entry.publisher}`
            .toLowerCase()
            .includes(query),
      );
  });
  // 슬라이더도 고정 제목이 아니라 현재 DB의 판매 도서를 사용한다.
  const banners = computed(() =>
    allBooks.value.slice(0, 3).map((book, index) => ({
      book: book.title,
      label: "북적북적 추천 도서",
      copy: `${book.author} · ${majorFor(book)}`,
      tone: bannerTones[index % bannerTones.length],
    })),
  );
  const cartBooks = computed(() =>
    cart.value
      .map((item, index) => {
        const title = typeof item === "string" ? item : item.title;
        const book = findBook(title);
        return book
          ? {
              ...book,
              quantity:
                typeof item === "string"
                  ? 1
                  : Math.max(1, Number(item.quantity || 1)),
              cartIndex: index,
              cartKey: String(book.id || book.title) + "-" + index,
            }
          : null;
      })
      .filter(Boolean),
  );
  const selectedCartBooks = computed(() =>
    cartBooks.value.filter((book) => selectedCart.value.has(book.cartIndex)),
  );
  const backendProducts = ref([]);
  const checkoutReady = ref(false);
  const checkoutMessage = ref("");
  const checkoutLoading = ref(false);
  const checkoutSubmitting = ref(false);
  const checkoutCoupons = ref([]),
    selectedCouponId = ref(""),
    couponLoading = ref(false),
    couponError = ref("");
  const selectedCoupon = computed(
    () =>
      checkoutCoupons.value.find(
        (coupon) =>
          String(coupon.member_coupon_id) === String(selectedCouponId.value),
      ) || null,
  );
  const couponDiscount = computed(() =>
    Number(selectedCoupon.value?.discount_amount || 0),
  );
  const paymentMethod = ref("CARD");
  const checkoutPaymentMode = ref("toss");
  const ordererEmail = ref(""); // 비회원 주문 조회에 쓰는 이메일
  const productByTitle = computed(
    () =>
      new Map(backendProducts.value.map((product) => [product.title, product])),
  );
  const checkoutTotal = computed(() =>
    selectedCartBooks.value.reduce((sum, book) => {
      const product = productByTitle.value.get(book.title);
      return sum + Number(product?.price || 0) * book.quantity;
    }, 0),
  );
  const cartSubtotal = computed(() =>
    selectedCartBooks.value.reduce(
      (sum, book) => sum + Number(book.price || 0) * book.quantity,
      0,
    ),
  );
  const cartTotal = computed(() =>
    selectedCartBooks.value.reduce(
      (sum, book) =>
        sum +
        Number(book.price || 0) *
          (1 - Number(book.discount || 0) / 100) *
          book.quantity,
      0,
    ),
  );
  const cartDiscount = computed(() => cartSubtotal.value - cartTotal.value);
  const homeCategories = computed(() => {
    const availableNames = new Set(
      allBooks.value.map(majorFor).filter(Boolean),
    );
    const orderedNames = categoryGroups.map((group) => group.name);
    const names = [
      ...orderedNames.filter((name) => availableNames.has(name)),
      ...[...availableNames]
        .filter((name) => !orderedNames.includes(name))
        .sort((a, b) => a.localeCompare(b, "ko")),
    ];
    return ["전체", ...names].map(
      (name) =>
        defaultHomeCategories.find((item) => item.name === name) || {
          name,
          icon: defaultHomeCategories[0].icon,
        },
    );
  });
  const selectedGroup = computed(() =>
    categoryGroups.find((group) => group.name === selectedMajor.value),
  );
  const homeSort = ref("sales"),
    categorySort = ref("default");
  const domesticSortOptions = [
    { value: "sales", label: "판매량순" },
    { value: "newest", label: "신상품순" },
    { value: "price-low", label: "낮은 가격순" },
    { value: "price-high", label: "높은 가격순" },
  ];
  const domesticSortByCategory = ref(new Map());
  function sortBooks(books, order) {
    const result = [...books];
    const price = (book) =>
      Number(book.price || 0) * (1 - Number(book.discount || 0) / 100);
    if (order === "sales")
      result.sort((a, b) => (b.salesCount ?? 0) - (a.salesCount ?? 0));
    if (order === "price-low") result.sort((a, b) => price(a) - price(b));
    if (order === "price-high") result.sort((a, b) => price(b) - price(a));
    if (order === "newest")
      result.sort((a, b) =>
        (b.published_date || "").localeCompare(a.published_date || ""),
      );
    return result;
  }
  const formSubcategories = computed(
    () =>
      categoryGroups.find((group) => group.name === bookForm.value.major)
        ?.subcategories || [],
  );
  const homeBooks = computed(() => {
    return sortBooks(
      filterByQuery(allBooks.value).filter(
        (book) =>
          selectedHomeCategory.value === "전체" ||
          majorFor(book) === selectedHomeCategory.value,
      ),
      homeSort.value,
    ).slice(0, 20);
  });
  const newBooks = computed(() => {
    return filterByQuery(allBooks.value)
      .filter((book) => book.published_date || book.featured)
      .slice()
      .sort((a, b) =>
        (b.published_date || "").localeCompare(a.published_date || ""),
      )
      .slice(0, 20);
  });
  const domesticCategories = computed(() =>
    homeCategories.value.filter((category) => category.name !== "전체"),
  );
  const headerCategoryMenu = ref(null);
  const activeDomesticCategory = computed(() => {
    const categories = domesticCategories.value;
    return (
      categories.find((category) => category.name === route.query.category)
        ?.name ??
      categories[0]?.name ??
      ""
    );
  });
  const domesticSort = computed(
    () =>
      domesticSortByCategory.value.get(activeDomesticCategory.value) ?? "sales",
  );
  const domesticBooks = computed(() =>
    sortBooks(
      filterByQuery(allBooks.value).filter(
        (book) => majorFor(book) === activeDomesticCategory.value,
      ),
      domesticSort.value,
    ),
  );
  const categoryBooks = computed(() =>
    sortBooks(
      filterByQuery(allBooks.value).filter((book) => {
        const category = book.major
          ? [book.major, book.subcategory]
          : bookCategories[book.title] || [book.cat, ""];
        return (
          category[0] === selectedMajor.value &&
          (!selectedSub.value || category[1] === selectedSub.value)
        );
      }),
      categorySort.value,
    ),
  );
  const availableSubcategories = computed(() =>
    (selectedGroup.value?.subcategories || []).filter((sub) =>
      allBooks.value.some(
        (book) =>
          book.major === selectedMajor.value && book.subcategory === sub,
      ),
    ),
  );
  const curatedBooks = computed(() => allBooks.value.slice(0, 20));
  const themeShelves = computed(() => {
    const groups = new Map();
    filterByQuery(allBooks.value).forEach((book) => {
      const name = majorFor(book);
      if (!groups.has(name)) groups.set(name, []);
      groups.get(name).push(book);
    });
    return [...groups].slice(0, 3).map(([title, books]) => ({
      title,
      note: `${title} 분야의 책을 만나보세요.`,
      books: books.slice(0, 3),
    }));
  });
  const adminBooks = computed(() =>
    allBooks.value.filter((book) => {
      const query = adminQuery.value.toLowerCase();
      const matchesQuery =
        !query || `${book.title} ${book.author}`.toLowerCase().includes(query);
      const matchesCategory =
        adminCategory.value === "전체" ||
        majorFor(book) === adminCategory.value;
      const matchesStock =
        adminStock.value === "전체 상태" ||
        (adminStock.value === "품절" ? book.stock === 0 : book.stock > 0);
      return matchesQuery && matchesCategory && matchesStock;
    }),
  );

  function filterByQuery(list) {
    const query = searchQuery.value.trim().toLowerCase();
    return list.filter(
      (book) =>
        !query ||
        `${book.title} ${book.author} ${book.cat} ${majorFor(book)}`
          .toLowerCase()
          .includes(query),
    );
  }
  function findBook(title) {
    return allBooks.value.find((book) => book.title === title);
  }
  function majorFor(book) {
    return book.major || bookCategories[book.title]?.[0] || book.cat;
  }
  function detailsFor(book) {
    return (
      bookDetails[book.title] || {
        intro: `${majorFor(book)} 분야의 도서입니다. 책의 핵심 주제와 저자의 시선을 만나보세요.`,
        contents: [
          "책의 주제와 배경",
          "핵심 내용 살펴보기",
          "읽고 생각해 볼 질문",
        ],
        formats: ["종이책"],
      }
    );
  }
  function coverUrl(book) {
    return bookCoverUrl(book);
  }
  function won(value) {
    return `${Number(value || 0).toLocaleString("ko-KR")}원`;
  }
  function showToast(message, wishLink = false) {
    toastWishLink.value = wishLink;
    toastMessage.value = message;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(
      () => {
        toastMessage.value = "";
        toastWishLink.value = false;
      },
      wishLink ? 8000 : 3500,
    );
  }
  function mapDatabaseBook(book, index) {
    const [major, subcategory] = databaseCategoryMap[book.category_name] || [
      book.category_name || "도서",
      "",
    ];
    return {
      id: book.book_id,
      isDatabaseBook: true,
      title: book.title,
      author: (book.authors || []).join(", ") || "저자 미상",
      cat: book.category_name || "도서",
      major,
      subcategory,
      price: Number(book.list_price || book.sale_price || 0),
      discount: Number(book.discount_rate || 0),
      rate:
        Number(book.rating_avg || 0) > 0
          ? Number(book.rating_avg).toFixed(1)
          : "",
      stock: Number(book.stock_qty || 0),
      salesCount: Number(book.sales_count || 0),
      publisher: book.publisher || "출판사 미상",
      cover_image: book.cover_image || "",
      color: ["#527366", "#5b6d9b", "#b7855d", "#638277"][index % 4],
      bg: ["#e4eae4", "#e3e8f3", "#efe7dd", "#e2e9e5"][index % 4],
      featured: book.published_date
        ? Date.now() - Date.parse(book.published_date) <
          365 * 24 * 60 * 60 * 1000
        : false,
      published_date: book.published_date || null,
      isbn13: book.isbn13,
    };
  }
  async function loadDatabaseBooks() {
    try {
      const result = await storefrontApi.listBooks();
      databaseBooks.value = (result.items || []).map(mapDatabaseBook);
      catalogError.value = "";
      if (!databaseBooks.value.length)
        showToast("DB에 표시할 도서가 없습니다.");
      if (activeBanner.value >= banners.value.length) activeBanner.value = 0;
    } catch (error) {
      catalogError.value =
        "도서 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.";
      showToast(catalogError.value);
    } finally {
      catalogLoading.value = false;
    }
  }
  watch([rememberAdminId, adminUserId], ([remember, id]) => {
    if (remember && id) localStorage.setItem("book-saved-id", id);
    else if (!remember) localStorage.removeItem("book-saved-id");
  });
  function navigate(nextView) {
    closeHeaderCategoryMenu();
    if (
      nextView === route.name &&
      !route.hash &&
      !Object.keys(route.query).length
    ) {
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    return router.push({ name: nextView });
  }
  function closeHeaderCategoryMenu(restoreFocus = false) {
    const menu = headerCategoryMenu.value;
    if (!menu?.open) return;
    menu.open = false;
    if (restoreFocus) menu.querySelector("summary")?.focus();
  }
  function closeHeaderCategoryMenuOnBlur(event) {
    if (
      event.relatedTarget &&
      !event.currentTarget.contains(event.relatedTarget)
    )
      closeHeaderCategoryMenu();
  }
  function closeHeaderCategoryMenuOnOutsideClick(event) {
    if (!headerCategoryMenu.value?.contains(event.target))
      closeHeaderCategoryMenu();
  }
  function selectHeaderCategory(name) {
    closeHeaderCategoryMenu(true);
    const target = view.value === "bestsellers" ? "bestsellers" : "domestic";
    if (view.value === target && route.query.category === name) {
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
    return router.push({ name: target, query: { category: name } });
  }
  function openBestSellers() {
    navigate("bestsellers");
  }
  async function showBookSearchResults() {
    if (!searchQuery.value.trim()) return;
    selectedHomeCategory.value = "전체";
    if (view.value !== "home")
      await router.push({ name: "home", hash: "#home-books-title" });
    await nextTick();
    const heading = document.getElementById("home-books-title");
    heading?.focus({ preventScroll: true });
    heading?.scrollIntoView({ block: "start" });
  }
  watch(
    [view, () => route.params.name],
    ([page, name]) => {
      selectedMajor.value = page === "category" ? name : "";
      selectedSub.value = "";
    },
    { immediate: true },
  );

  watch(
    [view, () => route.params.title, allBooks],
    ([page, title]) => {
      const book = page === "productInfo" ? findBook(title) : null;
      const current = productBook.value;
      if (
        book &&
        current?.id === book.id &&
        current.title === book.title &&
        current.isDatabaseBook === book.isDatabaseBook
      )
        return;
      productBook.value = book;
    },
    { immediate: true },
  );

  let deliveryLoadGeneration = 0;
  watch(
    view,
    (page) => {
      const deliveryLoad = ++deliveryLoadGeneration;
      closeHeaderCategoryMenu();

      if (page === "checkout") {
        delivery.value = {
          name: "",
          phone: "",
          postalCode: "",
          address: "",
          addressDetail: "",
        };
        loadSavedDelivery(deliveryLoad);
        prepareCheckout();
      }
    },
    { immediate: true },
  );

  async function loadSavedDelivery(generation) {
    if (!auth.initialized) await auth.fetchMe();
    if (
      generation !== deliveryLoadGeneration ||
      view.value !== "checkout" ||
      !auth.isAuthenticated
    )
      return;
    try {
      const { data } = await http.get("/api/v1/members/me/addresses");
      if (
        generation !== deliveryLoadGeneration ||
        view.value !== "checkout" ||
        !auth.isAuthenticated
      )
        return;
      // Do not overwrite information entered while the saved address was loading.
      if (
        Object.values(delivery.value).some((value) =>
          String(value || "").trim(),
        )
      )
        return;
      const address = data.find((item) => item.is_default) || data[0];
      if (address)
        delivery.value = {
          name: address.receiver || "",
          phone: address.phone || "",
          postalCode: address.zipcode || "",
          address: address.address1 || "",
          addressDetail: address.address2 || "",
        };
    } catch (error) {
      if (generation === deliveryLoadGeneration && view.value === "checkout")
        showToast(
          "저장된 배송지를 불러오지 못했습니다. 배송 정보를 직접 입력해 주세요.",
        );
    }
  }
  function openProduct(book) {
    const product = typeof book === "string" ? findBook(book) : book;
    if (!product) return;
    if (view.value !== "productInfo") productSourcePath.value = route.fullPath;
    return router.push({
      name: "productInfo",
      params: { title: product.title },
    });
  }
  function backToBooks() {
    if (route.query.from === "mypage")
      return router.push({ name: "mypage", hash: "#member-recommendations" });
    return router.push(productSourcePath.value);
  }
  function openBookInfo(book) {
    openProduct(book);
  }
  async function toggleWish(book) {
    if (!canWish.value) return;
    if (!wishesReady) {
      showToast("찜 목록을 확인 중이거나 불러오지 못했어요.");
      return;
    }
    const id = String(book.id);
    if (wishPending.has(id)) return;
    const generation = wishGeneration;
    const next = new Set(wishlist.value);
    if (auth.isAuthenticated) {
      if (!book.isDatabaseBook) {
        showToast("이 도서는 찜할 수 없어요.");
        return;
      }
      wishPending.add(id);
      try {
        const result = await storefrontApi.toggleWishlist(id);
        if (generation !== wishGeneration) return;
        const updated = new Set(wishlist.value);
        if (result.wished) updated.add(id);
        else updated.delete(id);
        wishlist.value = updated;
        showToast(
          result.wished ? "찜 목록에 담았어요" : "찜 목록에서 삭제했어요",
          true,
        );
      } catch {
        if (generation === wishGeneration)
          showToast("찜 상태를 저장하지 못했어요.");
      } finally {
        wishPending.delete(id);
      }
      return;
    }
    if (next.has(id)) next.delete(id);
    else next.add(id);
    wishlist.value = next;
    localStorage.setItem(guestWishKey, JSON.stringify([...next]));
    showToast(
      next.has(id) ? "찜 목록에 담았어요" : "찜 목록에서 삭제했어요",
      true,
    );
  }
  function addCart(book) {
    const title = typeof book === "string" ? book : book.title;
    const index = cart.value.findIndex(
      (item) => (typeof item === "string" ? item : item.title) === title,
    );
    if (index >= 0) {
      openCartDialog(title, true);
      return;
    }
    cart.value = [...cart.value, { title, quantity: 1 }];
    selectedCart.value = new Set(cart.value.map((_, itemIndex) => itemIndex));
    persistCart();
    openCartDialog(title);
  }
  function openCartDialog(title, duplicate = false) {
    cartDialogTrigger = document.activeElement;
    cartAlreadyAdded.value = duplicate;
    addedCartTitle.value = title;
    nextTick(() => cartDialog.value?.querySelector("button")?.focus());
  }
  function closeCartDialog(goToCart = false) {
    addedCartTitle.value = "";
    cartAlreadyAdded.value = false;
    if (goToCart) {
      navigate("cart");
    } else nextTick(() => cartDialogTrigger?.focus());
  }
  function trapCartDialogFocus(event) {
    const buttons = [...(cartDialog.value?.querySelectorAll("button") || [])];
    if (!buttons.length) return;
    if (event.shiftKey && document.activeElement === buttons[0]) {
      event.preventDefault();
      buttons[buttons.length - 1].focus();
    } else if (
      !event.shiftKey &&
      document.activeElement === buttons[buttons.length - 1]
    ) {
      event.preventDefault();
      buttons[0].focus();
    }
  }
  function requestCartDelete(indices, mode = "selected") {
    if (!indices.length) {
      showToast("삭제할 상품을 선택해 주세요.");
      return;
    }
    cartDialogTrigger = document.activeElement;
    cartDeleteMode.value = mode;
    cartDeleteTargets.value = indices;
    nextTick(() => cartDialog.value?.querySelector("button")?.focus());
  }
  function closeCartDelete() {
    cartDeleteTargets.value = null;
    nextTick(() => cartDialogTrigger?.focus());
  }
  function confirmCartDelete() {
    const targets = new Set(cartDeleteTargets.value || []);
    const remainingSelection = new Set();
    const remaining = [];
    cart.value.forEach((item, index) => {
      if (targets.has(index)) return;
      if (selectedCart.value.has(index))
        remainingSelection.add(remaining.length);
      remaining.push(item);
    });
    cart.value = remaining;
    selectedCart.value = remainingSelection;
    persistCart();
    cartDeleteTargets.value = null;
    cartDeleteComplete.value = true;
    nextTick(() => cartDialog.value?.querySelector("button")?.focus());
  }
  function closeCartDeleteComplete() {
    cartDeleteComplete.value = false;
    nextTick(() => cartDialogTrigger?.isConnected && cartDialogTrigger.focus());
  }
  function removeCart(index) {
    requestCartDelete([index], "single");
  }
  function toggleCartItem(index) {
    const next = new Set(selectedCart.value);
    next.has(index) ? next.delete(index) : next.add(index);
    selectedCart.value = next;
  }
  function removeAllCart() {
    requestCartDelete(
      cart.value.map((_, index) => index),
      "all",
    );
  }
  function updateCartQuantity(index, quantity) {
    cart.value = cart.value.map((item, itemIndex) =>
      itemIndex === index
        ? {
            title: typeof item === "string" ? item : item.title,
            quantity: Math.max(1, Number(quantity)),
          }
        : item,
    );
    persistCart();
  }
  function effectivePrice(book) {
    return Number(productByTitle.value.get(book.title)?.price ?? book.price);
  }
  function tossCustomerKey() {
    let key = localStorage.getItem("toss-customer-key");
    if (!key) {
      const bytes = new Uint8Array(16);
      window.crypto.getRandomValues(bytes);
      key = `bk_${Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("")}`;
      localStorage.setItem("toss-customer-key", key);
    }
    return key;
  }
  async function prepareCheckout() {
    if (checkoutLoading.value || !selectedCartBooks.value.length) return;
    checkoutLoading.value = true;
    checkoutReady.value = false;
    checkoutMessage.value = "";
    checkoutCoupons.value = [];
    selectedCouponId.value = "";
    couponError.value = "";
    try {
      const result = await storefrontApi.listProducts();
      backendProducts.value = result.items || [];
      const missing = selectedCartBooks.value.filter(
        (book) => !productByTitle.value.has(book.title),
      );
      if (missing.length) {
        checkoutMessage.value = `판매 상품 정보가 없는 책이 있어요: ${missing.map((book) => book.title).join(", ")}`;
        return;
      }
      if (!auth.initialized) await auth.fetchMe();
      if (auth.isAuthenticated) {
        couponLoading.value = true;
        try {
          checkoutCoupons.value = (
            await http.get("/api/v1/members/me/coupons/available", {
              params: { amount: checkoutTotal.value },
            })
          ).data;
        } catch (error) {
          couponError.value =
            error.userMessage || "쿠폰을 불러오지 못했습니다.";
        } finally {
          couponLoading.value = false;
        }
      }
      // 백엔드 결제 설정(mock/toss)을 확인한 뒤 결제 버튼을 활성화한다.
      // 결제 설정을 못 불러와도 결제 버튼은 막지 않는다(기본값: 토스 테스트 결제).
      let mode = null;
      try {
        mode = await storefrontApi.getPaymentMode();
      } catch {
        mode = null;
      }
      checkoutPaymentMode.value = mode?.mode === "mock" ? "mock" : "toss";
      checkoutMessage.value = "";
      checkoutReady.value = true;
    } catch (error) {
      checkoutMessage.value =
        error.message ||
        "주문 정보를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.";
    } finally {
      checkoutLoading.value = false;
    }
  }
  function openPayment() {
    if (!selectedCartBooks.value.length) return;
    navigate("checkout");
  }
  // 결제가 끝난 주문을 완료 화면에 보여주고, 산 책을 장바구니에서 뺀다.
  function completeOrder(pending, statusLabel) {
    lastOrder.value = {
      id: pending.orderNo,
      books: pending.books,
      total: pending.total,
      profile: pending.profile,
      status: statusLabel,
    };
    orderHistory.value = [lastOrder.value, ...orderHistory.value];
    localStorage.setItem(
      "bookjjeok-orders",
      JSON.stringify(orderHistory.value),
    );
    const purchased = new Set(pending.books.map((book) => book.title));
    cart.value = cart.value.filter(
      (item) => !purchased.has(typeof item === "string" ? item : item.title),
    );
    selectedCart.value = new Set(cart.value.map((_, index) => index));
    persistCart();
    sessionStorage.removeItem("bookjjeok-pending-order");
    if (view.value !== "orderComplete") navigate("orderComplete");
  }
  // 토스 결제창에서 돌아왔을 때(successUrl / failUrl) 처리한다.
  let tossHandled = "";
  async function finishTossPayment() {
    const q = route.query;
    const key = `${q.toss}|${q.paymentKey || q.code || ""}`;
    if (!q.toss || tossHandled === key) return;
    tossHandled = key;
    let pending = null;
    try {
      pending = JSON.parse(
        sessionStorage.getItem("bookjjeok-pending-order") || "null",
      );
    } catch {
      pending = null;
    }
    const cleanQuery = () => router.replace({ query: {} });
    if (q.toss === "fail") {
      sessionStorage.removeItem("bookjjeok-pending-order");
      showToast(
        q.message
          ? `결제가 취소되었어요: ${q.message}`
          : "결제가 취소되었어요.",
      );
      cleanQuery();
      return;
    }
    if (!pending || !q.paymentKey) {
      showToast("결제 정보를 확인할 수 없어요. 주문 내역을 확인해 주세요.");
      cleanQuery();
      return;
    }
    try {
      await storefrontApi.payOrder(
        pending.orderDbId,
        {
          payment_key: String(q.paymentKey),
          order_no: String(q.orderId),
          amount: Number(q.amount),
        },
        pending.guestToken,
      );
      completeOrder(pending, "결제 완료");
    } catch (error) {
      showToast(
        error.message || "결제 승인에 실패했어요. 고객센터로 문의해 주세요.",
      );
    } finally {
      cleanQuery();
    }
  }
  watch(
    () => route.query.toss,
    (value) => {
      if (value) finishTossPayment();
    },
    { immediate: true },
  );
  async function submitTossPayment() {
    if (!checkoutReady.value || checkoutSubmitting.value) return;
    if (
      !delivery.value.name.trim() ||
      !delivery.value.phone.trim() ||
      !delivery.value.address.trim()
    ) {
      showToast("받는 분, 연락처와 주소를 입력해 주세요.");
      return;
    }
    if (!/^\d{5}$/.test(delivery.value.postalCode.trim())) {
      showToast("우편번호 5자리를 입력해 주세요.");
      return;
    }
    if (
      !auth.isAuthenticated &&
      !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(ordererEmail.value.trim())
    ) {
      showToast("비회원 주문 조회에 사용할 이메일을 입력해 주세요.");
      return;
    }
    checkoutSubmitting.value = true;
    try {
      const member = auth.isAuthenticated ? auth.user : null;
      const order = await storefrontApi.createOrder({
        items: selectedCartBooks.value.map((book) => ({
          book_id: Number(productByTitle.value.get(book.title).id),
          quantity: book.quantity,
        })),
        orderer_name: (member?.name || delivery.value.name).trim(),
        orderer_phone: (member?.phone || delivery.value.phone).trim(),
        orderer_email: member ? member.email : ordererEmail.value.trim(),
        receiver: delivery.value.name.trim(),
        receiver_phone: delivery.value.phone.trim(),
        zipcode: delivery.value.postalCode.trim(),
        address1: delivery.value.address.trim(),
        address2: (delivery.value.addressDetail || "").trim() || null,
        member_coupon_id:
          member && selectedCouponId.value
            ? Number(selectedCouponId.value)
            : null,
        payment_method:
          paymentMethod.value === "TRANSFER" ? "TRANSFER" : "CARD",
      });
      const guestToken = order.guest_order_token || null;
      const pendingOrder = {
        orderDbId: order.order_id,
        orderNo: order.order_no,
        guestToken,
        books: selectedCartBooks.value.map((book) => ({
          ...book,
          price: effectivePrice(book),
        })),
        total: Number(order.total_amount),
        profile: { ...delivery.value },
      };

      if (checkoutPaymentMode.value === "mock") {
        // 테스트(mock) 모드: 백엔드 가상 결제로 바로 승인한다.
        await storefrontApi.payOrder(order.order_id, {}, guestToken);
        completeOrder(pendingOrder, "결제 완료");
        return;
      }

      // 토스 결제창: 인증 후 successUrl로 돌아오면 finishTossPayment()가 승인 API를 호출한다.
      await loadTossPayments();
      const ready = await storefrontApi.getPaymentReady(
        order.order_id,
        guestToken,
      );
      pendingOrder.total = ready.amount;
      sessionStorage.setItem(
        "bookjjeok-pending-order",
        JSON.stringify(pendingOrder),
      );
      const payment = window
        .TossPayments(ready.client_key)
        .payment({ customerKey: tossCustomerKey() });
      await payment.requestPayment({
        method: paymentMethod.value === "TRANSFER" ? "TRANSFER" : "CARD",
        amount: { value: ready.amount, currency: "KRW" },
        orderId: ready.order_id,
        orderName: ready.order_name,
        customerName: ready.customer_name,
        successUrl: `${window.location.origin}/order-complete?toss=success`,
        failUrl: `${window.location.origin}/checkout?toss=fail`,
      });
    } catch (error) {
      sessionStorage.removeItem("bookjjeok-pending-order");
      showToast(error.message || "결제 요청을 시작하지 못했어요.");
    } finally {
      checkoutSubmitting.value = false;
    }
  }
  function startProfileEdit() {
    profileDraft.value = { ...myProfile.value };
    isEditingProfile.value = true;
  }
  function cancelProfileEdit() {
    profileDraft.value = { ...myProfile.value };
    isEditingProfile.value = false;
  }
  function saveMyProfile() {
    if (
      !profileDraft.value.name.trim() ||
      !profileDraft.value.phone.trim() ||
      !profileDraft.value.address.trim()
    ) {
      showToast("받는 분, 연락처, 주소를 입력해 주세요.");
      return;
    }
    if (!/^\d{5}$/.test(profileDraft.value.postalCode.trim())) {
      showToast("우편번호 5자리를 입력해 주세요.");
      return;
    }
    myProfile.value = { ...profileDraft.value };
    localStorage.setItem("bookjjeok-profile", JSON.stringify(myProfile.value));
    isEditingProfile.value = false;
    showToast("내 정보를 저장했어요");
  }
  function removeOrder(orderId) {
    orderHistory.value = orderHistory.value.filter(
      (order) => order.id !== orderId,
    );
    localStorage.setItem(
      "bookjjeok-orders",
      JSON.stringify(orderHistory.value),
    );
    showToast("주문 내역을 삭제했어요");
  }
  function likedBooks() {
    return allBooks.value.filter((book) => wishlist.value.has(String(book.id)));
  }
  function moveBanner(step) {
    if (!banners.value.length) return;
    activeBanner.value =
      (activeBanner.value + step + banners.value.length) % banners.value.length;
  }
  function openBookForm() {
    editingBookId.value = null;
    bookForm.value = {
      title: "",
      author: "",
      major: categoryGroups[0].name,
      subcategory: categoryGroups[0].subcategories[0],
      price: 0,
      stock: 10,
      publisher: "",
    };
    showBookForm.value = true;
  }
  function openEditBookForm(book) {
    editingBookId.value = book.id;
    bookForm.value = {
      title: book.title,
      author: book.author,
      major: majorFor(book),
      subcategory:
        book.subcategory ||
        categoryGroups.find((group) => group.name === majorFor(book))
          ?.subcategories[0] ||
        "",
      price: book.price,
      stock: book.stock,
      publisher: book.publisher,
    };
    showBookForm.value = true;
  }
  function createBook() {
    if (editingBookId.value !== null) {
      const book = {
        ...allBooks.value.find((item) => item.id === editingBookId.value),
        ...bookForm.value,
        cat: bookForm.value.major,
        major: bookForm.value.major,
      };
      if (adminExtra.value.some((item) => item.id === editingBookId.value)) {
        adminExtra.value = adminExtra.value.map((item) =>
          item.id === editingBookId.value ? book : item,
        );
        localStorage.setItem(
          "bookjjeok-admin-books",
          JSON.stringify(adminExtra.value),
        );
      } else {
        adminOverrides.value = {
          ...adminOverrides.value,
          [String(editingBookId.value)]: book,
        };
        localStorage.setItem(
          "bookjjeok-book-overrides",
          JSON.stringify(adminOverrides.value),
        );
      }
      showToast("도서 정보를 수정했어요");
    } else {
      const book = {
        ...bookForm.value,
        id: Date.now(),
        cat: bookForm.value.major,
        major: bookForm.value.major,
        discount: 0,
        rate: "-",
        color: "#527366",
        bg: "#e4eae4",
      };
      adminExtra.value = [book, ...adminExtra.value];
      localStorage.setItem(
        "bookjjeok-admin-books",
        JSON.stringify(adminExtra.value),
      );
      showToast("도서를 등록했어요");
    }
    showBookForm.value = false;
    editingBookId.value = null;
  }
  function removeBook(book) {
    adminExtra.value = adminExtra.value.filter((item) => item.id !== book.id);
    adminDeletedIds.value = [...new Set([...adminDeletedIds.value, book.id])];
    localStorage.setItem(
      "bookjjeok-deleted-books",
      JSON.stringify(adminDeletedIds.value),
    );
    localStorage.setItem(
      "bookjjeok-admin-books",
      JSON.stringify(adminExtra.value),
    );
    showToast("도서를 삭제했어요");
  }

  onMounted(() => {
    loadDatabaseBooks();
    // 관리자에서 수정하거나 DB 시드가 끝난 뒤 서버를 재시작하지 않아도 목록을 갱신한다.
    window.addEventListener("focus", refreshBooks);
    document.addEventListener("visibilitychange", refreshBooks);
    refreshTimer = window.setInterval(refreshBooks, 30000);
    document.addEventListener(
      "pointerdown",
      closeHeaderCategoryMenuOnOutsideClick,
    );
  });
  onUnmounted(() => {
    clearTimeout(toastTimer);
    window.removeEventListener("focus", refreshBooks);
    document.removeEventListener("visibilitychange", refreshBooks);
    window.clearInterval(refreshTimer);
    document.removeEventListener(
      "pointerdown",
      closeHeaderCategoryMenuOnOutsideClick,
    );
  });

  return {
    view,
    searchQuery,
    showBookSearchResults,
    categoryGroups,
    selectedMajor,
    selectedSub,
    selectedGroup,
    availableSubcategories,
    homeCategories,
    selectedHomeCategory,
    homeSort,
    domesticSortOptions,
    domesticSortByCategory,
    categorySort,
    headerCategoryMenu,
    closeHeaderCategoryMenu,
    closeHeaderCategoryMenuOnBlur,
    selectHeaderCategory,
    postalOpen,
    postalKeyword,
    postalResults,
    postalPage,
    postalLoading,
    postalMessage,
    searchPostal,
    selectPostal,
    activeBanner,
    banners,
    wishlist,
    canWish,
    cart,
    cartBooks,
    selectedCart,
    selectedCartBooks,
    cartSubtotal,
    cartDiscount,
    cartTotal,
    checkoutTotal,
    checkoutReady,
    checkoutMessage,
    checkoutLoading,
    ordererEmail,
    checkoutSubmitting,
    checkoutCoupons,
    selectedCouponId,
    selectedCoupon,
    couponDiscount,
    couponLoading,
    couponError,
    checkoutAuthenticated: computed(() => auth.isAuthenticated),
    delivery,
    paymentMethod,
    checkoutPaymentMode,
    effectivePrice,
    allBooks,
    homeBooks,
    newBooks,
    themeShelves,
    domesticCategories,
    activeDomesticCategory,
    domesticSort,
    domesticBooks,
    categoryBooks,
    curatedBooks,
    bestSellerBooks,
    lastOrder,
    orderHistory,
    myProfile,
    profileDraft,
    isEditingProfile,
    catalogLoading,
    catalogError,
    curationNotes,
    productBook,
    productPanel,
    productDetail,
    productDetailStatus,
    publishedContents,
    productIntroduction,
    productReviews,
    reviewStats,
    ratingCount,
    reviewCount,
    reviewSort,
    reviewRating,
    reviewPage,
    reviewsStatus,
    reviewDraft,
    reviewMessage,
    reviewSubmitting,
    loadProductReviews,
    submitProductReview,
    toastMessage,
    addedCartTitle,
    cartAlreadyAdded,
    cartDialog,
    closeCartDialog,
    trapCartDialogFocus,
    cartDeleteTargets,
    cartDeleteMode,
    cartDeleteComplete,
    closeCartDelete,
    confirmCartDelete,
    closeCartDeleteComplete,
    showBookForm,
    editingBookId,
    bookForm,
    formSubcategories,
    adminQuery,
    adminCategory,
    adminStock,
    adminBooks,
    adminUserId,
    adminPassword,
    rememberAdminId,
    showAdminPassword,
    adminLoginError,
    signupConsent,
    signupError,
    signupForm,
    adminTodayLabel,
    adminMetrics,
    adminProfile,
    workload,
    workloadMix,
    adminDonutStyle,
    findBook,
    majorFor,
    detailsFor,
    coverUrl,
    won,
    navigate,
    openBestSellers,
    openProduct,
    backToBooks,
    openBookInfo,
    toastWishLink,
    toggleWish,
    addCart,
    removeCart,
    openPayment,
    toggleCartItem,
    removeAllCart,
    updateCartQuantity,
    submitTossPayment,
    startProfileEdit,
    cancelProfileEdit,
    saveMyProfile,
    removeOrder,
    likedBooks,
    moveBanner,
    showToast,
    openBookForm,
    openEditBookForm,
    createBook,
    removeBook
  };
}
