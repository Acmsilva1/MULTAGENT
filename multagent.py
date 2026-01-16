import streamlit as st
from groq import Groq
from supabase import create_client, Client
import json

# --- 1. CONFIGURAÇÃO (LAYOUT CENTRALIZADO E LIMPO) ---
st.set_page_config(page_title="Agente Pessoal", layout="centered", initial_sidebar_state="collapsed")

# CSS para esconder o botão da sidebar que sobra e limpar margens
st.markdown("<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} [data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro na conexão: {e}")
    st.stop()

# --- 2. DEFINIÇÕES DE IA ---
BASE_SYSTEM_PROMPT = "Você é o 'Sênior', mentor de TI e mestre confeiteiro. Ajude o André. Seja assertivo, sarcástico e use analogias."
CLASSIFIER_PROMPT = 'Analise a mensagem. Responda APENAS JSON: {"is_important": boolean, "fact_type": "string", "extracted_info": "string"}'

# --- 3. LÓGICA DE DADOS (SILENCIOSA) ---
def carregar_contexto_db():
    try:
        perfil = supabase.table("perfil_usuario").select("*").eq("usuario", "André").single().execute().data
        # Pega as últimas 3 interações apenas para o cérebro da IA
        hist = supabase.table("historico_conversas").select("pergunta, resposta").eq("usuario", "André").order("created_at", desc=True).limit(3).execute().data
        return perfil, hist
    except:
        return {}, []

# --- 4. INTERFACE DE CHAT (SÓ O QUE IMPORTA) ---
st.title("Agente Sênior Ácido")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostra as mensagens da sessão atual
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("O que vamos aprontar hoje?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        # Tudo acontece aqui dentro sem poluir a tela
        perfil, hist_raw = carregar_contexto_db()
        
        # 1. Classificação (Backend)
        res_class = client_groq.chat.completions.create(
            messages=[{"role": "system", "content": CLASSIFIER_PROMPT}, {"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile", response_format={"type": "json_object"}
        )
        decisao = json.loads(res_class.choices[0].message.content)

        # 2. Roteamento de Dados para o Perfil (Silencioso)
        if decisao.get("is_important"):
            info = decisao.get("extracted_info")
            coluna = "formacao" if "carreira" in str(decisao.get("fact_type")).lower() else "interesses"
            dado_atual = perfil.get(coluna, "")
            if info and info.lower() not in str(dado_atual).lower():
                novo_valor = f"{dado_atual} | {info}" if dado_atual else info
                supabase.table("perfil_usuario").update({coluna: novo_valor}).eq("usuario", "André").execute()

        # 3. Resposta da IA
        hist_context = "\n".join([f"U: {d['pergunta']} | A: {d['resposta']}" for d in hist_raw])
        res_final = client_groq.chat.completions.create(
            messages=[{"role": "system", "content": f"{BASE_SYSTEM_PROMPT}\n\nPERFIL: {perfil}\nHISTÓRICO: {hist_context}"}, *st.session_state.messages],
            model="llama-3.3-70b-versatile"
        )
        resposta = res_final.choices[0].message.content

        # 4. Salvamento no DB
        is_imp = decisao.get("is_important") or any(x in prompt.lower() for x in ["receita", "script", "codigo"])
        supabase.table("historico_conversas").insert({
            "usuario": "André", "pergunta": prompt, "resposta": resposta, 
            "categoria": "importante" if is_imp else "casual"
        }).execute()

        # Entrega final
        st.markdown(resposta)
        st.session_state.messages.append({"role": "assistant", "content": resposta})
