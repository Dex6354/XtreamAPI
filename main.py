import streamlit as st
import re
import requests
from urllib.parse import quote

st.set_page_config(page_title="Testar Xtream API", layout="centered")

st.markdown("""
    <style>
        .block-container {
            padding-top: 2.5rem;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <h5 style='margin-bottom: 0.1rem;'>🔌 Testar Xtream API</h5>
""", unsafe_allow_html=True)

if "m3u_input_value" not in st.session_state:
    st.session_state.m3u_input_value = ""

def clear_input():
    st.session_state.m3u_input_value = ""
    st.session_state.form_submitted = False

def parse_m3u_urls(message):
    url_pattern = r"(https?://[^\s]+?get\.php\?username=[^\s&]+&password=[^\s&]+&type=m3u_plus(&output=[^\s]+)?)"
    urls = re.findall(url_pattern, message)
    parsed_urls = []
    for url, _ in urls:
        base_match = re.search(r"(https?://[^/]+(?::\d+)?)", url)
        user_match = re.search(r"username=([^&]+)", url)
        pwd_match = re.search(r"password=([^&]+)", url)
        if base_match and user_match and pwd_match:
            parsed_urls.append({
                "url": url,
                "base": base_match.group(1),
                "username": user_match.group(1),
                "password": pwd_match.group(1)
            })
    return parsed_urls

def test_api(base, username, password):
    username = quote(username)
    password = quote(password)
    api_url = f"{base}/player_api.php?username={username}&password={password}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    try:
        response = requests.get(api_url, headers=headers, timeout=10, allow_redirects=True)
        response.raise_for_status()
        try:
            response.json()
            return True
        except ValueError:
            return False
    except requests.exceptions.RequestException:
        return False

with st.form(key="m3u_form"):
    m3u_message = st.text_area("Cole a mensagem com URLs M3U", key="m3u_input_value", height=200)

    col1, col2 = st.columns([1,1])
    with col1:
        submit_button = st.form_submit_button("🔍 Testar APIs")
    with col2:
        clear_button = st.form_submit_button("🧹 Limpar", on_click=clear_input)

    if submit_button or st.session_state.get("form_submitted", False):
        if not m3u_message:
            st.warning("⚠️ Por favor, insira uma mensagem com URLs M3U.")
        else:
            with st.spinner("Testando APIs..."):
                parsed_urls = parse_m3u_urls(m3u_message)
                if not parsed_urls:
                    st.warning("⚠️ Nenhuma URL M3U válida encontrada na mensagem.")
                else:
                    results = []
                    for parsed in parsed_urls:
                        is_json = test_api(parsed["base"], parsed["username"], parsed["password"])
                        api_url = f"{parsed['base']}/player_api.php?username={quote(parsed['username'])}&password={quote(parsed['password'])}"
                        results.append({"api_url": api_url, "is_json": is_json})

                    st.markdown("**JSON nas URLs encontradas:**")
                    for result in results:
                        status = "✅" if result["is_json"] else "❌"
                        st.markdown(f"- {status} <a href='{result['api_url']}' target='_blank'>{result['api_url']}</a>", unsafe_allow_html=True)

if st.session_state.m3u_input_value:
    st.session_state.form_submitted = True
else:
    st.session_state.form_submitted = False
