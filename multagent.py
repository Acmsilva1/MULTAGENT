import streamlit as st
from groq import Groq
from supabase import create_client, Client
import json

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Agente pessoal", layout="centered", initial_sidebar_state="collapsed")

# --- 2. CSS PARA DOCK HORIZONTAL FLUTUANTE ---
st.markdown("""
    <style>
        [data-testid="stSidebar"], #MainMenu, footer {display: none;}
        
        /* A Doca agora é horizontal e fica no topo à direita */
        .floating-dock {
            position: fixed;
            right: 30px;
            top: 30px;
            display: flex;
            align-items: center;
            gap: 10px;
            z-index: 1000;
            background: rgba(30, 31, 38, 0.9);
            padding: 8px 15px;
            border-radius: 30px;
            border: 1px solid rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(15px);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
        }

        /* Compactar o Uploader para virar um ícone */
        .stFileUploader { width: 45px !important; }
        .stFileUploader section { padding: 0 !important; min-height: 45px !important; }
        .stFileUploader label, .stFileUploader small { display: none !important; }
        .stFileUploader [data-testid="stFileUploadDropzone"] { 
            border: none !important; 
            background: transparent !important; 
        }
        
        /* Botão Novo circular */
        div.stButton > button {
            border-radius: 50% !important;
            width: 42px !important;
            height: 42px !important;
            border: none !important;
            background: rgba(255, 255, 255, 0.05) !important;
            transition: 0.3s;
        }
        div.stButton > button:hover { background: rgba(255, 255, 255, 0.2) !important; }
    </style>
""", unsafe_allow_html=True)

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro na conexão: {e}")
    st.stop()

# --- 3. DOCK LADO A LADO ---
# Usamos colunas dentro de um container fixo via HTML/CSS
with st.container():
    # Simulando a doca horizontal
    st.markdown('<div class="floating-dock">', unsafe_allow_html=True)
    col_btn, col_upload = st.columns([1, 1])
    
    with col_btn:
        if st.button("Novo"):
            st.session_state.messages = []
            st.rerun()
            
    with col_upload:
        uploaded_file = st.file_uploader("📎", type=["txt", "py", "csv"], label_visibility="collapsed")
    
    st.markdown('</div>', unsafe_allow_html=True)

# --- 4. CHAT PRINCIPAL ---
st.title("Agente pessoal")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Área de Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input de Chat
if prompt := st.chat_input("Em que posso ser útil?"):
    # Lógica de processamento de arquivo
    file_content = ""
    if uploaded_file:
        content = uploaded_file.getvalue().decode("utf-8")
        file_content = f"\n\n[ARQUIVO LIDO: {uploaded_file.name}]\n{content}"
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt if not uploaded_file else f"📎 **{uploaded_file.name}**\n\n{prompt}")

    with st.chat_message("assistant"):
        # IA gera resposta com contexto
        res_ia = client_groq.chat.completions.create(
            messages=[
                {"role": "system", "content": "Você é o Sênior. Mentor de TI. Sarcástico. Usa analogias criativas quando necessário. Foco em LGPD."},
                *st.session_state.messages,
                {"role": "user", "content": file_content} if file_content else {"role": "system", "content": "Sem anexos."}
            ],
            model="llama-3.3-70b-versatile"
        )
        resposta = res_ia.choices[0].message.content
        
        # Salvamento no Banco (Só o texto do prompt, sem o dump do arquivo para não estourar o DB)
        supabase.table("historico_conversas").insert({
            "usuario": "André", "pergunta": prompt, "resposta": resposta, 
            "categoria": "importante" if uploaded_file else "casual"
        }).execute()

        st.markdown(resposta)
        st.session_state.messages.append({"role": "assistant", "content": resposta})
        if uploaded_file: st.toast("Contexto do arquivo integrado!", icon="📎")
