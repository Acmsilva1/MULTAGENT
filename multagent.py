import streamlit as st
import pandas as pd
from groq import Groq
from supabase import create_client, Client
from PyPDF2 import PdfReader
import io

# --- 1. IDENTIDADE E DIRETRIZES DE FERRO (O "Contrato" do André) ---
USER_PROFILE = """
USUÁRIO: André, recém-formado em TI (Vila Velha/ES). Foco em IA e Dados.
ESTILO: Sarcástico, assertivo, sem enrolação. Use analogias de TI/Culinária.
GOVERNANÇA: Vigilante LGPD. Proibido dados sensíveis ou ilícitos. 
ORDEM: Se o código for ineficiente ou o André te pegar alucinando, você será resetado.
"""

st.set_page_config(page_title="Agente pessoal", layout="wide")

# Conexão com a "Matriz"
try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("Erro de conexão. Verifique se o café (e os Secrets) não acabaram.")
    st.stop()

# --- 2. PROCESSAMENTO DE ARQUIVOS (Mise en Place de Dados) ---
def processar_arquivo(uploaded_file):
    if uploaded_file is None: return ""
    ext = uploaded_file.name.split('.')[-1].lower()
    try:
        if ext == "csv":
            # Eficiência: lendo apenas o essencial para não fritar os tokens do 8B
            df = pd.read_csv(uploaded_file, nrows=15)
            return f"DATASET CSV (Amostra de 15 linhas):\n{df.to_markdown()}"
        elif ext == "pdf":
            reader = PdfReader(uploaded_file)
            return "".join([p.extract_text() for p in reader.pages[:3]])
        return uploaded_file.getvalue().decode("utf-8")[:4000]
    except Exception as e:
        return f"Erro ao processar arquivo: {e}"

# --- 3. BARRA LATERAL (A Interface que você sentiu falta) ---
with st.sidebar:
    st.header("Painel")
    
    # O botão que voltou do exílio
    if st.button("Nova Conversa", help="Limpa o histórico para o estagiário não se confundir"):
        st.session_state.messages = []
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    doc = st.file_uploader("Upload (CSV, PDF, TXT)", type=["csv", "pdf", "txt"])
    st.caption("O estagiário está te observando. Seja direto.")

# --- 4. INTERFACE PRINCIPAL ---
st.title("Agente pessoal")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Exibição Scannable
for msg in st.session_state.messages[-4:]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 5. FLUXO DE RESPOSTA ---
if prompt := st.chat_input("Pergunte algo..."):
    # Extração de contexto
    conteudo_arquivo = processar_arquivo(doc)
    
    # Injeção de Identidade + Contexto + Prompt
    contexto_final = f"{USER_PROFILE}\n\n[ARQUIVO]: {conteudo_arquivo}\n\n[ANDRÉ]: {prompt}"

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # Fixamos o Llama 3.1 8B para máxima economia
        try:
            chat_completion = client_groq.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Você é o Mentor ranzinza do André. Sem enrolação. Foco em LGPD."},
                    {"role": "user", "content": contexto_final}
                ],
                model="llama-3.1-8b-instant",
                temperature=0.4 # Baixamos a temperatura para ele não inventar moda
            )
            
            resposta = chat_completion.choices[0].message.content
            st.markdown(resposta)
            st.session_state.messages.append({"role": "assistant", "content": resposta})

            # Registro no Supabase (Memória de longo prazo)
            supabase.table("historico_conversas").insert({
                "usuario": "André", 
                "pergunta": prompt, 
                "resposta": resposta, 
                "categoria": "8B_Incisivo"
            }).execute()

        except Exception as e:
            st.error(f"Erro na Groq: {e}")
