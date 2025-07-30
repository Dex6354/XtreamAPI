import streamlit as st
import re
import requests
from urllib.parse import quote

# Configuração inicial da página
st.set_page_config(page_title="Testar Xtream API", layout="centered")

# Remover espaço superior da página
st.markdown("""
    <style>
        .block-container {
            padding-top: 2.5rem;
        }
    </style>
""", unsafe_allow_html=True)

# Título com fonte menor (estilo h5)
st.markdown("""
    <h5 style='margin-bottom: 0.1rem;'>🔌 Testar Xtream API</h5>
""", unsafe_allow_html=True)

# Estado da sessão para valor inicial
if "clipboard_value" not in st.session_state:
    st.session_state.clipboard_value = ""

# Função para extrair partes da URL M3U
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

# Criar um formulário para capturar a URL e executar ao pressionar Enter
with st.form(key="m3u_form"):
    m3u_url = st.text_input("Cole a URL do M3U", value=st.session_state.clipboard_value, key="m3u_input")
    submit_button = st.form_submit_button("🔍 Testar API")  # Botão opcional, mas ação ocorre com Enter

    # Lógica executada ao submeter o formulário (com Enter ou clicando no botão)
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

# Atualizar estado para detectar submissão automática
if m3u_url and m3u_url != st.session_state.clipboard_value:
    st.session_state.form_submitted = True
    st.session_state.clipboard_value = m3u_url
else:
    st.session_state.form_submitted = False
