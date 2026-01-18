import streamlit as st
import pandas as pd
from groq import Groq
from supabase import create_client, Client
from PyPDF2 import PdfReader
import io

# --- 1. IDENTIDADE E DIRETRIZES DE FERRO ---
USER_PROFILE = """
VOCÊ É O MENTOR DO ANDRÉ (Recém-formado TI, Vila Velha/ES).
REGRAS:
1. Sarcasmo assertivo, sem enrolação. 
2. Foco total em LGPD e Governança de Dados.
3. Se o código for ineficiente (ex: ler CSV sem chunks), você será penalizado.
4. Identidade: Você é brilhante, ranzinza e direto ao ponto.
"""

st.set_page_config(page_title="Agente pessoal", layout="wide")

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("Erro de conexão.")
    st.stop()

# --- 2. PROCESSAMENTO DE ARQUIVOS (Eficiência Máxima) ---
def processar_arquivo(uploaded_file):
    if uploaded_file is None: return ""
    ext = uploaded_file.name.split('.')[-1].lower()
    try:
        if ext == "csv":
            # Estagiário agora é obrigado a ser eficiente: lê só o cabeçalho/amostra
            df = pd.read_csv(uploaded_file, nrows=15)
            return f"DATASET CSV (Amostra):\n{df.to_markdown()}"
        elif ext == "pdf":
            reader = PdfReader(uploaded_file)
            return "".join([p.extract_text() for p in reader.pages[:3]])
        return uploaded_file.getvalue().decode("utf-8")[:4000]
    except: return "Erro no processamento do arquivo."

# --- 3. INTERFACE ---
with st.sidebar:
    st.header("⚙️ Controle do Estagiário")
    doc = st.file_uploader("Upload (CSV, PDF, TXT)", type=["csv", "pdf", "txt"])
    if st.button("Resetar Memória"):
        st.session_state.messages = []; st.rerun()

st.title("Agente pessoal")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages[-4:]:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

# --- 4. FLUXO DE TRABALHO ---
if prompt := st.chat_input("Pergunte algo..."):
    conteudo_arquivo = processar_arquivo(doc)
    contexto_final = f"{USER_PROFILE}\n\n[CONTEXTO]: {conteudo_arquivo}\n\n[USER]: {prompt}"

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        # Forçamos o modelo 8B para economia total
        try:
            res = client_groq.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Você é o Mentor ranzinza. Seja incisivo e técnico."},
                    {"role": "user", "content": contexto_final}
                ],
                model="llama-3.1-8b-instant",
                temperature=0.5 # Menos criatividade, mais precisão técnica
            )
            resposta = res.choices[0].message.content
            st.markdown(resposta)
            st.session_state.messages.append({"role": "assistant", "content": resposta})

            # Log simplificado
            supabase.table("historico_conversas").insert({
                "usuario": "André", "pergunta": prompt, "resposta": resposta, "categoria": "Bootcamp_8B"
            }).execute()
        except Exception as e:
            st.error(f"Erro: {e}")
