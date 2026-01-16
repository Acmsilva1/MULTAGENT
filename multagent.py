import streamlit as st
from groq import Groq
from supabase import create_client, Client
import pandas as pd
import json

# --- 1. CONFIGURAÇÃO E CONEXÕES ---
# Ajustado para 'centered' para foco total no chat sem poluição lateral
st.set_page_config(page_title="Agente Pessoal", layout="centered")

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro na fiação: {e}")
    st.stop()

# --- 2. PERSONALIDADE E CLASSIFICADOR ---
# Mantendo sua definição exata de 'Sênior'
BASE_SYSTEM_PROMPT = "Você é o 'Sênior', mentor de TI e mestre confeiteiro. Ajude o André. Use analogias intligentes nas explicações. Seja sarcástico sem exagerar ou ofender."
CLASSIFIER_PROMPT = 'Analise a mensagem e extraia fatos em JSON: {"is_important": boolean, "fact_type": "string", "extracted_info": "string"}'

# --- 3. FUNÇÕES DE BANCO DE DADOS ---
def carregar_dados_usuario():
    try:
        perfil = supabase.table("perfil_usuario").select("*").eq("usuario", "André").single().execute().data
        historico = supabase.table("historico_conversas").select("pergunta, resposta").eq("usuario", "André").order("created_at", desc=True).limit(3).execute().data
        return perfil, historico
    except:
        return None, []

def limpar_historico_db():
    try:
        # Deleta apenas o lixo (casual) como você pediu
        supabase.table("historico_conversas").delete().eq("categoria", "casual").execute()
        return True
    except Exception as e:
        st.sidebar.error(f"Erro na faxina: {e}")
        return False

# --- 4. SIDEBAR (AUDITORIA E FAXINA) ---
# A única parte visual além do chat, para manter a governança
with st.sidebar:
    st.header("🧠 Memória Core")
    perfil, hist_raw = carregar_dados_usuario()
    
    if perfil:
        st.write(f"🎓 **Foco:** {perfil.get('formacao')}")
        st.write(f"🎨 **Interesses:** {perfil.get('interesses')}")
        with st.expander("Ver JSON do Banco"):
            st.json(perfil)
    
    st.divider()
    st.header("🧹 Governança de Dados")
    if st.button("🗑️ Limpar Conversas Casuais"):
        if limpar_historico_db():
            st.sidebar.success("Lixo deletado! O plano Free agradece.")
            st.rerun()

    st.divider()
    arquivo = st.file_uploader("Upload de contexto", type=["txt", "py", "csv"])

# --- 5. CHAT PRINCIPAL (SEM POLUIÇÃO) ---
st.title("Agente Sênior Ácido")
st.caption("Foco em TI, Dados e Confeitaria Técnica")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Exibição limpa do histórico da sessão atual
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("O que vamos codificar (ou assar) hoje?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Processando...", expanded=False) as status:
            # Lógica de Classificação para o DB
            try:
                analise_res = client_groq.chat.completions.create(
                    messages=[{"role": "system", "content": CLASSIFIER_PROMPT}, {"role": "user", "content": prompt}],
                    model="llama-3.3-70b-versatile",
                    response_format={"type": "json_object"}
                )
                decisao = json.loads(analise_res.choices[0].message.content)
            except:
                decisao = {"is_important": False}

            # Update no Perfil (Roteamento que você validou)
            if decisao.get("is_important"):
                info = decisao.get("extracted_info")
                tipo = decisao.get("fact_type").lower()
                coluna = "formacao" if "carreira" in tipo else "interesses"
                
                dado_atual = perfil.get(coluna) if perfil else ""
                if info.lower() not in str(dado_atual).lower():
                    novo_valor = f"{dado_atual} | {info}" if dado_atual else info
                    supabase.table("perfil_usuario").update({coluna: novo_valor}).eq("usuario", "André").execute()

            # Geração da Resposta Final
            hist_str = "\n".join([f"U: {d['pergunta']} | A: {d['resposta']}" for d in hist_raw])
            prompt_final = f"{BASE_SYSTEM_PROMPT}\n\nPERFIL: {perfil}\n\nHISTÓRICO: {hist_str}"
            
            res_ia = client_groq.chat.completions.create(
                messages=[{"role": "system", "content": prompt_final}, *st.session_state.messages],
                model="llama-3.3-70b-versatile"
            )
            resposta = res_ia.choices[0].message.content
            
            # Persistência no Histórico do DB (Sem aparecer na tela principal)
            is_imp = decisao.get("is_important") or any(x in prompt.lower() for x in ["receita", "script", "codigo", "calculadora"])
            supabase.table("historico_conversas").insert({
                "pergunta": prompt, 
                "resposta": resposta, 
                "categoria": "importante" if is_imp else "casual"
            }).execute()
            
            status.update(label="Pronto!", state="complete")

        st.markdown(resposta)
        st.session_state.messages.append({"role": "assistant", "content": resposta})
        # Notificação discreta de salvamento
        if is_imp: st.toast("🔖 Salvo no histórico importante.", icon="💾")
