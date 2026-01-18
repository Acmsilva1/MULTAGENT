import streamlit as st
from groq import Groq
from supabase import create_client, Client
from PyPDF2 import PdfReader
import requests
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
        return "Você é um mentor de TI sênior, assertivo e sarcástico."

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro de conexão técnica: {e}")
    st.stop()

# --- 2. FUNÇÕES DE SUPORTE (AS FERRAMENTAS) ---

def buscar_contexto_mundo():
    """Captura localização e clima reais via IP e Open-Meteo."""
    try:
        geo = requests.get("http://ip-api.com/json/", timeout=5).json()
        cidade = geo.get("city", "Vila Velha")
        lat, lon = geo.get("lat", -20.32), geo.get("lon", -40.29)
        w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        clima = requests.get(w_url, timeout=5).json()
        temp = clima["current_weather"]["temperature"]
        return f"[DADOS REAIS DO MUNDO]: Localização: {cidade}. Temperatura: {temp}°C."
    except:
        return "[DADOS REAIS DO MUNDO]: Localização e clima indisponíveis no momento."

def extrair_texto_pdf(file):
    try:
        reader = PdfReader(file)
        return "".join([page.extract_text() for page in reader.pages[:15]])
    except Exception as e:
        return f"Erro ao processar PDF: {e}"

def carregar_dados_usuario():
    try:
        perfil = supabase.table("perfil_usuario").select("*").eq("usuario", "André").single().execute().data
        hist = supabase.table("historico_conversas").select("pergunta, resposta").eq("usuario", "André").order("created_at", desc=True).limit(5).execute().data
        return perfil, hist
    except:
        return {}, []

def check_lgpd_locally(text: str) -> bool:
    patterns = [r'\d{3}\.\d{3}\.\d{3}-\d{2}', r'[\w\.-]+@[\w\.-]+\.\w+']
    return any(re.search(p, text) for p in patterns)

# --- 3. SIDEBAR (O PAINEL DE CONTROLE RESTAURADO) ---
with st.sidebar:
    st.header("Painel de Controle")
    if st.button("Nova Conversa", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.divider()
    uploaded_file = st.file_uploader("Subir Docs (PDF, TXT)", type=["pdf", "txt"])
    
    if st.button("Limpar Histórico Casual", use_container_width=True):
        try:
            supabase.table("historico_conversas").delete().eq("usuario", "André").eq("categoria", "casual").execute()
            st.success("Histórico limpo!")
        except Exception as e:
            st.error(f"Erro: {e}")

# --- 4. INTERFACE DE CHAT ---
st.title("Agente Pessoal 🤖")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): 
        st.markdown(msg["content"])

# --- 5. FLUXO EXECUTIVO ---
if prompt := st.chat_input("Diga algo ao seu Agente..."):
    # Coleta de Contextos
    perfil, hist_raw = carregar_dados_usuario()
    mundo_info = buscar_contexto_mundo()
    
    file_context = ""
    if uploaded_file:
        with st.spinner("Analisando arquivo..."):
            if uploaded_file.type == "application/pdf":
                raw_content = extrair_texto_pdf(uploaded_file)
            else:
                raw_content = uploaded_file.getvalue().decode("utf-8")
            file_context = f"\n\n[DADOS DO ARQUIVO]:\n{raw_content[:25000]}"

    # CONSTRUÇÃO DA PERSONA BLINDADA
    system_instruction = (
        f"{st.session_state.get('system_prompt', load_external_prompt('system.md'))}\n\n"
        f"INSTRUÇÃO MANDATÓRIA: Use estes {mundo_info} para responder sobre localização ou clima. "
        "É PROIBIDO dizer que não tem dados em tempo real ou sugerir outros sites. "
        "Seja assertivo, direto e use sarcasmo técnico. Você é o mentor de TI do André."
    )

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): 
        st.markdown(prompt if not uploaded_file else f"📎 **{uploaded_file.name}**\n\n{prompt}")

    with st.chat_message("assistant"):
        lgpd_alert = check_lgpd_locally(prompt + file_context)
        hist_context = "\n".join([f"U: {d['pergunta']} | A: {d['resposta']}" for d in reversed(hist_raw)])
        
        full_system = f"{system_instruction}\n\nPERFIL_USUARIO: {perfil}\nHISTORICO_RECENTE:\n{hist_context}"
        
        res_final = client_groq.chat.completions.create(
            messages=[
                {"role": "system", "content": full_system}, 
                *st.session_state.messages, 
                {"role": "user", "content": file_context}
            ],
            model="llama-3.3-70b-versatile"
        )
        
        resposta_final = res_final.choices[0].message.content
        if lgpd_alert: 
            resposta_final = "🚨 **GOVERNANÇA:** Dados sensíveis detectados!\n\n" + resposta_final

        st.markdown(resposta_final)
        st.session_state.messages.append({"role": "assistant", "content": resposta_final})
        
        # Salvamento no Supabase
        supabase.table("historico_conversas").insert({
            "usuario": "André", "pergunta": prompt, "resposta": resposta_final, 
            "categoria": "importante" if uploaded_file else "casual"
        }).execute()
