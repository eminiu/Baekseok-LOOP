import logging
logging.getLogger("google_genai").setLevel(logging.ERROR)
from google import genai
import PIL.Image
import os
import re
import streamlit as st
#=====================================================================================================================================

#=====================================================================================================================================
st.set_page_config(
    page_title = 'LOOP',
    page_icon = 'loop_logo.png',
    layout = 'centered'
    )

st.logo('loop_logo.png', size='large')

defaults = {
    'e_list': [], 'k_list': [],        # 추출한 단어
    'quz': [], 'sol': [],              # 이번 회차 문제와 정답
    'idx': 0,                          # 지금 몇 번째 문제인지 (기존 for문의 i)
    'nq': [], 'ns': [],                # 이번 회차에 틀린 문제
    'turn_cnt': 1, 'correct': 0, 'total': 0,
    'record': None,                    # 오답을 어디에 기록할지 (오답 테스트면 None)
    'e_wrong_list': [], 'k_wrong_list': [],   # 오답노트
    'message': None, 'accuracy': None,
    'status': 'idle',                  # idle: 대기 / testing: 진행 중 / done: 끝
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

st.title('LOOP : 누구보다 빠른 나만의 단어장')

voca = st.file_uploader(
    label = '**사진을 업로드 해주세요.**',
    type = ['png','jpg'],
    accept_multiple_files= True,
    help = '사진을 여러 장 업로드 할 수 있습니다.'
)

choice = st.selectbox(
    '**응시할 테스트를 선택해주세요.**',
    ('뜻 테스트', '스펠링 테스트', '뜻 오답 테스트', '스펠링 오답 테스트'),
    index = 0
)

start = st.button('테스트 생성')
#===================================================================================================================================

#===================================================================================================================================
# Render: 환경 변수에서 키 읽기 / 내 컴퓨터, Streamlit Cloud: secrets에서 읽기
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    api_key = st.secrets["GEMINI_API_KEY"]

client = genai.Client(api_key=api_key)

@st.cache_data(show_spinner=False)
def extract_text_from_image(image_path: str):
    image = PIL.Image.open(image_path)

    prompt = """
사진은 영어 단어 학습 자료다. 아래 규칙에 따라 메인 단어와 뜻만 추출해라.

구분 기준:
1. 각 줄(행)의 가장 왼쪽에 있는 굵거나 큰 영어 단어 = 추출 대상 단어
2. 그 단어 바로 옆(같은 줄)에 있는 첫 번째 한국어 뜻 = 추출 대상 뜻
3. 다음은 절대 추출하지 마라:
   - 유의어(=, syn, 비슷한말 등으로 표시된 것)
   - 반의어(≠, ant, 반대말 등으로 표시된 것)
   - 예문(문장 형태로 되어 있거나 괄호 안에 있는 보조 설명)
   - 품사 표시(v., n., adj. 등)나 발음기호

4. 한 줄에 뜻이 여러 개 쉼표로 나열되어 있으면 가장 먼저 나오는 것 하나만 선택해라.
5. e_list와 k_list의 길이는 반드시 같아야 한다. 같은 줄 수만큼 항목을 만들어라.
6. 설명, 문장, 마크다운, 주석 없이 아래 형식의 코드만 출력해라.

출력 형식:
e_list = ["word1", "word2", ...]
k_list = ["뜻1", "뜻2", ...]
"""
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=[prompt, image]
    )

    text = response.text.strip()
    text = re.sub(r"```python|```", "", text).strip()  # 코드블록 표시 제거

    local_vars = {}
    exec(text, {}, local_vars)
    return local_vars["e_list"], local_vars["k_list"]
#===================================================================================================================================

#===================================================================================================================================
def start_test(quz,sol,record):

    if not quz:
        st.error('단어를 찾지 못했습니다. 다른 사진으로 시도해주세요.')
        return
    
    s = st.session_state
    s.quz, s.sol = quz, sol
    s.idx = 0
    s.nq, s.ns = [], []
    s.turn_cnt, s.correct, s.total = 1, 0, len(quz)
    s.record = record
    s.message, s.accuracy = None, None
    s.status = 'testing'

def check_answer(answer):
    s = st.session_state
    q, a = s.quz[s.idx], s.sol[s.idx]

    if answer.strip() == a.strip():
        s.message = ('success', '성공! 정답입니다.')
        if s.turn_cnt == 1:
            s.correct += 1
    else:
        s.message = ('error', f'오답입니다. 정답 : {a}')
        s.nq.append(q)
        s.ns.append(a)
        if s.turn_cnt == 1 and s.record:
            q_list, s_list = s.record
            if q not in s[q_list]:
                s[q_list].append(q)
                s[s_list].append(a)

    s.idx += 1

    if s.idx == len(s.quz):
        if s.turn_cnt == 1:
            s.accuracy = f'정답률 : {s.correct / s.total * 100:.1f}%'
        s.turn_cnt += 1
        s.quz, s.sol = s.nq, s.ns
        s.nq, s.ns = [], []
        s.idx = 0
        if not s.quz:                          
            s.status = 'done'
#===================================================================================================================================

#===================================================================================================================================
if start:
    s = st.session_state

    if choice in ('뜻 테스트', '스펠링 테스트'):
        if not voca:
            st.warning('파일을 먼저 업로드 해주세요.')
        else:
            original_e = []
            original_k = []
            with st.spinner('단어를 추출하는 중...'):
                for i in voca:
                    i.seek(0)
                    e_temp, k_temp = extract_text_from_image(i)
                    original_e.extend(e_temp)
                    original_k.extend(k_temp)

            s.e_list, s.k_list =original_e, original_k
            if choice == '뜻 테스트':
                start_test(s.e_list, s.k_list, ('e_wrong_list', 'k_wrong_list'))
            else:
                start_test(s.k_list, s.e_list, ('k_wrong_list', 'e_wrong_list'))

    elif choice == '뜻 오답 테스트':
        if not s.e_wrong_list:
            st.info('현재는 오답이 비어 있습니다.')
        else:
            start_test(s.e_wrong_list, s.k_wrong_list, None)

    elif choice == '스펠링 오답 테스트':
        if not s.k_wrong_list:
            st.info('현재는 오답이 비어 있습니다.')
        else:
            start_test(s.k_wrong_list, s.e_wrong_list, None)
#===================================================================================================================================

#===================================================================================================================================
s = st.session_state

if s.status == 'testing':
    st.divider()
    if s.message:
        kind, text = s.message
        if kind == 'success':
            st.success(text)
        else:
            st.error(text)
    if s.turn_cnt >= 2 and s.idx == 0:
        st.info(f'{s.accuracy} · 이제부터 오답을 시작합니다.')

    st.caption(f'{s.turn_cnt}회차 · {s.idx+1}/{len(s.quz)}')
    st.markdown(f'## {s.quz[s.idx]}')

    # 화면 맨 아래에 고정되는 입력창 (문제가 바뀌어도 같은 입력창이 유지됨, 엔터로 제출)
    answer = st.chat_input('답을 입력하고 엔터')
    if answer:
        check_answer(answer)
        st.rerun()

    if st.button('그만하기'):
        s.status = 'idle'
        st.rerun()

elif s.status == 'done':
    st.divider()
    if s.message:
        kind, text = s.message
        getattr(st, kind)(text)
    st.info(s.accuracy)
    st.success('성공! 수고하셨습니다.')
#===================================================================================================================================
