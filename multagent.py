import streamlit as st
from groq import Groq
from supabase import create_client, Client
import json
import os
import re

# --- 1. CONFIGURAÇÃO (CACHE LEVE) ---
st.set_page_config(page_title="Agente Pessoal", layout="centered")

@st.cache_data
def load_external_prompt(file_name: str) -> str:
    """Carrega o cérebro do MD. Isso é rápido e não pesa."""
    path = os.path.join("prompts", file_name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "Você é um assistente de TI sênior."

if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = load_external_prompt("system.md")

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro de conexão: {e}")
    st.stop()

# --- 2. FUNÇÕES DE DADOS (SEM VETORES = SEM LENTIDÃO) ---

def carregar_dados_simples():
    """Busca apenas o essencial: quem é você e o que conversamos por último."""
    try:
        perfil = supabase.table("perfil_usuario").select("*").eq("usuario", "André").single().execute().data
        # Voltamos para o limite de 5, ordenado por data (suave e rápido)
        hist = supabase.table("historico_conversas").select("pergunta, resposta").eq("usuario", "André").order("created_at", desc=True).limit(5).execute().data
        return perfil, hist
    except:
        return {}, []

def check_lgpd_locally(text: str) -> bool:
    patterns = [r'\d{3}\.\d{3}\.\d.3}-\d{2}', r'[\w\.-]+@[\w\.-]+\.\w+']
    return any(re.search(p, text) for p in patterns)

# --- 3. INTERFACE ---
st.title("Agente Pessoal 🤖")
if "messages" not in st.session_state: st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

# --- 4. FLUXO EXECUTIVO ---
if prompt := st.chat_input("Diga algo rápido..."):
    lgpd_risk = check_lgpd_locally(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        # Acesso direto ao banco (Sem cálculo de vetor)
        perfil, hist_raw = carregar_dados_simples()
        
        hist_context = "\n".join([f"U: {d['pergunta']} | A: {d['resposta']}" for d in reversed(hist_raw)])
        full_system = f"{st.session_state.system_prompt}\n\nPERFIL: {perfil}\nHISTÓRICO RECENTE:\n{hist_context}"
        
        res_final = client_groq.chat.completions.create(
            messages=[{"role": "system", "content": full_system}, *st.session_state.messages],
            model="llama-3.3-70b-versatile"
        )
        
        resposta_final = res_final.choices[0].message.content
        if lgpd_risk: resposta_final = "🚨 **LGPD ALERT!**\n\n" + resposta_final

        st.markdown(resposta_final)
        st.session_state.messages.append({"role": "assistant", "content": resposta_final})
        
        # Salvamento simples (Rápido como um flash)
        supabase.table("historico_conversas").insert({
            "usuario": "André", "pergunta": prompt, "resposta": resposta_final, "categoria": "importante"
        }).execute()
