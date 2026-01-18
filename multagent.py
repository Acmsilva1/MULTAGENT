import streamlit as st
import pandas as pd
from groq import Groq
from supabase import create_client, Client
from PyPDF2 import PdfReader
import io
import os

# --- CONFIGURAÇÕES DE AMBIENTE ---
st.set_page_config(page_title="Agente Pessoal", layout="wide")

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("Erro nas APIs. Verifique os Secrets.")
    st.stop()

# --- CARREGAMENTO DO SYSTEM PROMPT EXTERNO ---
def carregar_system_md():
    try:
        with open("system.md", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Responda de forma técnica e direta. Wikipédia Style."

def definir_comportamento(query):
    gatilhos_mentor = ["ensinar", "educar", "instruir", "explicar"]
    if any(g in query.lower() for g in gatilhos_mentor):
        return carregar_system_md()
    return "Aja como Wikipédia/Google. Resposta direta, com sarcasmo, com analogias. Foco em fatos e LGPD."

# --- PROCESSAMENTO DE DADOS ---
def processar_arquivo(file):
    if file is None: return ""
    ext = file.name.split('.')[-1].lower()
    try:
        if ext == "csv":
            df = pd.read_csv(file, nrows=15)
            return f"Amostra CSV:\n{df.to_markdown()}"
        elif ext == "pdf":
            return "".join([p.extract_text() for p in PdfReader(file).pages[:3]])
        return file.getvalue().decode("utf-8")[:4000]
    except Exception as e: return f"Erro no arquivo: {e}"

# --- INTERFACE ---
with st.sidebar:
    st.header("⚙️ Configurações")
    if st.button("🗑️ Nova Conversa"):
        st.session_state.messages = []
        st.cache_data.clear()
        st.rerun()
    st.divider()
    doc = st.file_uploader("Upload (CSV, PDF, TXT)", type=["csv", "pdf", "txt"])

st.title("Agente Pessoal")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages[-4:]:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

# --- LOOP PRINCIPAL ---
if prompt := st.chat_input("Pergunte algo..."):
    sys_msg = definir_comportamento(prompt)
    contexto_arquivo = processar_arquivo(doc)
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            chat_completion = client_groq.chat.completions.create(
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": f"Contexto: {contexto_arquivo}\n\nPergunta: {prompt}"}
                ],
                model="llama-3.1-8b-instant",
                temperature=0.3
            )
            resposta = chat_completion.choices[0].message.content
            st.markdown(resposta)
            st.session_state.messages.append({"role": "assistant", "content": resposta})

            # Log para auditoria
            supabase.table("historico_conversas").insert({
                "usuario": "André", "pergunta": prompt, "resposta": resposta, "origem": "Git_System_MD"
            }).execute()
        except Exception as e:
            st.error(f"Erro na Groq: {e}")
