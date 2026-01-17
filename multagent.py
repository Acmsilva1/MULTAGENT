import streamlit as st
from groq import Groq
from supabase import create_client, Client
import json
import os

# --- 1. CONFIGURAÇÃO E GOVERNANÇA ---
st.set_page_config(page_title="Agente Pessoal", layout="centered")

@st.cache_data
def load_external_prompt(file_name: str) -> str:
    """
    Carrega o prompt do GitHub/Disco com cache para performance.
    Governança: Centraliza as instruções do sistema fora do código principal.
    """
    path = os.path.join("prompts", file_name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return "Você é um assistente de TI. (Erro técnico: Prompt Master não encontrado)."

# Carregamento Seguro (Lazy Loading com Cache)
if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = load_external_prompt("system.md")

# Inicialização de APIs (Mantenha seu bloco Try/Except atual)
try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro na conexão técnica: {e}")
    st.stop()

# --- 2. LOGICA DE SEGURANÇA (LGPD PRE-FLIGHT) ---
def check_lgpd_locally(text: str) -> bool:
    """
    Simulação de busca por dados sensíveis antes de enviar para a API.
    Analogia: Passar o detector de metais antes de entrar no cofre.
    """
    # Exemplo simples de Regex para CPF ou E-mail (Pode ser expandido com Presidio)
    import re
    sensitive_patterns = [
        r'\d{3}\.\d{3}\.\d{3}-\d{2}', # CPF
        r'[\w\.-]+@[\w\.-]+\.\w+'      # Email
    ]
    return any(re.search(p, text) for p in sensitive_patterns)

# --- 3. INTEGRAÇÃO NO FLUXO ---
# (Substitua a parte do loop de chat por esta lógica otimizada)

if prompt := st.chat_input("Diga algo ao seu Agente Pessoal..."):
    # Validação Local de Governança
    lgpd_warning = ""
    if check_lgpd_locally(prompt):
        lgpd_warning = "🚨 **LGPD ALERT:** Detectei possíveis dados sensíveis no seu input! "
    
    # ... (Seu código de contexto de arquivo continua aqui) ...

    with st.chat_message("assistant"):
        perfil, hist_raw = carregar_dados()
        
        # Otimização: O System Prompt agora vem do st.session_state (carregado do MD)
        hist_context = "\n".join([f"U: {d['pergunta']} | A: {d['resposta']}" for d in hist_raw])
        full_system = f"{st.session_state.system_prompt}\n\nPERFIL: {perfil}\nHISTÓRICO: {hist_context}"
        
        # Chamada da API (Llama 3.3)
        # ... (restante do seu código de chat completions) ...
        
        # Se houve risco local, anexa o aviso à resposta final
        if lgpd_warning:
            resposta_final = lgpd_warning + "\n\n" + res_final.choices[0].message.content
        else:
            resposta_final = res_final.choices[0].message.content

        st.markdown(resposta_final)
