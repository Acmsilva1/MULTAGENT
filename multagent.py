import streamlit as st
from groq import Groq
from supabase import create_client, Client
import json

# --- 1. CONFIGURAÇÃO (LAYOUT CENTRALIZADO) ---
st.set_page_config(page_title="Agente Pessoal", layout="centered", initial_sidebar_state="collapsed")

# --- 2. CSS PARA BOTÕES FLUTUANTES E INTERFACE ---
st.markdown("""
    <style>
        /* Esconde a barra lateral nativa */
        [data-testid="stSidebar"] {display: none;}
        
        /* Estilização da área de controle flutuante */
        .floating-controls {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 999;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        /* Ajuste do botão de upload para parecer um ícone flutuante */
        .stFileUploader {
            position: fixed;
            bottom: 100px;
            right: 20px;
            width: 50px;
            z-index: 999;
        }
    </style>
""", unsafe_allow_html=True)

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro na conexão: {e}")
    st.stop()

# --- 3. LÓGICA DE DADOS ---
def carregar_contexto():
    try:
        perfil = supabase.table("perfil_usuario").select("*").eq("usuario", "André").single().execute().data
        hist = supabase.table("historico_conversas").select("pergunta, resposta").eq("usuario", "André").order("created_at", desc=True).limit(2).execute().data
        return perfil, hist
    except: return {}, []

# --- 4. COMANDOS FLUTUANTES (FIXOS NA TELA) ---
# Botão Novo Diálogo fixo no canto superior
with st.container():
    col1, col2 = st.columns([0.9, 0.1])
    with col2:
        if st.button("Novo"):
            st.session_state.messages = []
            st.rerun()

# Botão de Upload fixo acima do input de chat
with st.container():
    uploaded_file = st.file_uploader("📎", type=["txt", "py", "csv"], label_visibility="collapsed")

# --- 5. CHAT PRINCIPAL ---
st.title("Agente Pessoal")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Diga algo..."):
    # Lógica de arquivo
    contexto_arquivo = ""
    if uploaded_file:
        stringio = uploaded_file.getvalue().decode("utf-8")
        contexto_arquivo = f"\n\n[ARQUIVO: {uploaded_file.name}]\n{stringio}"
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt if not uploaded_file else f"📎 {uploaded_file.name}\n\n{prompt}")

    with st.chat_message("assistant"):
        perfil, hist_raw = carregar_contexto()
        
        # 1. Classificação e LGPD
        res_class = client_groq.chat.completions.create(
            messages=[{"role": "system", "content": 'Analise a mensagem e extraia JSON: {"is_important": boolean, "info": "string", "lgpd_risk": boolean}'}, {"role": "user", "content": prompt + contexto_arquivo}],
            model="llama-3.3-70b-versatile", response_format={"type": "json_object"}
        )
        decisao = json.loads(res_class.choices[0].message.content)

        # 2. Resposta com Memória
        hist_context = "\n".join([f"U: {d['pergunta']} | A: {d['resposta']}" for d in hist_raw])
        sys_prompt = f"Você é o Sênior. Mentor de TI. Sarcástico. Usa analogias criativas em suas respostas. Perfil do usuário: {perfil}. Histórico: {hist_context}"
        
        res_final = client_groq.chat.completions.create(
            messages=[{"role": "system", "content": sys_prompt}, *st.session_state.messages],
            model="llama-3.3-70b-versatile"
        )
        resposta = res_final.choices[0].message.content
        
        if decisao.get("lgpd_risk"):
            resposta = "🚨 **ALERTA DE SEGURANÇA:** Identifiquei dados sensíveis no seu input/arquivo. Como seu mentor de TI, recomendo anonimizar isso antes de prosseguirmos.\n\n" + resposta

        # 3. Salvamento Silencioso
        supabase.table("historico_conversas").insert({
            "usuario": "André", "pergunta": prompt, "resposta": resposta, 
            "categoria": "importante" if (decisao.get("is_important") or uploaded_file) else "casual"
        }).execute()

        st.markdown(resposta)
        st.session_state.messages.append({"role": "assistant", "content": resposta})
