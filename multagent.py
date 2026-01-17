import streamlit as st
from groq import Groq
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer # Biblioteca local e estável
import json
import os
import re

# --- 1. CONFIGURAÇÃO E CACHE ---
st.set_page_config(page_title="Agente Pessoal", layout="centered")

@st.cache_resource # Usamos resource para modelos pesados
def load_embedding_model():
    """Carrega o modelo de tradução de vetores localmente."""
    return SentenceTransformer('all-MiniLM-L6-v2')

@st.cache_data
def load_external_prompt(file_name: str) -> str:
    path = os.path.join("prompts", file_name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "Você é um assistente de TI."

# Inicialização
model_embedding = load_embedding_model()

if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = load_external_prompt("system.md")

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro técnico: {e}")
    st.stop()

# --- 2. FUNÇÕES (A COZINHA) ---

def gerar_embedding(texto: str):
    """Transforma texto em vetor localmente, sem erro de API."""
    embedding = model_embedding.encode(texto)
    return embedding.tolist() # Converte para lista que o Supabase entende

def carregar_contexto_semantico(pergunta_usuario: str):
    """Busca no Supabase usando o comando SQL que você já rodou."""
    try:
        vetor_pergunta = gerar_embedding(pergunta_usuario)
        rpc_res = supabase.rpc(
            'match_conversas', 
            {'query_embedding': vetor_pergunta, 'match_threshold': 0.4, 'match_count': 5}
        ).execute()
        return rpc_res.data
    except Exception as e:
        return []

def check_lgpd_locally(text: str) -> bool:
    sensitive_patterns = [r'\d{3}\.\d{3}\.\d{3}-\d{2}', r'[\w\.-]+@[\w\.-]+\.\w+']
    return any(re.search(p, text) for p in sensitive_patterns)

# --- 3. INTERFACE E EXECUÇÃO ---
st.title("Agente Pessoal 🤖")

if prompt := st.chat_input("Diga algo..."):
    lgpd_risk = check_lgpd_locally(prompt)
    st.session_state.messages = st.session_state.get("messages", [])
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        # Agora a busca funciona sem erro de NotFound!
        contexto_rico = carregar_contexto_semantico(prompt)
        hist_context = "\n".join([f"P: {c['pergunta']} | R: {c['resposta']}" for c in contexto_rico])
        
        full_system = f"{st.session_state.system_prompt}\n\nCONHECIMENTO RECUPERADO:\n{hist_context}"
        
        res_final = client_groq.chat.completions.create(
            messages=[{"role": "system", "content": full_system}, *st.session_state.messages],
            model="llama-3.3-70b-versatile"
        )
        
        resposta_final = res_final.choices[0].message.content
        if lgpd_risk: resposta_final = "🚨 **LGPD ALERT!**\n\n" + resposta_final
        
        st.markdown(resposta_final)
        st.session_state.messages.append({"role": "assistant", "content": resposta_final})
        
        # Salva com o embedding gerado localmente
        novo_vetor = gerar_embedding(prompt + " " + resposta_final)
        supabase.table("historico_conversas").insert({
            "usuario": "André", "pergunta": prompt, "resposta": resposta_final, 
            "categoria": "importante", "embedding": novo_vetor
        }).execute()
