import streamlit as st
from groq import Groq
from supabase import create_client, Client
import pandas as pd
import io

# --- 1. CONEXÕES (MANTIDAS) ---
try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro de conexão: {e}")
    st.stop()

# --- 2. PERSONALIDADE (MANTIDA) ---
BASE_SYSTEM_PROMPT = """
Você é o 'Sênior Ácido', mentor de TI. Use o histórico e os arquivos enviados para dar respostas técnicas, sarcásticas e precisas.
Foco: IA, Dados e LGPD. Se o arquivo contiver dados sensíveis, avise o André imediatamente!
"""

# --- 3. INTERFACE ---
st.set_page_config(page_title="Agente Pessoal v3.0", page_icon="🤖")
st.title("Agente Pessoal")
st.caption("Memória Ativa + Analisador de Arquivos | Llama 3.3")

# --- 4. ÁREA DE UPLOAD (A NOVIDADE) ---
with st.sidebar:
    st.header("🗂️ Arquivos do André")
    arquivo_subido = st.file_uploader("Suba um arquivo para análise (.txt, .py, .csv)", type=["txt", "py", "csv", "log"])
    
    conteudo_arquivo = ""
    if arquivo_subido is not None:
        try:
            if arquivo_subido.name.endswith(".csv"):
                df = pd.read_csv(arquivo_subido)
                conteudo_arquivo = f"\n[CONTEÚDO DO CSV '{arquivo_subido.name}']:\n{df.head(10).to_string()}"
                st.success("CSV carregado (mostrando 10 primeiras linhas).")
            else:
                stringio = io.StringIO(arquivo_subido.getvalue().decode("utf-8"))
                conteudo_arquivo = f"\n[CONTEÚDO DO ARQUIVO '{arquivo_subido.name}']:\n{stringio.read()}"
                st.success("Texto/Script carregado!")
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")

    st.divider()
    if st.button("Limpar Histórico Visual"):
        st.session_state.messages = []
        st.rerun()

# --- 5. CHAT E LÓGICA ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("O que vamos analisar hoje?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Processando dados e memórias...", expanded=False) as status:
            try:
                # Busca memória no Supabase
                res = supabase.table("memoria_agente").select("pergunta, resposta").eq("usuario", "André").order("created_at", desc=True).limit(3).execute()
                memorias = "\n".join([f"U: {d['pergunta']} | A: {d['resposta']}" for d in res.data]) if res.data else ""
                
                # Monta o Prompt com Memória + Arquivo
                prompt_final = f"{BASE_SYSTEM_PROMPT}\n\nMEMÓRIA:\n{memorias}\n\n{conteudo_arquivo}"
                
                chat_completion = client_groq.chat.completions.create(
                    messages=[
                        {"role": "system", "content": prompt_final},
                        *st.session_state.messages 
                    ],
                    model="llama-3.3-70b-versatile",
                    temperature=0.7,
                )
                resposta = chat_completion.choices[0].message.content
                
                # Grava no banco
                supabase.table("memoria_agente").insert({"pergunta": prompt, "resposta": resposta, "usuario": "André"}).execute()
                status.update(label="Análise concluída!", state="complete")
                
            except Exception as e:
                resposta = f"Bug no sistema! {e}"
                status.update(label="Erro!", state="error")

        st.markdown(resposta)
        st.session_state.messages.append({"role": "assistant", "content": resposta})
