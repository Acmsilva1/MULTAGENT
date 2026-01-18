import streamlit as st
from groq import Groq
from supabase import create_client, Client
from PyPDF2 import PdfReader
import os

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Agente André 1.0 Turbo", layout="centered")

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("Erro de conexão. Verifique os Secrets.")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("Configurações")
    if st.button("Nova Conversa"):
        st.session_state.messages = []
        st.rerun()
    uploaded_file = st.file_uploader("Subir Doc (TXT/PDF)", type=["pdf", "txt"])

# --- LÓGICA DE CHAT ---
st.title("Agente Pessoal 🤖")
if "messages" not in st.session_state: st.session_state.messages = []

for msg in st.session_state.messages[-6:]: # Mantém só as últimas 6 visíveis
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

if prompt := st.chat_input("Fale comigo..."):
    # 1. Preparar contexto de arquivo (Limitado a 4000 caracteres para segurança total)
    file_context = ""
    if uploaded_file:
        if ".pdf" in uploaded_file.name:
            reader = PdfReader(uploaded_file)
            raw = "".join([p.extract_text() for p in reader.pages[:2]]) # Apenas 2 páginas
        else:
            raw = uploaded_file.getvalue().decode()
        file_context = f"\n[CONTEXTO ARQUIVO]: {raw[:4000]}"

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        # 2. Puxar apenas o essencial do histórico
        hist = supabase.table("historico_conversas").select("pergunta, resposta").eq("usuario", "André").order("created_at", desc=True).limit(2).execute().data
        hist_context = "\n".join([f"U:{h['pergunta']}|A:{h['resposta']}" for h in reversed(hist)])
        
        system_msg = f"Você é o mentor de TI do André. Sarcástico e direto. Histórico: {hist_context}"

        try:
            # AQUI ESTÁ A MÁGICA DO MODELO MENOR
            res = client_groq.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"{file_context}\n\nPergunta: {prompt}"}
                ],
                model="llama-3.1-8b-instant" # <--- O MODELO QUE DURA MAIS
            )
            
            resposta = res.choices[0].message.content
            st.markdown(resposta)
            st.session_state.messages.append({"role": "assistant", "content": resposta})
            
            # Salvar no Banco
            supabase.table("historico_conversas").insert({
                "usuario": "André", "pergunta": prompt, "resposta": resposta, "categoria": "casual"
            }).execute()
        except Exception as e:
            st.error(f"Esgotou até o modelo 8B! Aguarde um pouco. Erro: {e}")
