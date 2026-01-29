import streamlit as st
import re
import requests
from urllib.parse import quote, urlparse
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import unicodedata
import urllib3
import json

# Desativa avisos de SSL (necessário para servidores http/https com certificado inválido)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuração da página
st.set_page_config(page_title="Xtream API Checker Pro", layout="centered")

# CSS Otimizado
st.markdown("""
    <style>
        .block-container { padding-top: 2rem; }
        .stCodeBlock, code { white-space: pre-wrap !important; word-break: break-all !important; }
        .success-box { padding: 10px; border-radius: 5px; background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .error-box { padding: 10px; border-radius: 5px; background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    </style>
""", unsafe_allow_html=True)

st.title("🔌 Xtream API Checker (Anti-Bloqueio)")
st.info("ℹ️ Se retornar '0 canais' mas mostrar categorias, o servidor bloqueia o download da lista completa (mas funciona no App).")

# Estado da Sessão
if "m3u_input_value" not in st.session_state: st.session_state.m3u_input_value = ""
if "search_name" not in st.session_state: st.session_state.search_name = ""

def clear_input():
    st.session_state.m3u_input_value = ""
    st.session_state.search_name = ""
    st.session_state.form_submitted = False

def normalize_text(text):
    if not isinstance(text, str): return ""
    return unicodedata.normalize('NFKD', text.lower()).encode('ascii', 'ignore').decode('utf-8')

def parse_urls(message):
    # Regex robusta para capturar http/https, portas e credenciais
    pattern = r"(https?://[a-zA-Z0-9.-]+(?::\d+)?/[^\s]*?(?:get|player_api)\.php\?username=([^\s&]+)&password=([^\s&]+))"
    matches = re.findall(pattern, message)
    
    unique_data = {}
    for url, user, pwd in matches:
        base_match = re.search(r"(https?://[^/]+(?::\d+)?)", url)
        if base_match:
            base = base_match.group(1).replace("https://", "http://") # Força HTTP para evitar erros de handshake SSL em alguns painéis
            key = (base, user, pwd)
            if key not in unique_data:
                unique_data[key] = {"base": base, "username": user, "password": pwd}
    
    return list(unique_data.values())

def fetch_data(session, url, retries=2):
    """Função auxiliar com retry e headers específicos de Android"""
    headers = {
        "User-Agent": "okhttp/3.12.1", # Simula App Android Nativo
        "Accept": "*/*",
        "Connection": "keep-alive"
    }
    for i in range(retries):
        try:
            r = session.get(url, headers=headers, timeout=20, verify=False)
            r.raise_for_status()
            try:
                return r.json(), r.text
            except ValueError:
                return None, r.text # Retorna texto se não for JSON
        except Exception:
            if i == retries - 1: return None, None
            time.sleep(1)
    return None, None

def check_content_availability(session, base_url, type_key):
    """
    Tenta pegar streams. Se falhar ou vier vazio, tenta pegar categorias.
    type_key: 'live', 'vod', 'series'
    """
    action_streams = f"get_{type_key}_streams" if type_key != "series" else "get_series"
    action_categories = f"get_{type_key}_categories"
    
    # 1. Tenta pegar lista completa
    data, raw = fetch_data(session, f"{base_url}&action={action_streams}")
    
    count = 0
    sample_data = []
    method = "Full List"
    
    if isinstance(data, list):
        count = len(data)
        sample_data = data
    elif isinstance(data, dict):
        # Alguns painéis retornam dict na lista de streams se houver erro
        count = 0 
    
    # 2. Se retornou 0, tenta pegar Categorias (Fallback)
    if count == 0:
        cat_data, _ = fetch_data(session, f"{base_url}&action={action_categories}")
        if isinstance(cat_data, list) and len(cat_data) > 0:
            count = len(cat_data)
            method = "Categories Only" # Indica que só conseguimos ler categorias
            
    return count, method, sample_data

def get_series_season_info(session, base_url, series_id):
    """Pega detalhes da série se possível"""
    url = f"{base_url}&action=get_series_info&series_id={series_id}"
    data, _ = fetch_data(session, url)
    if data and "episodes" in data:
        seasons = [k for k in data["episodes"].keys() if k.isdigit()]
        if seasons:
            last_season = max(map(int, seasons))
            eps = data["episodes"][str(last_season)]
            return f"S{last_season:02d}E{len(eps):02d}"
    return "Info N/A"

def process_api(data, search_query):
    session = requests.Session()
    base_auth = f"{data['base']}/player_api.php?username={data['username']}&password={data['password']}"
    
    # 1. Login e Info do Usuário
    login_data, raw_login = fetch_data(session, base_auth)
    
    result = {
        "url_display": base_auth,
        "base": data['base'],
        "user": data['username'],
        "pass": data['password'],
        "status": "Falha",
        "exp": "N/A",
        "con": "N/A",
        "live": 0, "live_method": "",
        "vod": 0, "vod_method": "",
        "series": 0, "series_method": "",
        "matches": {"Canais": [], "Filmes": [], "Séries": []},
        "raw_debug": raw_login
    }

    if not login_data or "user_info" not in login_data:
        return result

    result["status"] = "Ativo"
    u_info = login_data.get("user_info", {})
    s_info = login_data.get("server_info", {})
    
    # Processa Data de Expiração
    exp = u_info.get("exp_date")
    if exp:
        try:
            ts = int(exp)
            result["exp"] = "Nunca" if ts > 9999999999 else datetime.fromtimestamp(ts).strftime('%d/%m/%Y')
        except: result["exp"] = "Erro data"
    
    result["con"] = f"{u_info.get('active_cons', 0)} / {u_info.get('max_connections', 0)}"
    
    # Atualiza URL real se houver redirecionamento no server info
    real_url = s_info.get("url")
    if real_url:
        real_url_clean = real_url.replace("https://", "http://") # Normaliza protocolo
        if not real_url_clean.startswith("http"): real_url_clean = "http://" + real_url_clean
        if ":" in data['base'] and ":" not in real_url_clean: # Mantem porta se original tinha e novo nao
             pass 
        else:
             # Atualiza base para as requisições de conteúdo
             base_auth = f"{real_url_clean}/player_api.php?username={data['username']}&password={data['password']}"

    # 2. Busca Conteúdo em Paralelo
    with ThreadPoolExecutor(max_workers=3) as executor:
        f_live = executor.submit(check_content_availability, session, base_auth, "live")
        f_vod = executor.submit(check_content_availability, session, base_auth, "vod")
        f_series = executor.submit(check_content_availability, session, base_auth, "series")
        
        # Resultados Live
        l_count, l_method, l_data = f_live.result()
        result["live"] = l_count
        result["live_method"] = l_method
        
        # Resultados VOD
        v_count, v_method, v_data = f_vod.result()
        result["vod"] = v_count
        result["vod_method"] = v_method
        
        # Resultados Series
        s_count, s_method, s_data = f_series.result()
        result["series"] = s_count
        result["series_method"] = s_method
        
        # 3. Busca (Search) - Só funciona se method == 'Full List'
        if search_query:
            norm_q = normalize_text(search_query)
            
            # Busca Canais
            if l_method == "Full List":
                result["matches"]["Canais"] = [x["name"] for x in l_data if norm_q in normalize_text(x.get("name", ""))]
            
            # Busca Filmes
            if v_method == "Full List":
                result["matches"]["Filmes"] = [x["name"] for x in v_data if norm_q in normalize_text(x.get("name", ""))]
                
            # Busca Séries (Mais complexo)
            if s_method == "Full List":
                found_series = [x for x in s_data if norm_q in normalize_text(x.get("name", ""))]
                for s in found_series:
                    info = get_series_season_info(session, base_auth, s["series_id"])
                    result["matches"]["Séries"].append(f"{s['name']} ({info})")

    return result

# --- Interface ---

with st.form("checker_form"):
    text_input = st.text_area("Cole os dados ou URL:", key="m3u_input_value", height=150)
    search_input = st.text_input("Buscar (Opcional):", key="search_name")
    
    c1, c2 = st.columns([1, 4])
    submitted = c1.form_submit_button("🚀 Verificar")
    cleaned = c2.form_submit_button("🧹 Limpar", on_click=clear_input)

if submitted and text_input:
    targets = parse_urls(text_input)
    
    if not targets:
        st.error("❌ Nenhuma URL ou credencial encontrada.")
    else:
        with st.status("🔍 Conectando aos servidores...", expanded=True) as status:
            results = []
            for target in targets:
                st.write(f"Testando: {target['base']}...")
                res = process_api(target, search_input)
                results.append(res)
            status.update(label="Concluído!", state="complete", expanded=False)
        
        st.divider()
        
        for r in results:
            # Cabeçalho do Card
            icon = "✅" if r["status"] == "Ativo" else "❌"
            st.markdown(f"### {icon} Servidor: `{r['base']}`")
            
            if r["status"] == "Ativo":
                with st.container():
                    # Info Básica
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Vencimento", r["exp"])
                    c2.metric("Conexões", r["con"])
                    
                    # Logica de exibição dos contadores
                    def format_count(count, method):
                        if count == 0: return "0"
                        if method == "Categories Only": return f"{count} (Categorias*)"
                        return str(count)

                    c3.metric("Status", "Online")
                    
                    st.markdown("---")
                    
                    # Conteúdo
                    k1, k2, k3 = st.columns(3)
                    k1.info(f"📺 **Canais:** {format_count(r['live'], r['live_method'])}")
                    k2.success(f"🎬 **Filmes:** {format_count(r['vod'], r['vod_method'])}")
                    k3.warning(f"🍿 **Séries:** {format_count(r['series'], r['series_method'])}")
                    
                    if "Categories Only" in [r['live_method'], r['vod_method'], r['series_method']]:
                        st.caption("(*) O servidor bloqueou a contagem individual de itens. O número exibido refere-se às pastas (Categorias) encontradas, confirmando que há conteúdo.")

                    # Resultados da Busca
                    if search_input:
                        st.markdown("#### 🔎 Resultados da Busca")
                        has_results = False
                        for cat, items in r["matches"].items():
                            if items:
                                has_results = True
                                with st.expander(f"{cat} Encontrados ({len(items)})"):
                                    for i in items: st.text(f"- {i}")
                        if not has_results:
                            if "Categories Only" in [r['live_method'], r['vod_method'], r['series_method']]:
                                st.warning("A busca detalhada falhou porque o servidor ocultou a lista de canais. Apenas verificação de login foi possível.")
                            else:
                                st.info("Nenhum item encontrado com esse nome.")
            
            else:
                st.error(f"Falha ao logar em {r['base']}. Verifique usuário/senha ou se o DNS está offline.")
            
            # Área de Debug
            with st.expander("🛠️ Ver Resposta Bruta (Debug JSON)"):
                st.json(r.get("raw_debug"))
                st.text(f"Raw Text Preview: {str(r.get('raw_debug'))[:500]}")
            
            st.markdown("---")
