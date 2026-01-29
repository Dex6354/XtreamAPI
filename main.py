import streamlit as st
import re
import requests
from urllib.parse import quote, urlparse
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import unicodedata

# Configuração da página do Streamlit
st.set_page_config(page_title="Testar Xtream API", layout="centered")

# Estilos CSS
st.markdown("""
    <style>
        .block-container { padding-top: 2.5rem; }
        .stCodeBlock, code { white-space: pre-wrap !important; word-break: break-all !important; }
        .stAlert { margin-top: 1rem; }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <h5 style='margin-bottom: 0.1rem;'>🔌 Testar Xtream API</h5>
    <p style='margin-top: 0.1rem;'>Insira o texto com o link M3U ou dados de acesso abaixo.</p>
""", unsafe_allow_html=True)

if "m3u_input_value" not in st.session_state:
    st.session_state.m3u_input_value = ""
if "search_name" not in st.session_state:
    st.session_state.search_name = ""

def clear_input():
    st.session_state.m3u_input_value = ""
    st.session_state.search_name = ""

def normalize_text(text):
    if not isinstance(text, str): return ""
    text = text.lower()
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')

def parse_urls(message):
    # Regex melhorada para capturar links M3U mesmo com caracteres especiais em volta
    m3u_pattern = r"(https?://[^\s\"']+?get\.php\?username=([^\s&\"']+)\&password=([^\s&\"']+))"
    api_pattern = r"(https?://[^\s\"']+?player_api\.php\?username=([^\s&\"']+)\&password=([^\s&\"']+))"
    
    found = re.findall(m3u_pattern, message) + re.findall(api_pattern, message)
    parsed_urls = []
    unique_ids = set()

    for item in found:
        full_url, user, pwd = item
        # Extrai a base (protocolo + host + porta)
        parsed_uri = urlparse(full_url)
        base = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
        
        identifier = (base, user, pwd)
        if identifier not in unique_ids:
            unique_ids.add(identifier)
            parsed_urls.append({"base": base, "username": user, "password": pwd})
    return parsed_urls

def get_xtream_info(url_data, search_name=None):
    base, user, pwd = url_data["base"], url_data["username"], url_data["password"]
    # Garante que as credenciais estejam limpas de espaços
    user = user.strip()
    pwd = pwd.strip()
    
    u_enc, p_enc = quote(user), quote(pwd)
    api_url = f"{base}/player_api.php?username={u_enc}&password={p_enc}"
    
    res = {
        "is_json": False, "real_server": base, "exp_date": "Falha no login",
        "active_cons": "0", "max_connections": "0", "has_adult_content": False,
        "is_accepted_domain": False, "live_count": 0, "vod_count": 0, "series_count": 0,
        "search_matches": {"Canais": [], "Filmes": [], "Séries": {}}
    }

    try:
        # 1. Tentar o login inicial
        response = requests.get(api_url, timeout=15)
        if response.status_code != 200:
            return url_data, res
            
        main_resp = response.json()
        
        # Verifica se o login foi aceito (Xtream retorna user_info se OK)
        if "user_info" not in main_resp or main_resp.get("user_info", {}).get("auth") == 0:
            return url_data, res
        
        res["is_json"] = True
        user_info = main_resp.get("user_info", {})
        
        # 2. Data de Expiração
        exp = user_info.get("exp_date")
        if exp is None or exp == "" or exp == "null":
            res["exp_date"] = "Ilimitado"
        elif str(exp).isdigit():
            res["exp_date"] = datetime.fromtimestamp(int(exp)).strftime('%d/%m/%Y')
        else:
            res["exp_date"] = str(exp)
        
        res["active_cons"] = str(user_info.get("active_cons", "0"))
        res["max_connections"] = str(user_info.get("max_connections", "0"))
        
        # 3. Validar Domínio
        valid_tlds = ('.ca', '.io', '.cc', '.me', '.in', '.top', '.space')
        domain = urlparse(base).netloc.lower()
        res["is_accepted_domain"] = any(domain.endswith(tld) for tld in valid_tlds)

        # 4. Obter Contagens Reais (Live, VOD, Series) via Threading
        actions = {"live": "get_live_streams", "vod": "get_vod_streams", "series": "get_series"}
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_key = {executor.submit(requests.get, f"{api_url}&action={act}", timeout=20): key for key, act in actions.items()}
            
            for future in as_completed(future_to_key):
                key = future_to_key[future]
                try:
                    data = future.result().json()
                    if isinstance(data, list):
                        res[f"{key}_count"] = len(data)
                        
                        # Busca opcional
                        if search_name:
                            s_norm = normalize_text(search_name)
                            for item in data:
                                name = item.get("name", "")
                                if s_norm in normalize_text(name):
                                    cat_name = "Canais" if key == "live" else ("Filmes" if key == "vod" else "Séries")
                                    if key == "series":
                                        res["search_matches"]["Séries"][name] = "Disponível"
                                    else:
                                        res["search_matches"][cat_name].append(name)
                except:
                    continue

    except Exception as e:
        print(f"Erro no teste: {e}")
    
    return url_data, res

# Interface Streamlit
with st.form(key="m3u_form"):
    m3u_message = st.text_area("Cole o texto ou link M3U aqui", key="m3u_input_value", height=200)
    search_query = st.text_input("🔍 Buscar canal ou filme (opcional)", key="search_name")
    
    col_btn1, col_btn2 = st.columns([1,1])
    with col_btn1:
        submit = st.form_submit_button("🚀 Testar Acesso")
    with col_btn2:
        st.form_submit_button("🧹 Limpar", on_click=clear_input)

if submit:
    if not m3u_message:
        st.warning("Por favor, cole um conteúdo antes de testar.")
    else:
        parsed = parse_urls(m3u_message)
        if not parsed:
            st.error("Nenhum link ou credencial Xtream válida foi identificada no texto.")
        else:
            with st.spinner("Conectando ao servidor e contando mídias..."):
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(get_xtream_info, url, search_query) for url in parsed]
                    for future in as_completed(futures):
                        orig, info = future.result()
                        
                        status_icon = "✅" if info["is_json"] else "❌"
                        st.markdown(f"### {status_icon} Servidor: `{orig['base']}`")
                        
                        with st.container(border=True):
                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.write(f"👤 **Usuário:** `{orig['username']}`")
                                st.write(f"🔑 **Senha:** `{orig['password']}`")
                                st.write(f"📅 **Expira:** `{info['exp_date']}`")
                                st.markdown(f"🌐 **Domínio OK:** {'✅' if info['is_accepted_domain'] else '❌'}")
                            
                            with col_b:
                                st.write(f"📺 **Canais:** `{info['live_count']}`")
                                st.write(f"🎬 **Filmes:** `{info['vod_count']}`")
                                st.write(f"🍿 **Séries:** `{info['series_count']}`")
                                st.write(f"👥 **Conexões:** `{info['active_cons']}/{info['max_connections']}`")

                        if search_query and any(info["search_matches"].values()):
                            with st.expander(f"🔎 Resultados para '{search_query}'"):
                                for cat, matches in info["search_matches"].items():
                                    if matches:
                                        st.write(**f"{cat}:**")
                                        if isinstance(matches, dict):
                                            for n, v in matches.items(): st.write(f"- {n}")
                                        else:
                                            for m in matches[:15]: st.write(f"- {m}")
                        st.divider()

st.info("Nota: Este sistema extrai o Host, Usuário e Senha automaticamente do link M3U colado.")
