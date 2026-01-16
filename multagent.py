import streamlit as st
from groq import Groq
from supabase import create_client, Client
import json

# --- 1. CONFIGURAÇÃO (LAYOUT CENTRALIZADO) ---
st.set_page_config(page_title="Agente Pessoal", layout="centered", initial_sidebar_state="collapsed")

# CSS para esconder a sidebar e focar no chat
st.markdown("<style>[data-testid='stSidebar'] {display: none;} .stChatInput {bottom: 20px;}</style>", unsafe_allow_html=True)

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro na conexão: {e}")
    st.stop()

# --- 2. DEFINIÇÕES DE IA ---
BASE_SYSTEM_PROMPT = """Você é o 'Sênior', mentor de TI e mestre confeiteiro. 
Responda ao André com sarcasmo assertivo e analogias. 
Sempre que salvar algo no perfil dele (formação ou interesses), avise-o na resposta com uma frase curta."""

CLASSIFIER_PROMPT = 'Analise a mensagem. Responda APENAS JSON: {"is_important": boolean, "fact_type": "string", "extracted_info": "string"}'

# --- 3. LÓGICA DE DADOS ---
def carregar_contexto():
    try:
        perfil = supabase.table("perfil_usuario").select("*").eq("usuario", "André").single().execute().data
        hist = supabase.table("historico_conversas").select("pergunta, resposta").eq("usuario", "André").order("created_at", desc=True).limit(3).execute().data
        return perfil, hist
    except: return {}, []

# --- 4. INTERFACE ---
col_t, col_b = st.columns([0.8, 0.2])
with col_t:
    st.title("Agente Pessoal")
with col_b:
    # BOTÃO DE NOVO DIÁLOGO (Limpa a memória da conversa atual)
    if st.button("🆕 Novo"):
        st.session_state.messages = []
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Em que posso ser útil hoje?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        perfil, hist_raw = carregar_contexto()
        
        # 1. Classificação
        res_class = client_groq.chat.completions.create(
            messages=[{"role": "system", "content": CLASSIFIER_PROMPT}, {"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile", response_format={"type": "json_object"}
        )
        decisao = json.loads(res_class.choices[0].message.content)

        # 2. Roteamento e Feedback de Memória
        memoria_aviso = ""
        if decisao.get("is_important"):
            info = decisao.get("extracted_info")
            tipo = str(decisao.get("fact_type")).lower()
            coluna = "formacao" if any(x in tipo for x in ["ti", "carreira", "estudo"]) else "interesses"
            
            dado_atual = perfil.get(coluna, "")
            if info and info.lower() not in str(dado_atual).lower():
                novo_valor = f"{dado_atual} | {info}" if dado_atual else info
                supabase.table("perfil_usuario").update({coluna: novo_valor}).eq("usuario", "André").execute()
                memoria_aviso = f"\n\n*(Nota técnica: Acabei de anotar '{info}' no seu perfil de {coluna}.)*"

        # 3. Resposta Final
        hist_context = "\n".join([f"U: {d['pergunta']} | A: {d['resposta']}" for d in hist_raw])
        res_final = client_groq.chat.completions.create(
            messages=[{"role": "system", "content": f"{BASE_SYSTEM_PROMPT}\n\nPERFIL: {perfil}\nHISTÓRICO: {hist_context}"}, *st.session_state.messages],
            model="llama-3.3-70b-versatile"
        )
        resposta = res_final.choices[0].message.content + memoria_aviso

        # 4. Salvamento
        is_imp = decisao.get("is_important") or any(x in prompt.lower() for x in ["receita", "script"])
        supabase.table("historico_conversas").insert({
            "usuario": "André", "pergunta": prompt, "resposta": resposta, 
            "categoria": "importante" if is_imp else "casual"
        }).execute()

        st.markdown(resposta)
        st.session_state.messages.append({"role": "assistant", "content": resposta})
