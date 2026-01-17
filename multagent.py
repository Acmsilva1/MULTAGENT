import streamlit as st
from groq import Groq
from supabase import create_client, Client
import json
import os
import re

# --- 1. CONFIGURAÇÃO DE AMBIENTE E CACHE ---
st.set_page_config(page_title="Agente Pessoal", layout="centered")

@st.cache_data
def load_external_prompt(file_name: str) -> str:
    """Carrega o cérebro (prompt) do MD no GitHub com cache."""
    path = os.path.join("prompts", file_name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "Você é um assistente de TI. (Erro: system.md não encontrado)."

# Inicializa o prompt no estado da sessão
if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = load_external_prompt("system.md")

# Conexões Técnicas
try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro na conexão técnica: {e}")
    st.stop()

# --- 2. DEFINIÇÃO DE FUNÇÕES (A COZINHA) ---
# Definir ANTES de chamar lá embaixo para evitar o NameError

def check_lgpd_locally(text: str) -> bool:
    """Busca padrões de dados sensíveis localmente."""
    sensitive_patterns = [r'\d{3}\.\d{3}\.\d{3}-\d{2}', r'[\w\.-]+@[\w\.-]+\.\w+']
    return any(re.search(p, text) for p in sensitive_patterns)

def carregar_dados():
    """Busca perfil e histórico no Supabase."""
    try:
        perfil = supabase.table("perfil_usuario").select("*").eq("usuario", "André").single().execute().data
        hist = supabase.table("historico_conversas").select("pergunta, resposta").eq("usuario", "André").order("created_at", desc=True).limit(3).execute().data
        return perfil, hist
    except: 
        return {}, []

def deletar_casuais():
    """Limpeza de dados não importantes."""
    try:
        supabase.table("historico_conversas").delete().eq("usuario", "André").eq("categoria", "casual").execute()
        st.sidebar.success("Histórico apagado!")
    except Exception as e:
        st.sidebar.error(f"Erro: {e}")

# --- 3. SIDEBAR E INTERFACE ---
with st.sidebar:
    st.header("Painel de Controle")
    if st.button("Nova conversa", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.divider()
    uploaded_file = st.file_uploader("Scripts ou dados", type=["txt", "py", "csv", "json"])
    
    if st.button("Limpar Histórico Casual", use_container_width=True):
        deletar_casuais()
        st.rerun()

st.title("Agente Pessoal 🤖")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): 
        st.markdown(msg["content"])

# --- 4. FLUXO DE EXECUÇÃO (O PROCESSO) ---
if prompt := st.chat_input("Diga algo ao seu Agente..."):
    # Validação Local
    lgpd_risk = check_lgpd_locally(prompt)
    
    # Contexto de Arquivo
    file_context = ""
    if uploaded_file:
        raw_content = uploaded_file.getvalue().decode("utf-8")
        file_context = f"\n\n[DADOS DO ARQUIVO]:\n{raw_content}"
        lgpd_risk = lgpd_risk or check_lgpd_locally(raw_content)

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): 
        st.markdown(prompt if not uploaded_file else f"📎 **{uploaded_file.name}**\n\n{prompt}")

    with st.chat_message("assistant"):
        # Agora o Python sabe exatamente onde está essa função!
        perfil, hist_raw = carregar_dados()
        
        # 1. Classificação (Prompt interno rápido)
        CLASSIFIER_PROMPT = 'Responda APENAS JSON: {"is_important": boolean, "lgpd_risk": boolean}'
        res_class = client_groq.chat.completions.create(
            messages=[{"role": "system", "content": CLASSIFIER_PROMPT}, {"role": "user", "content": prompt + file_context}],
            model="llama-3.3-70b-versatile", response_format={"type": "json_object"}
        )
        decisao = json.loads(res_class.choices[0].message.content)

        # 2. Resposta Final usando o MD do GitHub
        hist_context = "\n".join([f"U: {d['pergunta']} | A: {d['resposta']}" for d in hist_raw])
        full_system = f"{st.session_state.system_prompt}\n\nPERFIL: {perfil}\nHISTÓRICO: {hist_context}"
        
        res_final = client_groq.chat.completions.create(
            messages=[{"role": "system", "content": full_system}, *st.session_state.messages, {"role": "user", "content": file_context}],
            model="llama-3.3-70b-versatile"
        )
        
        resposta_final = res_final.choices[0].message.content
        
        # Alerta de Governança
        if lgpd_risk or decisao.get("lgpd_risk"):
            resposta_final = "🚨 **LGPD ALERT:** Cuidado com dados sensíveis!\n\n" + resposta_final

        st.markdown(resposta_final)
        st.session_state.messages.append({"role": "assistant", "content": resposta_final})
        
        # 3. Persistência
        is_imp = decisao.get("is_important") or uploaded_file is not None
        supabase.table("historico_conversas").insert({
            "usuario": "André", "pergunta": prompt, "resposta": resposta_final, 
            "categoria": "importante" if is_imp else "casual"
        }).execute()
