import streamlit as st
import re
import requests
from urllib.parse import quote, urlparse
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import unicodedata

# Configuração da página
st.set_page_config(page_title="Xtream API Checker Pro", layout="centered")

st.markdown("""
    <style>
        .block-container { padding-top: 2.5rem; }
        .stCodeBlock, code { white-space: pre-wrap !important; word-break: break-all !important; }
    </style>
""", unsafe_allow_html=True)

st.title("🔌 Xtream API Checker")

# --- FUNÇÕES DE PARSE ---

def normalize_text(text):
    if not isinstance(text, str): return ""
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8').lower()

def extract_credentials(text):
    """Extrai credenciais tanto de URLs completas quanto de campos isolados."""
    results = []
    
    # 1. Tentar capturar URL completa (M3U ou Player API)
    m3u_pattern = r"(https?://[^\s|]+)/get\.php\?username=([^\s&]+)&password=([^\s&]+)"
    api_pattern = r"(https?://[^\s|]+)/player_api\.php\?username=([^\s&]+)&password=([^\s&]+)"
    
    found_urls = re.findall(m3u_pattern, text) + re.findall(api_pattern, text)
    for base, user, pwd in found_urls:
        results.append({"base": base, "username": user, "password": pwd})

    # 2. Se não achou URL, ou para garantir, busca campos isolados (Host, User, Pass)
    # Procura por padrões como "Host: http://..." ou "User: admin"
    if not results:
        hosts = re.findall(r"(?:Host|Real|http-port)\s*[:➩>]*\s*(https?://[^\s]+)", text, re.I)
        users = re.findall(r"(?:User|Username|Usuário)\s*[:➩>]*\s*([a-zA-Z0-9._-]+)", text, re.I)
        pwds = re.findall(r"(?:Pass|Password|Senha)\s*[:➩>]*\s*([a-zA-Z0-9._-]+)", text, re.I)
        
        if hosts and users and pwds:
            # Pega o primeiro de cada categoria encontrado
            base_url = hosts[0].split(':80')[0] if ':80' in hosts[0] else hosts[0]
            # Remove barras finais
            base_url = base_url.rstrip('/')
            results.append({
                "base": base_url,
                "username": users[0],
                "password": pwds[0]
            })

    # Remover duplicatas mantendo ordem
    unique_results = []
    seen = set()
    for item in results:
        identifier = (item['base'], item['username'], item['password'])
        if identifier not in seen:
            seen.add(identifier)
            unique_results.append(item)
            
    return unique_results

# --- FUNÇÕES DE API ---

def get_xtream_info(cred, search_query=None):
    base = cred["base"]
    u, p = cred["username"], cred["password"]
    api_url = f"{base}/player_api.php?username={quote(u)}&password={quote(p)}"
    
    data_res = {
        "valid": False, "exp": "N/A", "active": "0", "max": "0",
        "live": 0, "vod": 0, "series": 0, "matches": []
    }

    try:
        # 1. Login e Informações de Usuário
        response = requests.get(api_url, timeout=10)
        if response.status_code != 200: return cred, data_res
        
        info = response.json()
        u_info = info.get("user_info", {})
        
        if u_info.get("auth") == 0 or "auth" not in u_info:
            return cred, data_res # Falha na autenticação

        data_res["valid"] = True
        
        # Expiração
        exp = u_info.get("exp_date")
        if exp:
            if exp == "null" or not str(exp).isdigit(): data_res["exp"] = "Ilimitado"
            else: data_res["exp"] = datetime.fromtimestamp(int(exp)).strftime('%d/%m/%Y')

        data_res["active"] = u_info.get("active_cons", "0")
        data_res["max"] = u_info.get("max_connections", "0")

        # 2. Contagem de Conteúdo (Paralelo)
        actions = {"live": "get_live_streams", "vod": "get_vod_streams", "series": "get_series"}
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_map = {executor.submit(requests.get, f"{api_url}&action={act}", timeout=12): key for key, act in actions.items()}
            for future in as_completed(future_map):
                key = future_map[future]
                try:
                    content = future.result().json()
                    if isinstance(content, list):
                        data_res[key] = len(content)
                        
                        # Busca simples se houver query
                        if search_query:
                            s_norm = normalize_text(search_query)
                            for item in content:
                                name = item.get("name", "")
                                if s_norm in normalize_text(name):
                                    data_res["matches"].append(f"[{key.upper()}] {name}")
                except: continue

    except Exception as e:
        print(f"Erro: {e}")
        
    return cred, data_res

# --- INTERFACE STREAMLIT ---

input_text = st.text_area("Cole os dados do painel ou a URL M3U:", height=200, placeholder="Pode colar o texto completo com Host, User e Pass...")
search_input = st.text_input("🔍 Buscar filme, série ou canal (Opcional)")

if st.button("🚀 Validar e Contar Conteúdo"):
    if not input_text:
        st.warning("Por favor, cole algum dado para analisar.")
    else:
        creds_found = extract_credentials(input_text)
        
        if not creds_found:
            st.error("Não encontrei um padrão de Host, Usuário e Senha. Verifique o texto colado.")
        else:
            for cred in creds_found:
                with st.spinner(f"Acessando {cred['base']}..."):
                    c, res = get_xtream_info(cred, search_input)
                    
                    if not res["valid"]:
                        st.error(f"❌ Falha no Login: {c['base']} (User: {c['username']})")
                    else:
                        st.success(f"✅ Conectado: {c['base']}")
                        
                        with st.container(border=True):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"👤 **Usuário:** `{c['username']}`")
                                st.write(f"🔑 **Senha:** `{c['password']}`")
                                st.write(f"📅 **Expira em:** `{res['exp']}`")
                            with col2:
                                st.write(f"📺 **Canais:** `{res['live']}`")
                                st.write(f"🎬 **Filmes:** `{res['vod']}`")
                                st.write(f"🍿 **Séries:** `{res['series']}`")
                                st.write(f"👥 **Conexões:** `{res['active']}/{res['max']}`")
                            
                            if res["matches"]:
                                with st.expander("🔎 Resultados da Busca"):
                                    for m in res["matches"][:15]: st.write(m)
                                    if len(res["matches"]) > 15: st.write("...")
