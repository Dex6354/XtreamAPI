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

def parse_m3u_url(m3u_url):
    try:
        base_match = re.search(r"(https?://[^/]+(?::\d+)?)", m3u_url)
        user_match = re.search(r"username=([^&]+)", m3u_url)
        pwd_match = re.search(r"password=([^&]+)", m3u_url)
        if not base_match or not user_match or not pwd_match:
            return None, None, None
        return base_match.group(1), user_match.group(1), pwd_match.group(1)
    except Exception:
        return None, None, None

with st.form(key="m3u_form"):
    # O valor vem do estado, não há value fixo no widget, pois é controlado pela key
    m3u_url = st.text_input("Cole a URL do M3U", key="m3u_input_value")
    
    col1, col2 = st.columns([1,1])
    with col1:
        submit_button = st.form_submit_button("🔍 Testar API")
    with col2:
        # Passa a função clear_input como callback para o botão Limpar
        clear_button = st.form_submit_button("🧹 Limpar", on_click=clear_input)

    if submit_button or st.session_state.get("form_submitted", False):
        if not m3u_url:
            st.warning("⚠️ Por favor, insira uma URL M3U válida.")
        else:
            with st.spinner("Testando API..."):
                base, username, password = parse_m3u_url(m3u_url)

                if base and username and password:
                    username = quote(username)
                    password = quote(password)
                    api_url = f"{base}/player_api.php?username={username}&password={password}"
                    st.markdown(f"🧩 URL da API: `{base}/player_api.php?username={username}&password=***`")

                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                        "Accept": "application/json"
                    }

                    try:
                        response = requests.get(api_url, headers=headers, timeout=10, allow_redirects=True)
                        response.raise_for_status()

                        try:
                            json_data = response.json()
                            st.success("✅ API respondeu corretamente com JSON!")
                            st.json(json_data)
                        except ValueError:
                            st.error("⚠️ A resposta **não é JSON válido**.")
                            st.code(response.text, language="text")
                    except requests.exceptions.HTTPError as e:
                        st.error(f"❌ Erro HTTP: {e}")
                        st.markdown("**Detalhes da Resposta:**")
                        st.code(f"Status: {response.status_code}\nReason: {response.reason}\nHeaders: {response.headers}\nBody: {response.text}", language="text")
                    except requests.exceptions.RequestException as e:
                        st.error(f"❌ Erro ao acessar a API: {e}")
                else:
                    st.warning("⚠️ A URL está incompleta ou mal formatada. Verifique se contém 'username' e 'password'.")

if st.session_state.m3u_input_value:
    st.session_state.form_submitted = True
else:
    st.session_state.form_submitted = False
