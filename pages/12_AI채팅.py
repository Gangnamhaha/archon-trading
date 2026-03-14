import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import streamlit.components.v1 as components
from config.styles import inject_pro_css
from config.auth import require_auth

st.set_page_config(page_title="AI Chat", page_icon="💬", layout="wide")
require_auth()
inject_pro_css()
st.title("💬 AI 채팅")


def tts_speak(text: str, lang: str = "ko-KR"):
    safe = text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$").replace('"', '\\"').replace("\n", " ")
    components.html(f"""
    <script>
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance("{safe}");
    u.lang = "{lang}";
    u.rate = 1.0;
    window.speechSynthesis.speak(u);
    </script>
    """, height=0)


if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = []
if "openai_api_key" not in st.session_state:
    st.session_state["openai_api_key"] = ""
if "tts_enabled" not in st.session_state:
    st.session_state["tts_enabled"] = False
if "stt_text" not in st.session_state:
    st.session_state["stt_text"] = ""

with st.sidebar:
    st.subheader("API 설정")
    api_key = st.text_input("OpenAI API Key", type="password", value=st.session_state["openai_api_key"], key="api_key_input")
    if api_key:
        st.session_state["openai_api_key"] = api_key

    st.markdown("---")
    model = st.selectbox("모델", ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"], key="chat_model")
    temperature = st.slider("Temperature", 0.0, 2.0, 0.7, 0.1, key="chat_temp")
    system_prompt = st.text_area(
        "시스템 프롬프트",
        value="당신은 주식 투자와 금융 분야에 전문적인 AI 어시스턴트입니다. 한국어로 답변하세요.",
        height=100,
        key="chat_system",
    )

    st.markdown("---")
    st.subheader("음성 설정")
    st.session_state["tts_enabled"] = st.toggle("🔊 AI 응답 자동 읽기 (TTS)", value=st.session_state["tts_enabled"], key="tts_toggle")

    st.markdown("---")
    if st.button("대화 초기화", use_container_width=True, key="chat_clear"):
        st.session_state["chat_messages"] = []
        st.rerun()

if not st.session_state["openai_api_key"]:
    st.info("좌측 사이드바에서 OpenAI API Key를 입력하세요.")
    st.markdown("""
    ### API Key 발급 방법
    1. [OpenAI 플랫폼](https://platform.openai.com) 접속
    2. 로그인 → API Keys → Create new secret key
    3. 생성된 키를 좌측에 입력

    > 💡 API Key는 세션 동안만 유지되며 서버에 저장되지 않습니다.
    """)
    st.stop()

for idx, msg in enumerate(st.session_state["chat_messages"]):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            if st.button("🔊", key=f"tts_{idx}", help="이 응답을 음성으로 읽기"):
                tts_speak(msg["content"])

stt_col1, stt_col2 = st.columns([1, 8])
with stt_col1:
    try:
        from streamlit_mic_recorder import speech_to_text
        stt_result = speech_to_text(
            language="ko",
            start_prompt="🎤",
            stop_prompt="⏹️",
            just_once=True,
            use_container_width=True,
            key="stt_main",
        )
        if stt_result:
            st.session_state["stt_text"] = stt_result
    except ImportError:
        if st.button("🎤", help="streamlit-mic-recorder 패키지 필요", key="stt_fallback"):
            st.toast("음성입력에는 streamlit-mic-recorder 패키지가 필요합니다.")

with stt_col2:
    if st.session_state["stt_text"]:
        st.info(f"🎤 인식된 텍스트: **{st.session_state['stt_text']}**")

prompt_value = st.session_state.get("stt_text", "")
if prompt := st.chat_input("메시지를 입력하세요 (🎤 음성입력도 가능)", key="chat_input_main"):
    prompt_value = prompt

if st.session_state["stt_text"] and not prompt:
    prompt_value = st.session_state["stt_text"]
    st.session_state["stt_text"] = ""

    st.session_state["chat_messages"].append({"role": "user", "content": prompt_value})
    with st.chat_message("user"):
        st.markdown(prompt_value)

    with st.chat_message("assistant"):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=st.session_state["openai_api_key"])
            messages = [{"role": "system", "content": system_prompt}]
            for m in st.session_state["chat_messages"]:
                messages.append({"role": m["role"], "content": m["content"]})
            with st.spinner("AI 응답 생성 중..."):
                response = client.chat.completions.create(
                    model=model, messages=messages,
                    temperature=temperature, max_tokens=4096,
                )
                reply = response.choices[0].message.content
            st.markdown(reply)
            st.session_state["chat_messages"].append({"role": "assistant", "content": reply})
            if st.session_state["tts_enabled"]:
                tts_speak(reply)
        except Exception as e:
            st.error(f"오류: {e}")
    st.rerun()

elif prompt:
    st.session_state["chat_messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=st.session_state["openai_api_key"])
            messages = [{"role": "system", "content": system_prompt}]
            for m in st.session_state["chat_messages"]:
                messages.append({"role": m["role"], "content": m["content"]})
            with st.spinner("AI 응답 생성 중..."):
                response = client.chat.completions.create(
                    model=model, messages=messages,
                    temperature=temperature, max_tokens=4096,
                )
                reply = response.choices[0].message.content
            st.markdown(reply)
            st.session_state["chat_messages"].append({"role": "assistant", "content": reply})
            if st.session_state["tts_enabled"]:
                tts_speak(reply)
        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower() or "auth" in error_msg.lower():
                st.error("API Key가 유효하지 않습니다.")
            else:
                st.error(f"오류: {error_msg}")
