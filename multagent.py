import streamlit as st
from groq import Groq
from supabase import create_client, Client
from PyPDF2 import PdfReader
import requests
import json
import os
import re

# --- 1. CONFIGURAÇÃO E CACHE ---
st.set_page_config(page_title="Agente Pessoal", layout="centered")

@st.cache_data
def load_external_prompt(file_name: str) -> str:
    path = os.path.join("prompts", file_name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        # Se falhar, pelo menos mantém a essência
        return "Você é um assistente de TI sênior sarcástico e assertivo. Use humor e exemplos práticos."

if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = load_external_prompt("system.md")

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro de conexão técnica: {e}")
    st.stop()

# --- 2. FUNÇÕES DE SUPORTE ---

def buscar_contexto_mundo():
    """Coleta localização e clima reais para injetar na mente do agente."""
    try:
        geo = requests.get("http://ip-api.com/json/", timeout=5).json()
        cidade = geo.get("city", "Vila Velha")
        lat, lon = geo.get("lat", -20.32), geo.get("lon", -40.29)
        w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        clima = requests.get(w_url, timeout=5).json()
        temp = clima["current_weather"]["temperature"]
        return f"[DADOS REAIS DO MUNDO]: Localização: {cidade}. Temperatura: {temp}°C."
    except:
        return "[DADOS REAIS DO MUNDO]: Informações externas indisponíveis no momento."

def extrair_texto_pdf(file):
    try:
        reader = PdfReader(file)
        return "".join([page.extract_text() for page in reader.pages[:15]])
    except Exception as e:
        return f"Erro ao processar PDF: {e}"

def carregar_dados_simples():
    try:
        perfil = supabase.table("perfil_usuario").select("*").eq("usuario", "André").single().execute().data
        hist = supabase.table("historico_conversas").select("pergunta, resposta").eq("usuario", "André").order("created_at", desc=True).limit(5).execute().data
        return perfil, hist
    except:
        return {}, []

def check_lgpd_locally(text: str) -> bool:
    patterns = [r'\d{3}\.\d{3}\.\d{3}-\d{2}', r'[\w\.-]+@[\w\.-]+\.\w+']
    return any(re.search(p, text) for p in patterns)

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("Painel de Controle")
    if st.button("Nova Conversa", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    st.divider()
    uploaded_file = st.file_uploader("Subir Docs (PDF, TXT, PY)", type=["pdf", "txt", "py", "json"])

# --- 4. INTERFACE ---
st.title("Agente Pessoal 🤖")
if "messages" not in st.session_state: st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

# --- 5. FLUXO EXECUTIVO (O PULO DO GATO) ---
if prompt := st.chat_input("Diga algo..."):
    lgpd_risk = check_lgpd_locally(prompt)
    
    file_content = ""
    if uploaded_file:
        with st.spinner("Analisando arquivo..."):
            if uploaded_file.type == "application/pdf":
                raw_content = extrair_texto_pdf(uploaded_file)
            else:
                raw_content = uploaded_file.getvalue().decode("utf-8")
            
            raw_content = raw_content[:30000] if len(raw_content) > 30000 else raw_content
            file_content = f"\n\n[DADOS DO ARQUIVO ANEXADO]:\n{raw_content}"
            lgpd_risk = lgpd_risk or check_lgpd_locally(raw_content)

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): 
        st.markdown(prompt if not uploaded_file else f"📎 **{uploaded_file.name}**\n\n{prompt}")

    with st.chat_message("assistant"):
        perfil, hist_raw = carregar_dados_simples()
        mundo = buscar_contexto_mundo() # Pega clima/cidade agora
        
        hist_context = "\n".join([f"U: {d['pergunta']} | A: {d['resposta']}" for d in reversed(hist_raw)])
        
        # INSTRUÇÃO MESTRE: Forçamos ele a usar os dados reais e manter a persona
        instrucao_mestre = (
            f"\n\nIMPORTANTE: Use os {mundo} para responder. "
            "Seja sarcástico, assertivo e direto. Não sugira sites externos se a informação está aqui. "
            "Ignore etiquetas sociais excessivas e aja como o mentor de TI do André."
        )
        
        full_system = f"{st.session_state.system_prompt}\n{instrucao_mestre}\nPERFIL_USUARIO: {perfil}\nHISTORICO_RECENTE:\n{hist_context}"
        
        res_final = client_groq.chat.completions.create(
            messages=[
                {"role": "system", "content": full_system}, 
                *st.session_state.messages, 
                {"role": "user", "content": file_content}
            ],
            model="llama-3.3-70b-versatile"
        )
        
        resposta_final = res_final.choices[0].message.content
        if lgpd_risk: resposta_final = "🚨 **LGPD ALERT!**\n\n" + resposta_final

        st.markdown(resposta_final)
        st.session_state.messages.append({"role": "assistant", "content": resposta_final})
        
        # Salvamento
        supabase.table("historico_conversas").insert({
            "usuario": "André", "pergunta": prompt, "resposta": resposta_final, 
            "categoria": "importante" if uploaded_file else "casual"
        }).execute()
