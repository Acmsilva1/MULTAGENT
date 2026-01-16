import streamlit as st
from groq import Groq
from supabase import create_client, Client
import pandas as pd
import json

# --- 1. CONFIGURAÇÃO E CONEXÕES ---
st.set_page_config(page_title="Agente Pessoal", layout="wide")

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro na fiação: {e}")
    st.stop()

# --- 2. PERSONALIDADE E CLASSIFICADOR ---
BASE_SYSTEM_PROMPT = "Você é o 'Sênior', mentor de TI e mestre confeiteiro. Ajude o André. Use analogias inteligentes nas explicações. Seja sarcástico sem exagerar ou ofender."
CLASSIFIER_PROMPT = 'Analise a mensagem e extraia fatos em JSON: {"is_important": boolean, "fact_type": "string", "extracted_info": "string"}'

# --- 3. FUNÇÕES DE BANCO DE DADOS ---
def carregar_dados_usuario():
    try:
        perfil = supabase.table("perfil_usuario").select("*").eq("usuario", "André").single().execute().data
        # Busca o histórico simplificado para a lateral
        historico_side = supabase.table("historico_conversas").select("pergunta, resposta, categoria").eq("usuario", "André").order("created_at", desc=True).limit(10).execute().data
        return perfil, historico_side
    except:
        return None, []

def limpar_historico_db():
    try:
        supabase.table("historico_conversas").delete().eq("categoria", "casual").execute()
        return True
    except Exception as e:
        st.sidebar.error(f"Erro na limpeza: {e}")
        return False

# --- 4. SIDEBAR (HISTÓRICO MINIMALISTA) ---
perfil, hist_raw = carregar_dados_usuario()

with st.sidebar:
    st.header("🧠 Perfil")
    if perfil:
        st.caption(f"🎓 {perfil.get('formacao')}")
        st.caption(f"🎨 {perfil.get('interesses')}")
    
    st.divider()
    st.subheader("📜 Conversas Recentes")
    
    if hist_raw:
        for item in hist_raw:
            # Título encurtado com ícone de status
            icon = "⭐" if item['categoria'] == 'importante' else "💬"
            label = item['pergunta'][:25] + "..." if len(item['pergunta']) > 25 else item['pergunta']
            
            with st.expander(f"{icon} {label}"):
                st.write(item['resposta'])
    else:
        st.write("Sem registros.")

    st.divider()
    if st.button("🗑️ Limpar Casuais"):
        if limpar_historico_db():
            st.rerun()

# --- 5. CHAT PRINCIPAL ---
st.title("Agente Sênior Ácido")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Área de exibição das mensagens
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input fixo no rodapé
if prompt := st.chat_input("Fale com o Sênior..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Pensando...", expanded=False) as status:
            # Classificação interna
            try:
                analise_res = client_groq.chat.completions.create(
                    messages=[{"role": "system", "content": CLASSIFIER_PROMPT}, {"role": "user", "content": prompt}],
                    model="llama-3.3-70b-versatile",
                    response_format={"type": "json_object"}
                )
                decisao = json.loads(analise_res.choices[0].message.content)
            except:
                decisao = {"is_important": False}

            # Atualização Silenciosa de Perfil
            if decisao.get("is_important"):
                info = decisao.get("extracted_info")
                coluna = "formacao" if "carreira" in str(decisao.get("fact_type")).lower() else "interesses"
                dado_atual = perfil.get(coluna) if perfil else ""
                if info and info.lower() not in str(dado_atual).lower():
                    novo_valor = f"{dado_atual} | {info}" if dado_atual else info
                    supabase.table("perfil_usuario").update({coluna: novo_valor}).eq("usuario", "André").execute()

            # Resposta Final
            hist_contexto = "\n".join([f"U: {d['pergunta']} | A: {d['resposta']}" for d in hist_raw[:3]])
            prompt_final = f"{BASE_SYSTEM_PROMPT}\n\nCONTEXTO: {perfil}\n\nHISTÓRICO: {hist_contexto}"
            
            res_ia = client_groq.chat.completions.create(
                messages=[{"role": "system", "content": prompt_final}, *st.session_state.messages],
                model="llama-3.3-70b-versatile"
            )
            resposta = res_ia.choices[0].message.content
            
            # Persistência no DB
            is_imp = decisao.get("is_important") or any(x in prompt.lower() for x in ["receita", "script", "codigo"])
            supabase.table("historico_conversas").insert({
                "usuario": "André",
                "pergunta": prompt, 
                "resposta": resposta, 
                "categoria": "importante" if is_imp else "casual"
            }).execute()
            
            status.update(label="Concluído!", state="complete")

        st.markdown(resposta)
        st.session_state.messages.append({"role": "assistant", "content": resposta})
        if is_imp: st.toast("💾 Salvo permanentemente!", icon="⭐")
