import streamlit as st
from groq import Groq
from supabase import create_client, Client
import pandas as pd
import json

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Sênior Ácido v7.0", layout="wide")

# --- 2. CONEXÕES ---
try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro na fiação técnica: {e}")
    st.stop()

# --- 3. DEFINIÇÕES DE PERSONALIDADE E CLASSIFICADOR ---
BASE_SYSTEM_PROMPT = """
Você é o 'Sênior', mentor de TI veterano e mestre confeiteiro técnico.
- Missão: Apoiar o André (TI, IA, Dados e LGPD).
- Estilo: Sarcástico, assertivo, usa analogias gerais.
- Regra: Use os dados do PERFIL para personalizar a resposta.
"""

CLASSIFIER_PROMPT = """
Analise a mensagem do usuário e extraia fatos RELEVANTES e PERMANENTES.
Responda APENAS em JSON: 
{"is_important": boolean, "fact_type": "carreira/hobbies/lgpd/outros", "extracted_info": "string ou null"}
"""

# --- 4. FUNÇÕES DE BUSCA ---
def carregar_dados_usuario():
    try:
        perfil = supabase.table("perfil_usuario").select("*").eq("usuario", "André").single().execute().data
        historico = supabase.table("historico_conversas").select("pergunta, resposta").eq("usuario", "André").order("created_at", desc=True).limit(3).execute().data
        hist_str = "\n".join([f"U: {d['pergunta']} | A: {d['resposta']}" for d in historico]) if historico else ""
        return perfil, hist_str
    except Exception as e:
        return None, ""

# --- 5. SIDEBAR (AUDITORIA EM TEMPO REAL) ---
with st.sidebar:
    st.header("🧠 Memória Core")
    perfil, historico_recente = carregar_dados_usuario()
    
    if perfil:
        st.write(f"🎓 **Foco:** {perfil.get('formacao')}")
        st.write(f"🎨 **Interesses:** {perfil.get('interesses')}")
        st.write(f"⚖️ **LGPD:** {perfil.get('diretrizes_lgpd')}")
        with st.expander("Ver JSON do Banco"):
            st.json(perfil)
    
    st.divider()
    st.header("🗂️ Arquivos")
    arquivo = st.file_uploader("Upload de contexto", type=["txt", "py", "csv", "log"])
    conteudo_arquivo = ""
    if arquivo:
        if arquivo.name.endswith(".csv"):
            df = pd.read_csv(arquivo)
            conteudo_arquivo = f"\n[CSV DATA]:\n{df.head(10).to_string()}"
        else:
            conteudo_arquivo = f"\n[FILE]:\n{arquivo.getvalue().decode('utf-8')}"
        st.success("Arquivo pronto!")

# --- 6. CHAT PRINCIPAL ---
st.title("Agente Pessoal")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Diga algo importante ou apenas jogue conversa fora..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Processando ingredientes...", expanded=False) as status:
            
            # PASSO 1: Classificar importância
            try:
                analise_res = client_groq.chat.completions.create(
                    messages=[{"role": "system", "content": CLASSIFIER_PROMPT}, {"role": "user", "content": prompt}],
                    model="llama-3.3-70b-versatile",
                    response_format={"type": "json_object"}
                )
                decisao = json.loads(analise_res.choices[0].message.content)
            except:
                decisao = {"is_important": False}

            # PASSO 2: Roteamento e Update (O coração da sua dúvida)
            if decisao.get("is_important"):
                info_nova = decisao.get("extracted_info")
                tipo_ia = decisao.get("fact_type").lower()
                
                # Mapeamento para as colunas físicas do DB
                if any(x in tipo_ia for x in ["carreira", "formacao", "cargo", "estudos"]):
                    coluna_alvo = "formacao"
                elif any(x in tipo_ia for x in ["lgpd", "seguranca", "privacidade"]):
                    coluna_alvo = "diretrizes_lgpd"
                else:
                    coluna_alvo = "interesses"

                # Lógica de concatenação para não apagar o passado
                dado_atual = perfil.get(coluna_alvo) if perfil else ""
                if info_nova.lower() not in str(dado_atual).lower():
                    valor_atualizado = f"{dado_atual} | {info_nova}" if dado_atual else info_nova
                    supabase.table("perfil_usuario").update({coluna_alvo: valor_atualizado}).eq("usuario", "André").execute()
                    status.write(f"💾 {coluna_alvo} atualizado com sucesso!")

            # PASSO 3: Resposta com o DNA atualizado
            perfil_contexto = f"Perfil Atual do André: {perfil}"
            prompt_final = f"{BASE_SYSTEM_PROMPT}\n\nCONTEXTO: {perfil_contexto}\n\nHISTÓRICO: {historico_recente}\n\nARQUIVO: {conteudo_arquivo}"
            
            res_ia = client_groq.chat.completions.create(
                messages=[{"role": "system", "content": prompt_final}, *st.session_state.messages],
                model="llama-3.3-70b-versatile"
            )
            resposta = res_ia.choices[0].message.content
            
            # PASSO 4: Log de conversa
            supabase.table("historico_conversas").insert({
                "pergunta": prompt, "resposta": resposta, "categoria": "importante" if decisao.get("is_important") else "casual"
            }).execute()
            
            status.update(label="Tudo pronto!", state="complete")

        st.markdown(resposta)
        st.session_state.messages.append({"role": "assistant", "content": resposta})
