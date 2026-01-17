import streamlit as st
from groq import Groq
from supabase import create_client, Client
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
        return "Você é um assistente de TI sênior."

if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = load_external_prompt("system.md")

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro de conexão: {e}")
    st.stop()

# --- 2. FUNÇÕES DE DADOS (FAST MODE) ---

def carregar_dados_simples():
    try:
        perfil = supabase.table("perfil_usuario").select("*").eq("usuario", "André").single().execute().data
        # Trazemos as últimas 5 para contexto
        hist = supabase.table("historico_conversas").select("pergunta, resposta").eq("usuario", "André").order("created_at", desc=True).limit(5).execute().data
        return perfil, hist
    except:
        return {}, []

def check_lgpd_locally(text: str) -> bool:
    patterns = [r'\d{3}\.\d{3}\.\d{3}-\d{2}', r'[\w\.-]+@[\w\.-]+\.\w+']
    return any(re.search(p, text) for p in patterns)

# --- 3. BARRA LATERAL (O QUE TINHA SUMIDO) ---
with st.sidebar:
    st.header("Painel de Controle")
    
    if st.button("Nova Conversa", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.divider()
    
    # Reativando o uploader de arquivos
    uploaded_file = st.file_uploader("Subir contexto (Scripts/Docs)", type=["txt", "py", "csv", "json"])
    
    if st.button("Limpar Histórico Casual", use_container_width=True):
        try:
            supabase.table("historico_conversas").delete().eq("usuario", "André").eq("categoria", "casual").execute()
            st.success("Lixo casual removido!")
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
if prompt := st.chat_input("Diga algo..."):
    lgpd_risk = check_lgpd_locally(prompt)
    
    # Processamento de Arquivo
    file_context = ""
    if uploaded_file:
        raw_content = uploaded_file.getvalue().decode("utf-8")
        file_context = f"\n\n[DADOS DO ARQUIVO]:\n{raw_content}"
        lgpd_risk = lgpd_risk or check_lgpd_locally(raw_content)

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): 
        st.markdown(prompt if not uploaded_file else f"📎 **{uploaded_file.name}**\n\n{prompt}")

    with st.chat_message("assistant"):
        perfil, hist_raw = carregar_dados_simples()
        
        # Invertemos para que a ordem cronológica no prompt faça sentido
        hist_context = "\n".join([f"U: {d['pergunta']} | A: {d['resposta']}" for d in reversed(hist_raw)])
        
        full_system = f"{st.session_state.system_prompt}\n\nPERFIL: {perfil}\nHISTÓRICO RECENTE:\n{hist_context}"
        
        res_final = client_groq.chat.completions.create(
            messages=[{"role": "system", "content": full_system}, *st.session_state.messages, {"role": "user", "content": file_context}],
            model="llama-3.3-70b-versatile"
        )
        
        resposta_final = res_final.choices[0].message.content
        if lgpd_risk:
            resposta_final = "🚨 **LGPD ALERT:** Possíveis dados sensíveis detectados!\n\n" + resposta_final

        st.markdown(resposta_final)
        st.session_state.messages.append({"role": "assistant", "content": resposta_final})
        
        # Salvamento rápido
        supabase.table("historico_conversas").insert({
            "usuario": "André", 
            "pergunta": prompt, 
            "resposta": resposta_final, 
            "categoria": "importante" if uploaded_file else "casual"
        }).execute()
