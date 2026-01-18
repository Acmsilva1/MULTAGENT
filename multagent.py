import streamlit as st
from groq import Groq
from supabase import create_client, Client
from PyPDF2 import PdfReader
import os
import re

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Agente Orquestrador André", layout="centered")

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("Erro de conexão. Verifique os Secrets.")
    st.stop()

# --- LÓGICA DE ROTEAMENTO (O CÉREBRO) ---
def escolher_modelo(prompt, tem_arquivo):
    # Se subiu arquivo, a LGPD exige o modelo mais inteligente (70B)
    if tem_arquivo:
        return "llama-3.3-70b-versatile", "Sênior (Análise de Doc)"
    
    # Termos que exigem raciocínio complexo ou governança
    termos_complexos = [
        'arquitetura', 'migração', 'sql', 'db', 'otimizar', 
        'lgpd', 'segurança', 'pipeline', 'infra', 'data lake'
    ]
    
    if any(t in prompt.lower() for t in termos_complexos):
        return "llama-3.3-70b-versatile", "Sênior (Complexidade)"
    
    # Para o resto, vamos de 8B economizar cota
    return "llama-3.1-8b-instant", "Estagiário Veloz (Casual)"

# --- FUNÇÕES AUXILIARES ---
def extrair_texto_pdf(file):
    try:
        reader = PdfReader(file)
        return "".join([p.extract_text() for p in reader.pages[:5]])
    except: return ""

# --- INTERFACE ---
with st.sidebar:
    st.header("Painel de Controle")
    if st.button("Nova Conversa"):
        st.session_state.messages = []
        st.rerun()
    uploaded_file = st.file_uploader("Upload de Contexto", type=["pdf", "txt"])

st.title("Agente Orquestrador 🤖")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages[-6:]:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

if prompt := st.chat_input("Mande sua dúvida técnica ou casual..."):
    # 1. Decisão de Roteamento
    modelo_id, modelo_nome = escolher_modelo(prompt, uploaded_file is not None)
    
    file_context = ""
    if uploaded_file:
        raw = extrair_texto_pdf(uploaded_file) if ".pdf" in uploaded_file.name else uploaded_file.getvalue().decode()
        file_context = f"\n[ARQUIVO]: {raw[:8000]}"

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        # Mostra qual modelo foi ativado (transparência de TI)
        st.caption(f"🚀 Ativado: {modelo_nome}")
        
        # Puxa histórico e perfil para o System Prompt
        hist = supabase.table("historico_conversas").select("pergunta, resposta").eq("usuario", "André").order("created_at", desc=True).limit(2).execute().data
        hist_context = "\n".join([f"U:{h['pergunta']}|A:{h['resposta']}" for h in reversed(hist)])
        
        # System Prompt v2.0 Turbo injetado
        system_msg = f"Você é o Mentor Sênior do André. Priorize solução técnica antes do sarcasmo. Contexto: {hist_context}"

        try:
            res = client_groq.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"{file_context}\n\nPergunta: {prompt}"}
                ],
                model=modelo_id
            )
            
            resposta = res.choices[0].message.content
            st.markdown(resposta)
            st.session_state.messages.append({"role": "assistant", "content": resposta})
            
            # Log no Supabase
            supabase.table("historico_conversas").insert({
                "usuario": "André", "pergunta": prompt, "resposta": resposta, 
                "categoria": "importante" if uploaded_file else "casual"
            }).execute()
            
        except Exception as e:
            st.error(f"Falha na orquestração: {e}")
