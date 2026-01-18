import streamlit as st
import pandas as pd
from groq import Groq
from supabase import create_client, Client
from PyPDF2 import PdfReader
import io

# --- 1. CONFIGURAÇÕES E IDENTIDADE (Fixa) ---
USER_PROFILE = """
USUÁRIO: André, profissional de TI (Vila Velha/ES), foco em IA e Dados.
ESTILO: Sarcástico, assertivo, sem enrolação. Use analogias de TI/Culinária.
GOVERNANÇA: Guardião LGPD. Proibido dados sensíveis ou ilícitos.
"""

st.set_page_config(page_title="Agente pessoal", layout="wide")

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("Erro de conexão. Verifique os Secrets.")
    st.stop()

# --- 2. ROTEAMENTO (Agora com foco em Dados) ---
def rotear_modelo(prompt, tem_arquivo, extensao=""):
    # Se tem arquivo (especialmente CSV/PDF), o Sênior ASSUME o controle
    if tem_arquivo or any(t in prompt.lower() for t in ['arquitetura', 'sql', 'lgpd', 'csv', 'iot', 'performance']):
        return "llama-3.3-70b-versatile", "Sênior (Expert em Dados)"
    return "llama-3.1-8b-instant", "Estagiário (Econômico)"

# --- 3. PROCESSAMENTO MULTI-ARQUIVO ---
def processar_arquivo(uploaded_file):
    if uploaded_file is None: return ""
    ext = uploaded_file.name.split('.')[-1].lower()
    
    try:
        if ext == "pdf":
            reader = PdfReader(uploaded_file)
            return "".join([p.extract_text() for p in reader.pages[:3]])
        
        elif ext == "csv":
            # Lógica de Sênior: Lemos apenas as primeiras 20 linhas para o prompt
            # Isso evita travar o modelo e permite análise de LGPD/Estrutura
            df = pd.read_csv(uploaded_file, nrows=20)
            buffer = io.StringIO()
            df.to_markdown(buffer) # Markdown é melhor para o modelo entender tabelas
            return f"ESTRUTURA DO CSV (Amostra):\n{buffer.getvalue()}"
            
        else: # TXT e outros
            return uploaded_file.getvalue().decode("utf-8")[:5000]
    except Exception as e:
        return f"Erro ao processar {ext}: {e}"

# --- 4. INTERFACE ---
with st.sidebar:
    st.header("⚙️ Configurações")
    # Adicionamos CSV aqui:
    doc = st.file_uploader("Upload de Contexto", type=["pdf", "txt", "csv"])
    if st.button("Limpar Chat"):
        st.session_state.messages = []; st.rerun()

st.title("Senior")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Exibe histórico
for msg in st.session_state.messages[-4:]:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

# --- 5. EXECUÇÃO ---
if prompt := st.chat_input("Pergunte algo..."):
    # Roteamento
    modelo_id, modelo_nome = rotear_modelo(prompt, doc is not None)
    
    # Extração de Conteúdo
    texto_doc = processar_arquivo(doc)
    contexto_final = f"{USER_PROFILE}\n\n[CONTEXTO ARQUIVO]:\n{texto_doc}\n\nPergunta: {prompt}"

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        st.caption(f"🚀 Ativado: {modelo_nome}")
        
        # System Prompt com histórico (Supabase)
        try:
            hist = supabase.table("historico_conversas").select("pergunta, resposta").eq("usuario", "André").limit(1).execute().data
            hist_context = f"Última: U:{hist[0]['pergunta']}|A:{hist[0]['resposta']}" if hist else ""
        except: hist_context = ""

        system_msg = f"Você é o Mentor Sênior do André. Priorize LGPD e técnica. {hist_context}"

        try:
            res = client_groq.chat.completions.create(
                messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": contexto_final}],
                model=modelo_id
            )
            resposta = res.choices[0].message.content
            st.markdown(resposta)
            st.session_state.messages.append({"role": "assistant", "content": resposta})
            
            # Log
            supabase.table("historico_conversas").insert({
                "usuario": "André", "pergunta": prompt, "resposta": resposta, "categoria": "CSV_Data_Analysis" if "csv" in str(doc) else "General"
            }).execute()
        except Exception as e:
            st.error(f"Erro: {e}")
