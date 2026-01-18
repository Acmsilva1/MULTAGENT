import streamlit as st
from groq import Groq
from supabase import create_client, Client
from PyPDF2 import PdfReader
import requests
import os
import re

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Agente Pessoal do André", layout="centered")

@st.cache_data
def load_external_prompt(file_name: str) -> str:
    path = os.path.join("prompts", file_name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Você é um mentor de TI sênior, assertivo e sarcástico."

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro Crítico: {e}")
    st.stop()

# --- FERRAMENTAS ---

def buscar_contexto_mundo():
    """Captura localização e clima reais via IP e Open-Meteo."""
    try:
        geo = requests.get("http://ip-api.com/json/", timeout=5).json()
        cidade = geo.get("city", "Vila Velha")
        lat, lon = geo.get("lat", -20.32), geo.get("lon", -40.29)
        
        w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        clima = requests.get(w_url, timeout=5).json()
        temp = clima["current_weather"]["temperature"]
        return f"DADOS REAIS: Localização {cidade}, Temperatura {temp}°C."
    except:
        return "DADOS REAIS: Indisponíveis (André, cheque sua conexão)."

def extrair_texto_pdf(file):
    try:
        reader = PdfReader(file)
        return "".join([p.extract_text() for p in reader.pages[:15]])
    except:
        return "Erro na extração do PDF."

def check_lgpd(text: str) -> bool:
    patterns = [r'\d{3}\.\d{3}\.\d{3}-\d{2}', r'[\w\.-]+@[\w\.-]+\.\w+']
    return any(re.search(p, text) for p in patterns)

# --- INTERFACE ---
st.title("Agente Pessoal 🤖")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

# --- PROCESSO PRINCIPAL ---
if prompt := st.chat_input("Diga algo ao seu Agente..."):
    # 1. Dados de Contexto
    mundo_info = buscar_contexto_mundo()
    perfil = supabase.table("perfil_usuario").select("*").eq("usuario", "André").single().execute().data or {}
    
    # 2. Tratamento de Arquivos
    file_context = ""
    uploaded_file = st.sidebar.file_uploader("Upload", type=["pdf", "txt"])
    if uploaded_file:
        content = extrair_texto_pdf(uploaded_file) if ".pdf" in uploaded_file.name else uploaded_file.getvalue().decode()
        file_context = f"\n\n[ARQUIVO]: {content[:20000]}"

    # 3. CONSTRUÇÃO DA PERSONA (O BLOQUEIO DE 'SABONETADA')
    # Forçamos o modelo a aceitar que o mundo real é o que enviamos.
    system_instruction = (
        f"{load_external_prompt('system.md')}\n\n"
        f"VOCÊ ESTÁ OPERANDO COM ESTES DADOS EM TEMPO REAL: {mundo_info}.\n"
        "É PROIBIDO dizer que não tem acesso ao clima ou localização.\n"
        "É PROIBIDO sugerir sites externos (INMET, prefeitura, etc).\n"
        "Responda diretamente: 'André, aqui em [Cidade] faz [Temp] graus'.\n"
        "Mantenha o sarcasmo técnico e a assertividade."
    )

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        lgpd_alert = check_lgpd(prompt + file_context)
        
        res = client_groq.chat.completions.create(
            messages=[
                {"role": "system", "content": system_instruction},
                *st.session_state.messages,
                {"role": "user", "content": file_context}
            ],
            model="llama-3.3-70b-versatile"
        )
        
        full_res = res.choices[0].message.content
        if lgpd_alert: full_res = "🚨 **GOVERNANÇA:** Dados sensíveis detectados!\n\n" + full_res
        
        st.markdown(full_res)
        st.session_state.messages.append({"role": "assistant", "content": full_res})
        
        # Log no Supabase
        supabase.table("historico_conversas").insert({
            "usuario": "André", "pergunta": prompt, "resposta": full_res, "categoria": "casual"
        }).execute()
