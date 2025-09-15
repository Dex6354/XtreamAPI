import streamlit as st
import re
import requests
from urllib.parse import quote, urlparse
from datetime import datetime
import time

# Configuração da página do Streamlit
st.set_page_config(page_title="Testar Xtream API", layout="centered")

# Estilos CSS para ajustar o layout e o comportamento de quebra de linha
st.markdown("""
    <style>
        .block-container {
            padding-top: 2.5rem;
        }
        .stCodeBlock, code {
            white-space: pre-wrap !important;
            word-break: break-all !important;
        }
        a {
            word-break: break-all !important;
        }
    </style>
""", unsafe_allow_html=True)

# Título e descrição da página
st.markdown("""
    <h5 style='margin-bottom: 0.1rem;'>🔌 Testar Xtream API</h5>
    <p style='margin-top: 0.1rem;'>
        ✅ <strong>Funcionam no IPTV SmartersPro:</strong> Servidores terminados com <code>.ca</code>, <code>.io</code>, <code>.cc</code>, <code>.me</code>, <code>.in</code> e porta <code>80</code>.<br>
        ❌ <strong>Não funcionam:</strong> Servidores terminados com <code>.site</code>, <code>.com</code>, <code>.lat</code>, <code>.live</code>, <code>.top</code>, <code>.icu</code>, <code>.xyz</code>, <code>.online</code>.
    </p>
""", unsafe_allow_html=True)

# Inicializa o estado da sessão para o campo de texto
if "m3u_input_value" not in st.session_state:
    st.session_state.m3u_input_value = ""

def clear_input():
    """Limpa o campo de texto e re-define o estado do formulário."""
    st.session_state.m3u_input_value = ""
    st.session_state.form_submitted = False

def parse_urls(message):
    """Extrai URLs M3U e Player API da mensagem de texto, evitando duplicatas."""
    m3u_pattern = r"(https?://[^\s]+?get\.php\?username=[^\s&]+&password=[^\s&]+&type=m3u_plus(?:&output=[^\s]+)?)"
    api_pattern = r"(https?://[^\s]+?player_api\.php\?username=[^\s&]+&password=[^\s&]+)"
    urls = re.findall(m3u_pattern, message) + re.findall(api_pattern, message)
    
    parsed_urls = []
    unique_urls = set()

    for url in urls:
        current_url = url[0] if isinstance(url, tuple) else url

        base_match = re.search(r"(https?://[^/]+(?::\d+)?)", current_url)
        user_match = re.search(r"username=([^&]+)", current_url)
        pwd_match = re.search(r"password=([^&]+)", current_url)
        
        if base_match and user_match and pwd_match:
            base = base_match.group(1).replace("https://", "http://")
            username = user_match.group(1)
            password = pwd_match.group(1)
            
            identifier = (base, username, password)
            if identifier not in unique_urls:
                unique_urls.add(identifier)
                parsed_urls.append({
                    "url": current_url,
                    "base": base,
                    "username": username,
                    "password": password
                })
    return parsed_urls

def test_api(base, username, password):
    """Testa a API Xtream e retorna informações detalhadas do usuário e do servidor."""
    username_encoded = quote(username)
    password_encoded = quote(password)
    api_url = f"{base}/player_api.php?username={username_encoded}&password={password_encoded}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    try:
        response = requests.get(api_url, headers=headers, timeout=10, allow_redirects=True)
        response.raise_for_status()
        json_data = response.json()

        server_info = json_data.get("server_info", {})
        real_server = server_info.get("url", base)
        
        # Garante que a URL real tenha o prefixo http://
        if not real_server.startswith(("http://", "https://")):
            real_server = "http://" + real_server
        real_server = real_server.replace("https://", "http://").rstrip("/")

        user_info = json_data.get("user_info", {})
        exp_date_ts = user_info.get("exp_date")
        
        if exp_date_ts and str(exp_date_ts).isdigit():
            if int(exp_date_ts) > time.time() * 2:
                 exp_date_str = "Nunca expira"
            else:
                 exp_date_str = datetime.fromtimestamp(int(exp_date_ts)).strftime('%d/%m/%Y %H:%M:%S')
        else:
            exp_date_str = "N/A"

        return {
            "is_json": True,
            "real_server": real_server,
            "exp_date": exp_date_str,
            "active_cons": user_info.get("active_cons", "N/A"),
            "max_connections": user_info.get("max_connections", "N/A"),
        }
    except (requests.exceptions.RequestException, ValueError):
        return {
            "is_json": False,
            "real_server": base,
            "exp_date": "Falha ao obter",
            "active_cons": "Falha ao obter",
            "max_connections": "Falha ao obter",
        }

# Criação do formulário na interface
with st.form(key="m3u_form"):
    m3u_message = st.text_area("Cole a mensagem com URLs M3U ou Player API", key="m3u_input_value", height=200)

    col1, col2 = st.columns([1,1])
    with col1:
        submit_button = st.form_submit_button("🔍 Testar APIs")
    with col2:
        clear_button = st.form_submit_button("🧹 Limpar", on_click=clear_input)

    # Lógica de processamento ao submeter o formulário
    if submit_button or st.session_state.get("form_submitted", False):
        if not m3u_message:
            st.warning("⚠️ Por favor, insira uma mensagem com URLs.")
        else:
            with st.spinner("Analisando e testando as APIs..."):
                parsed_urls = parse_urls(m3u_message)
                
                if not parsed_urls:
                    st.warning("⚠️ Nenhuma URL válida encontrada na mensagem.")
                else:
                    results = []
                    
                    for parsed in parsed_urls:
                        api_result = test_api(parsed["base"], parsed["username"], parsed["password"])
                        api_url = f"{parsed['base']}/player_api.php?username={quote(parsed['username'])}&password={quote(parsed['password'])}"
                        
                        results.append({
                            "api_url": api_url,
                            "username": parsed["username"],
                            "password": parsed["password"],
                            **api_result
                        })

                    # Ordena a lista: resultados com JSON vêm primeiro (True=1, False=0)
                    results.sort(key=lambda item: item['is_json'], reverse=True)

                    st.markdown("---")
                    st.markdown("#### Resultados")
                    
                    if not results:
                        st.info("Nenhuma URL foi processada.")
                    else:
                        for result in results:
                            # O status agora depende apenas se a API retornou JSON
                            status = "✅" if result["is_json"] else "❌"
                            
                            # Exibe a URL da API como um link clicável
                            st.markdown(
                                f"**{status} API URL:** <a href='{result['api_url']}' target='_blank'>{result['api_url']}</a>",
                                unsafe_allow_html=True
                            )

                            # Container para agrupar as informações de depuração
                            with st.container(border=True):
                                # Campos com botão para copiar
                                st.text("Usuário:")
                                st.code(result['username'], language="text")
                                st.text("Senha:")
                                st.code(result['password'], language="text")
                                st.text("URL Real:")
                                st.code(result['real_server'], language="text")

                                # Campos de informação sem botão de cópia
                                st.markdown(f"**Data de Expiração:** `{result['exp_date']}`")
                                st.markdown(f"**Usuários Ativos:** `{result['active_cons']}`")
                                st.markdown(f"**Usuários Máximos:** `{result['max_connections']}`")
                            st.markdown("---") # Separador visual

# Mantém o formulário submetido se houver texto, para evitar que os resultados desapareçam
if st.session_state.m3u_input_value:
    st.session_state.form_submitted = True
else:
    st.session_state.form_submitted = False
