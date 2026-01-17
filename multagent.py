import streamlit as st
from groq import Groq
from supabase import create_client, Client
import json
import os
import re

# --- 1. CONFIGURAÇÃO E CACHE ---
st.set_page_config(page_title="Agente Pessoal - Memória Semântica", layout="centered")

@st.cache_data
def load_external_prompt(file_name: str) -> str:
    path = os.path.join("prompts", file_name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "Você é um assistente de TI. (Erro: system.md não encontrado)."

if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = load_external_prompt("system.md")

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro na conexão técnica: {e}")
    st.stop()

# --- 2. FUNÇÕES DE IA E DADOS (A COZINHA) ---

def gerar_embedding(texto: str):
    """Transforma texto em vetor usando a API da Groq."""
    # Usando o modelo de embedding da Groq (ex: distilbert ou similar disponível)
    # Nota: Verifique se seu plano suporta o modelo 'nomic-embed-text-v1.5' ou similar
    response = client_groq.embeddings.create(
        input=texto,
        model="nomic-embed-text-v1.5" 
    )
    return response.data[0].embedding

def carregar_contexto_semantico(pergunta_usuario: str):
    """Busca no Supabase o que é RELEVANTE, não apenas o que é RECENTE."""
    try:
        vetor_pergunta = gerar_embedding(pergunta_usuario)
        
        # Chama a função SQL (RPC) que criamos no Passo 1
        rpc_res = supabase.rpc(
            'match_conversas', 
            {
                'query_embedding': vetor_pergunta, 
                'match_threshold': 0.5, # Ajuste a sensibilidade aqui
                'match_count': 5        # Traz as 5 memórias mais pertinentes
            }
        ).execute()
        
        return rpc_res.data
    except Exception as e:
        st.error(f"Erro na busca semântica: {e}")
        return []

def check_lgpd_locally(text: str) -> bool:
    sensitive_patterns = [r'\d{3}\.\d{3}\.\d{3}-\d{2}', r'[\w\.-]+@[\w\.-]+\.\w+']
    return any(re.search(p, text) for p in sensitive_patterns)

# --- 3. INTERFACE ---
st.title("Agente Pessoal 🤖")
if "messages" not in st.session_state: st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

# --- 4. FLUXO DE EXECUÇÃO ---
if prompt := st.chat_input("Diga algo ao seu Agente..."):
    lgpd_risk = check_lgpd_locally(prompt)
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        # A MÁGICA: Em vez de carregar as últimas 3, ele busca o SENTIDO
        contexto_rico = carregar_contexto_semantico(prompt)
        
        # Monta o histórico baseado na relevância semântica
        hist_context = "\n".join([f"Antiga Conversa - P: {c['pergunta']} | R: {c['resposta']}" for c in contexto_rico])
        
        full_system = f"{st.session_state.system_prompt}\n\nCONHECIMENTO RECUPERADO:\n{hist_context}"
        
        # Chamada da Resposta Final
        res_final = client_groq.chat.completions.create(
            messages=[{"role": "system", "content": full_system}, *st.session_state.messages],
            model="llama-3.3-70b-versatile"
        )
        
        resposta_final = res_final.choices[0].message.content
        if lgpd_risk: resposta_final = "🚨 **LGPD ALERT!**\n\n" + resposta_final

        st.markdown(resposta_final)
        st.session_state.messages.append({"role": "assistant", "content": resposta_final})
        
        # SALVAMENTO COM EMBEDDING (Para futuras buscas)
        novo_vetor = gerar_embedding(prompt + " " + resposta_final)
        supabase.table("historico_conversas").insert({
            "usuario": "André", 
            "pergunta": prompt, 
            "resposta": resposta_final, 
            "categoria": "importante", # Agora tudo pode ser buscado semanticamente
            "embedding": novo_vetor
        }).execute()
