import streamlit as st
from groq import Groq
from supabase import create_client, Client
import json

# --- 1. CONFIGURAÇÃO (TOTAL CLEAN) ---
st.set_page_config(page_title="Agente pessoal", layout="centered", initial_sidebar_state="collapsed")

# --- 2. CSS AVANÇADO: A DOCA DE COMANDOS ---
st.markdown("""
    <style>
        /* Remove elementos inúteis do Streamlit */
        [data-testid="stSidebar"], #MainMenu, footer {display: none;}
        
        /* Container flutuante na direita centralizado verticalmente */
        .floating-dock {
            position: fixed;
            right: 25px;
            top: 50%;
            transform: translateY(-50%);
            display: flex;
            flex-direction: column;
            gap: 15px;
            z-index: 1000;
            background: rgba(38, 39, 48, 0.8);
            padding: 15px;
            border-radius: 50px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
        }

        /* Ajuste do Uploader para não quebrar o layout */
        .stFileUploader section {
            padding: 0 !important;
            width: 45px !important;
            min-width: 45px !important;
        }
        .stFileUploader label { display: none; }
        
        /* Ajuste do botão Novo para o Dock */
        div.stButton > button {
            border-radius: 50% !important;
            width: 45px !important;
            height: 45px !important;
            padding: 0 !important;
            font-size: 20px !important;
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

# --- 4. BARRA DE FERRAMENTAS FLUTUANTE (DOCK) ---
# Usamos colunas vazias apenas para posicionar o uploader no dock
with st.container():
    # Isso cria a estrutura visual no lado direito
    st.markdown('<div class="floating-dock">', unsafe_allow_html=True)
    
    # Botão Novo Diálogo
    if st.button("🆕", help="Resetar conversa atual"):
        st.session_state.messages = []
        st.rerun()
    
    # Upload de Arquivo (Ícone de Clipe)
    uploaded_file = st.file_uploader("📎", type=["txt", "py", "csv"], help="Anexar contexto (LGPD Ativa)")
    
    st.markdown('</div>', unsafe_allow_html=True)

# --- 5. CHAT PRINCIPAL ---
st.title("Agente pessoal")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Em que posso ser útil hoje?"):
    contexto_arquivo = ""
    if uploaded_file:
        stringio = uploaded_file.getvalue().decode("utf-8")
        contexto_arquivo = f"\n\n[FILE_CONTEXT: {uploaded_file.name}]\n{stringio}"
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt if not uploaded_file else f"📎 **{uploaded_file.name}**\n\n{prompt}")

    with st.chat_message("assistant"):
        perfil, hist_raw = carregar_contexto()
        
        # 1. IA Analisa TUDO (Prompt + Arquivo + LGPD)
        res_ia = client_groq.chat.completions.create(
            messages=[
                {"role": "system", "content": f"Você é o Sênior. Sarcástico e técnico. Usa analogias criativas e assertivas. Perfil: {perfil}. Analise arquivos para LGPD/Malware."},
                *st.session_state.messages,
                {"role": "user", "content": contexto_arquivo} if contexto_arquivo else {"role": "system", "content": "Nenhum arquivo enviado."}
            ],
            model="llama-3.3-70b-versatile"
        )
        resposta = res_ia.choices[0].message.content

        # 2. Notificação de Memória (Sempre que algo for relevante)
        # Lógica interna para decidir se salvamos
        if len(prompt) > 20 or uploaded_file:
            supabase.table("historico_conversas").insert({
                "usuario": "André", "pergunta": prompt, "resposta": resposta, 
                "categoria": "importante" if uploaded_file else "casual"
            }).execute()
            if uploaded_file: st.toast("Arquivo processado!")

        st.markdown(resposta)
        st.session_state.messages.append({"role": "assistant", "content": resposta})
