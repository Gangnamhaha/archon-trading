import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import streamlit.components.v1 as components
from config.styles import inject_pro_css, save_user_preferences, load_user_preferences
from config.auth import require_auth
from data.database import save_chat_message, load_chat_history, clear_chat_history

st.set_page_config(page_title="AI Chat", page_icon="💬", layout="wide")
user = require_auth()
inject_pro_css()
username = user["username"]
st.title("💬 AI 채팅")

_PROVIDERS = {
    "OpenAI": {"models": ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"], "key_label": "OpenAI API Key", "key_name": "openai_api_key"},
    "Claude": {"models": ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"], "key_label": "Anthropic API Key", "key_name": "anthropic_api_key"},
    "Gemini": {"models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"], "key_label": "Google API Key", "key_name": "gemini_api_key"},
}


def call_ai(provider: str, api_key: str, model: str, messages: list, temperature: float, max_tokens: int = 4096) -> str:
    if provider == "OpenAI":
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
        return resp.choices[0].message.content

    elif provider == "Claude":
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        system_msg = ""
        chat_msgs = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                chat_msgs.append({"role": m["role"], "content": m["content"]})
        resp = client.messages.create(model=model, max_tokens=max_tokens, system=system_msg, messages=chat_msgs, temperature=temperature)
        return resp.content[0].text

    elif provider == "Gemini":
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        gen_model = genai.GenerativeModel(model)
        system_msg = ""
        history_parts = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            elif m["role"] == "user":
                history_parts.append(m["content"])
            elif m["role"] == "assistant":
                history_parts.append(m["content"])
        combined = ""
        if system_msg:
            combined = f"[시스템 지시사항: {system_msg}]\n\n"
        combined += history_parts[-1] if history_parts else ""
        resp = gen_model.generate_content(combined, generation_config={"temperature": temperature, "max_output_tokens": max_tokens})
        return resp.text

    return "지원되지 않는 제공사입니다."


def tts_speak(text: str, lang: str = "ko-KR"):
    safe = text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$").replace('"', '\\"').replace("\n", " ")
    components.html(f"""<script>window.speechSynthesis.cancel();const u=new SpeechSynthesisUtterance("{safe}");u.lang="{lang}";u.rate=1.0;window.speechSynthesis.speak(u);</script>""", height=0)


chat_settings = load_user_preferences(username, "ai_chat")

if "chat_messages" not in st.session_state or not st.session_state["chat_messages"]:
    st.session_state["chat_messages"] = load_chat_history(username, "general")
if "tts_enabled" not in st.session_state:
    st.session_state["tts_enabled"] = bool(chat_settings.get("tts_enabled", False))
if "stt_text" not in st.session_state:
    st.session_state["stt_text"] = ""

with st.sidebar:
    st.subheader("AI 제공사")
    _saved_provider = chat_settings.get("provider", "OpenAI")
    _provider_list = list(_PROVIDERS.keys())
    _prov_idx = _provider_list.index(_saved_provider) if _saved_provider in _provider_list else 0
    provider = st.selectbox("제공사 선택", _provider_list, index=_prov_idx, key="chat_provider")
    prov_info = _PROVIDERS[provider]

    st.markdown("---")
    st.subheader("API 설정")
    from data.database import load_user_setting, save_user_setting
    _saved_key = load_user_setting(username, prov_info["key_name"], "")
    if f"_api_key_{provider}" not in st.session_state:
        st.session_state[f"_api_key_{provider}"] = _saved_key

    api_key = st.text_input(prov_info["key_label"], type="password", value=st.session_state[f"_api_key_{provider}"], key="api_key_input")
    if api_key and api_key != st.session_state[f"_api_key_{provider}"]:
        st.session_state[f"_api_key_{provider}"] = api_key
        save_user_setting(username, prov_info["key_name"], api_key)

    st.markdown("---")
    _saved_model = chat_settings.get("model", prov_info["models"][0])
    _model_idx = prov_info["models"].index(_saved_model) if _saved_model in prov_info["models"] else 0
    model = st.selectbox("모델", prov_info["models"], index=_model_idx, key="chat_model")
    temperature = st.slider("Temperature", 0.0, 2.0, float(chat_settings.get("temperature", 0.7)), 0.1, key="chat_temp")
    system_prompt = st.text_area(
        "시스템 프롬프트",
        value=chat_settings.get("system_prompt", "당신은 주식 투자와 금융 분야에 전문적인 AI 어시스턴트입니다. 한국어로 답변하세요."),
        height=100, key="chat_system",
    )

    st.markdown("---")
    st.subheader("음성 설정")
    st.session_state["tts_enabled"] = st.toggle("🔊 AI 응답 자동 읽기", value=st.session_state["tts_enabled"], key="tts_toggle")

    st.markdown("---")
    if st.button("대화 초기화", use_container_width=True, key="chat_clear"):
        st.session_state["chat_messages"] = []
        clear_chat_history(username, "general")
        st.rerun()

save_user_preferences(username, "ai_chat", {
    "provider": provider, "model": model,
    "temperature": temperature, "system_prompt": system_prompt,
    "tts_enabled": st.session_state["tts_enabled"],
})

if not api_key:
    st.info(f"좌측 사이드바에서 **{prov_info['key_label']}**를 입력하세요.")
    st.markdown(f"""
    ### API Key 발급 방법

    **OpenAI**: [platform.openai.com](https://platform.openai.com) → API Keys → Create
    **Anthropic (Claude)**: [console.anthropic.com](https://console.anthropic.com) → API Keys → Create
    **Google (Gemini)**: [aistudio.google.com](https://aistudio.google.com/apikey) → API Key 생성

    > 💡 API Key는 사용자별로 저장되며 다음 로그인 시 자동 복원됩니다.
    """)
    st.stop()

for idx, msg in enumerate(st.session_state["chat_messages"]):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            if st.button("🔊", key=f"tts_{idx}", help="음성으로 읽기"):
                tts_speak(msg["content"])

stt_col1, stt_col2 = st.columns([1, 8])
with stt_col1:
    try:
        from streamlit_mic_recorder import speech_to_text
        stt_result = speech_to_text(language="ko", start_prompt="🎤", stop_prompt="⏹️", just_once=True, use_container_width=True, key="stt_main")
        if stt_result:
            st.session_state["stt_text"] = stt_result
    except ImportError:
        if st.button("🎤", key="stt_fallback"):
            st.toast("streamlit-mic-recorder 패키지 필요")
with stt_col2:
    if st.session_state["stt_text"]:
        st.info(f"🎤 인식: **{st.session_state['stt_text']}**")

prompt = st.chat_input(f"메시지를 입력하세요 ({provider})", key="chat_input_main")

if st.session_state["stt_text"] and not prompt:
    prompt = st.session_state["stt_text"]
    st.session_state["stt_text"] = ""

if prompt:
    st.session_state["chat_messages"].append({"role": "user", "content": prompt})
    save_chat_message(username, "general", "user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            messages = [{"role": "system", "content": system_prompt}]
            for m in st.session_state["chat_messages"]:
                messages.append({"role": m["role"], "content": m["content"]})
            with st.spinner(f"{provider} 응답 생성 중..."):
                reply = call_ai(provider, api_key, model, messages, temperature)
            st.markdown(reply)
            st.session_state["chat_messages"].append({"role": "assistant", "content": reply})
            save_chat_message(username, "general", "assistant", reply)
            if st.session_state["tts_enabled"]:
                tts_speak(reply)
        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower() or "auth" in error_msg.lower() or "invalid" in error_msg.lower():
                st.error(f"{provider} API Key가 유효하지 않습니다.")
            else:
                st.error(f"오류: {error_msg}")
    st.rerun()
