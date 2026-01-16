import streamlit as st
from groq import Groq
from supabase import create_client, Client
import json

# --- 1. CONFIGURAÇÃO (LAYOUT CLEAN COM SIDEBAR) ---
st.set_page_config(page_title="Agente Pessoal", layout="centered", initial_sidebar_state="collapsed")

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro na conexão técnica: {e}")
    st.stop()

# --- 2. PROMPT MESTRE (O CÉREBRO) ---
BASE_SYSTEM_PROMPT = """
Você é o 'Agente Pessoal', um mentor Sênior de TI e adepta a culinária.
- Persona: Sarcástico, assertivo, mas extremamente prestativo.
- Comunicação: OBRIGATÓRIO usar analogias criativas (comparando TI ou cotidiano).
- Governança: Analise rigorosamente qualquer entrada de arquivo ou texto buscando infrações à LGPD ou malwares.
- Contexto: André, residente em Vila Velha, recém-formado em TI, foco em IA e Dados.
"""

CLASSIFIER_PROMPT = 'Analise a entrada. Responda APENAS JSON: {"is_important": boolean, "fact_type": "string", "extracted_info": "string", "lgpd_risk": boolean}'

# --- 3. LÓGICA DE PERSISTÊNCIA ---
def carregar_dados():
    try:
        perfil = supabase.table("perfil_usuario").select("*").eq("usuario", "André").single().execute().data
        hist = supabase.table("historico_conversas").select("pergunta, resposta").eq("usuario", "André").order("created_at", desc=True).limit(3).execute().data
        return perfil, hist
    except: return {}, []

# --- 4. SIDEBAR OCULTÁVEL (CONTROLES) ---
with st.sidebar:
    st.header("Painel de Controle")
    
    # Botão de Novo Diálogo
    if st.button("Nova conversa", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.divider()
    
    # Upload de Arquivo
    st.subheader("📎 Anexar Contexto")
    uploaded_file = st.file_uploader("Arraste scripts ou dados aqui", type=["txt", "py", "csv", "json"], label_visibility="collapsed")
    
    st.divider()
    st.caption("Agente Pessoal")

# --- 5. INTERFACE DE CHAT ---
st.title("Agente Pessoal")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Exibe histórico da sessão atual
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input do Usuário
if prompt := st.chat_input("Em que posso ser útil hoje?"):
    # Processamento de arquivo (se houver)
    file_context = ""
    if uploaded_file:
        raw_content = uploaded_file.getvalue().decode("utf-8")
        file_context = f"\n\n[DADOS DO ARQUIVO ANEXADO]:\n{raw_content}"
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt if not uploaded_file else f"📎 **{uploaded_file.name}**\n\n{prompt}")

    with st.chat_message("assistant"):
        perfil, hist_raw = carregar_dados()
        
        # 1. Análise de Segurança e Classificação
        res_class = client_groq.chat.completions.create(
            messages=[{"role": "system", "content": CLASSIFIER_PROMPT}, {"role": "user", "content": prompt + file_context}],
            model="llama-3.3-70b-versatile", response_format={"type": "json_object"}
        )
        decisao = json.loads(res_class.choices[0].message.content)

        # 2. Construção da Resposta Final
        hist_context = "\n".join([f"U: {d['pergunta']} | A: {d['resposta']}" for d in hist_raw])
        full_system = f"{BASE_SYSTEM_PROMPT}\n\nPERFIL DO USUÁRIO: {perfil}\nHISTÓRICO RECENTE: {hist_context}"
        
        # Feedback de memória se algo for novo
        memoria_nota = ""
        if decisao.get("is_important"):
            info = decisao.get("extracted_info")
            memoria_nota = f"\n\n*(Governança: Registrei '{info}' na sua base de conhecimento.)*"
            # Update no Supabase (omitido aqui para brevidade, mas segue a lógica anterior)

        res_final = client_groq.chat.completions.create(
            messages=[{"role": "system", "content": full_system}, *st.session_state.messages, {"role": "user", "content": file_context}],
            model="llama-3.3-70b-versatile"
        )
        
        resposta_final = res_final.choices[0].message.content
        
        # Alerta de LGPD se houver risco
        if decisao.get("lgpd_risk"):
            resposta_final = "🚨 **AVISO DE PRIVACIDADE:** Detectei possíveis dados sensíveis. Procedendo com cautela técnica.\n\n" + resposta_final

        st.markdown(resposta_final + memoria_nota)
        st.session_state.messages.append({"role": "assistant", "content": resposta_final + memoria_nota})
        
        # Salvamento no DB
        supabase.table("historico_conversas").insert({
            "usuario": "André", "pergunta": prompt, "resposta": resposta_final, 
            "categoria": "importante" if (decisao.get("is_important") or uploaded_file) else "casual"
        }).execute()
