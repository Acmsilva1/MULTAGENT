import streamlit as st
from groq import Groq
from supabase import create_client, Client
import pandas as pd
import io
import json

# --- 1. CONFIGURAÇÃO DA PÁGINA (A CEREJA DO BOLO) ---
st.set_page_config(page_title="Agente Sênior Ácido", page_icon="🍰", layout="wide")

# --- 2. CONEXÕES ---
try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro na fiação técnica: {e}")
    st.stop()

# --- 3. DEFINIÇÕES DE PERSONALIDADE E IA ---
BASE_SYSTEM_PROMPT = """
Você é o 'Sênior Ácido', mentor de TI veterano e mestre confeiteiro técnico.
- Missão: Apoiar o André (recém-formado em TI, foco em IA, Dados e LGPD).
- Estilo: Sarcástico, assertivo, usa analogias de confeitaria para explicar erros de código.
- Regra: Use os dados do PERFIL para personalizar a resposta. Se o André aprender algo novo, parabenize-o com ironia.
"""

CLASSIFIER_PROMPT = """
Analise a mensagem do usuário e extraia fatos RELEVANTES e PERMANENTES (carreira, novas ferramentas, hobbies, regras de LGPD).
Responda APENAS em JSON: 
{"is_important": boolean, "fact_type": "formacao/interesses/lgpd", "extracted_info": "string ou null"}
"""

# --- 4. FUNÇÕES DE BUSCA DE DADOS ---
def carregar_dados_usuario():
    try:
        # Busca perfil fixo
        perfil = supabase.table("perfil_usuario").select("*").eq("usuario", "André").single().execute().data
        # Busca histórico recente (últimas 3)
        historico = supabase.table("historico_conversas").select("pergunta, resposta").eq("usuario", "André").order("created_at", desc=True).limit(3).execute().data
        
        hist_str = "\n".join([f"U: {d['pergunta']} | A: {d['resposta']}" for d in historico]) if historico else ""
        return perfil, hist_str
    except Exception as e:
        st.sidebar.error(f"Erro ao ler DB: {e}")
        return None, ""

# --- 5. INTERFACE LATERAL (SIDEBAR) ---
with st.sidebar:
    st.header("🧠 Memória do Sistema")
    
    perfil, historico_recente = carregar_dados_usuario()
    
    if perfil:
        st.subheader("Perfil do André (Core)")
        st.info(f"🎓 **Foco:** {perfil.get('formacao')}")
        st.info(f"🎨 **Interesses:** {perfil.get('interesses')}")
        with st.expander("Ver JSON Bruto do Banco"):
            st.json(perfil)
    
    st.divider()
    st.header("🗂️ Analisador de Arquivos")
    arquivo = st.file_uploader("Suba um código ou log", type=["txt", "py", "csv", "log"])
    
    conteudo_arquivo = ""
    if arquivo:
        if arquivo.name.endswith(".csv"):
            df = pd.read_csv(arquivo)
            conteudo_arquivo = f"\n[CSV DATA]:\n{df.head(10).to_string()}"
        else:
            conteudo_arquivo = f"\n[FILE CONTENT]:\n{arquivo.getvalue().decode('utf-8')}"
        st.success("Arquivo processado!")

    if st.button("Limpar Histórico Visual"):
        st.session_state.messages = []
        st.rerun()

# --- 6. CHAT PRINCIPAL ---
st.title("Agente Pessoal: TI & Confeitaria")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("O que vamos cozinhar hoje?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Pensando...", expanded=False) as status:
            
            # PASSO 1: Classificar se o que o André disse deve ser salvo no Perfil
            try:
                analise_res = client_groq.chat.completions.create(
                    messages=[{"role": "system", "content": CLASSIFIER_PROMPT}, {"role": "user", "content": prompt}],
                    model="llama-3.3-70b-versatile",
                    response_format={"type": "json_object"}
                )
                decisao = json.loads(analise_res.choices[0].message.content)
            except:
                decisao = {"is_important": False}

            # PASSO 2: Update real no Banco de Dados se for importante
            if decisao.get("is_important"):
                info = decisao.get("extracted_info")
                tipo = decisao.get("fact_type")
                # Mapeamento para as colunas do seu novo SQL
                coluna = "formacao" if tipo == "formacao" else "interesses"
                
                supabase.table("perfil_usuario").update({coluna: info}).eq("usuario", "André").execute()
                status.write(f"✅ Memória de longo prazo atualizada: {info}")

            # PASSO 3: Gerar resposta com todo o contexto
            perfil_contexto = f"Perfil do André: {perfil}" if perfil else "André: Dev de TI."
            prompt_final = f"{BASE_SYSTEM_PROMPT}\n\nCONTEXTO DO USUÁRIO: {perfil_contexto}\n\nHISTÓRICO: {historico_recente}\n\nARQUIVO: {conteudo_arquivo}"
            
            res_ia = client_groq.chat.completions.create(
                messages=[{"role": "system", "content": prompt_final}, *st.session_state.messages],
                model="llama-3.3-70b-versatile"
            )
            resposta = res_ia.choices[0].message.content
            
            # PASSO 4: Salvar a conversa no Histórico (Buffer)
            supabase.table("historico_conversas").insert({
                "pergunta": prompt, 
                "resposta": resposta,
                "categoria": "importante" if decisao.get("is_important") else "casual"
            }).execute()
            
            status.update(label="Análise completa!", state="complete")

        st.markdown(resposta)
        st.session_state.messages.append({"role": "assistant", "content": resposta})
