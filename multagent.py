import streamlit as st
from groq import Groq
from supabase import create_client, Client
from PyPDF2 import PdfReader
import os

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Agente pessoal", layout="centered")

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("Erro de conexão. Verifique os Secrets.")
    st.stop()

# --- LÓGICA DE ROTEAMENTO (Dicionário de Domínios) ---
def escolher_modelo(prompt, tem_arquivo):
    # 1. Arquivos SEMPRE acionam o Sênior (Governança LGPD)
    if tem_arquivo:
        return "llama-3.3-70b-versatile", "Sênior (Análise de Dados/LGPD)"
    
    # 2. Categorias de Alta Performance e Engenharia
    dominios_senior = {
        'industria_engenharia': ['turbina', 'jato', 'motor', 'propulsão', 'aerodinâmica', 'termodinâmica'],
        'iot_hardware': ['iot', 'sensores', 'telemetria', 'esp32', 'arduino', 'raspberry', 'protocolo'],
        'arquitetura_dados': ['sql', 'data lake', 'pipeline', 'migração', 'batch', 'etl', 'otimização'],
        'governanca_seguranca': ['lgpd', 'criptografia', 'segurança', 'pentest', 'anonimização', 'vulnerabilidade']
    }
    
    # Flatten para busca eficiente
    palavras_chave = [termo for sublist in dominios_senior.values() for termo in sublist]
    
    # Verificação de ativação
    if any(t in prompt.lower() for t in palavras_chave):
        return "llama-3.3-70b-versatile", "Sênior (Especialista Ativado)"
    
    # 3. Default Econômico
    return "llama-3.1-8b-instant", "Estagiário (Casual)"

# --- FUNÇÕES ---
def extrair_texto_pdf(file):
    try:
        reader = PdfReader(file)
        return "".join([p.extract_text() for p in reader.pages[:5]])
    except: return ""

# --- INTERFACE ---
with st.sidebar:
    st.header("Painel de Controle")
    if st.button("Nova Conversa"):
        st.session_state.messages = []
        st.rerun()
    uploaded_file = st.file_uploader("Contexto (PDF/TXT)", type=["pdf", "txt"])

st.title("Agente pessoal 🤖")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Exibe histórico curto para economizar tokens
for msg in st.session_state.messages[-4:]:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

if prompt := st.chat_input("Fale sobre turbinas, IoT ou LGPD..."):
    # Executa o Roteamento
    modelo_id, modelo_nome = escolher_modelo(prompt, uploaded_file is not None)
    
    file_context = ""
    if uploaded_file:
        raw = extrair_texto_pdf(uploaded_file) if ".pdf" in uploaded_file.name else uploaded_file.getvalue().decode()
        file_context = f"\n[ARQUIVO]: {raw[:5000]}"

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        st.caption(f"🧠 Modelo em uso: {modelo_nome}")
        
        # Injeção de System Prompt (Vindo do seu arquivo system.md via session_state ou carregamento)
        # Assumindo que você usa o conteúdo do system.md que revisamos
        system_msg = "Você é o Mentor Sênior do André. Priorize solução técnica antes do sarcasmo. Seja brutalmente honesto."

        try:
            res = client_groq.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"{file_context}\n\nPergunta: {prompt}"}
                ],
                model=modelo_id
            )
            
            resposta = res.choices[0].message.content
            st.markdown(resposta)
            st.session_state.messages.append({"role": "assistant", "content": resposta})
            
            # Registro de Log
            supabase.table("historico_conversas").insert({
                "usuario": "André", "pergunta": prompt, "resposta": resposta, "categoria": "orquestrado"
            }).execute()
            
        except Exception as e:
            st.error(f"Erro na orquestração: {e}")
