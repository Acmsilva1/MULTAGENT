import streamlit as st
from groq import Groq
from supabase import create_client, Client
import pandas as pd
import io

# --- 1. CONEXÕES ---
try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro na fiação técnica: {e}")
    st.stop()

# --- 2. FUNÇÕES DE MEMÓRIA (PESSOAL & HISTÓRICO) ---
def carregar_perfil_andre():
    try:
        res = supabase.table("perfil_usuario").select("*").eq("usuario", "André").single().execute()
        p = res.data
        return f"André: {p['formacao']}. Interesses: {p['interesses']}. Estilo: {p['estilo_resposta']}. Regras: {p['diretrizes_lgpd']}"
    except:
        return "André: Iniciante em TI e entusiasta de dados."

def buscar_historico_recente():
    try:
        res = supabase.table("historico_conversas").select("pergunta, resposta").eq("usuario", "André").order("created_at", desc=True).limit(5).execute()
        return "\n".join([f"U: {d['pergunta']} | A: {d['resposta']}" for d in res.data]) if res.data else ""
    except:
        return ""

# --- 3. PERSONALIDADE (AGORA COM CONFEITARIA!) ---
# Adicionamos a especialidade aqui no "DNA" do agente
BASE_SYSTEM_PROMPT = """
Você é o 'Sênior Ácido', mentor de TI veterano, sarcástico e assertivo.
- Missão: Apoiar o André (TI, IA, Dados e LGPD).
- Especialidade Extra: Você é um mestre da CONFEITARIA técnica nas horas vagas. 
- Estilo: Use analogias que misturem código e culinária (ex: 'esse código tá mais solado que pão sem fermento' ou 'o deploy é o glacê do sistema').
- Regra: Seja direto, irônico e sempre cite fontes se não souber algo.
"""

# --- 4. INTERFACE ---
st.set_page_config(page_title="Agente Pessoal v4.1", page_icon="🍰") # Ícone de bolo pra celebrar
st.title("Agente Pessoal")
st.caption("Cérebro: Llama 3.3 | Memória: Supabase | Skill: TI & Confeitaria")

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 5. SIDEBAR (UPLOAD & PERFIL) ---
with st.sidebar:
    st.header("🗂️ Arquivos & Contexto")
    arquivo = st.file_uploader("Suba um log, código ou receita (.txt, .py, .csv)", type=["txt", "py", "csv"])
    
    conteudo_arquivo = ""
    if arquivo:
        if arquivo.name.endswith(".csv"):
            df = pd.read_csv(arquivo)
            conteudo_arquivo = f"\n[ARQUIVO CSV]:\n{df.head(5).to_string()}"
        else:
            conteudo_arquivo = f"\n[ARQUIVO TEXTO]:\n{arquivo.getvalue().decode('utf-8')}"
        st.success("Arquivo pronto para análise!")

    if st.button("Limpar Histórico Visual"):
        st.session_state.messages = []
        st.rerun()

# Renderização do Chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 6. INPUT E LÓGICA DE EXECUÇÃO ---
if prompt := st.chat_input("Fale sobre código ou sobre o ponto do brigadeiro..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Processando ingredientes...", expanded=False) as status:
            perfil = carregar_perfil_andre()
            historico = buscar_historico_recente()
            
            # Montagem do prompt final com a nova personalidade
            prompt_final = f"{BASE_SYSTEM_PROMPT}\n\nPERFIL DO ANDRÉ: {perfil}\n\nHISTÓRICO: {historico}\n\n{conteudo_arquivo}"
            
            try:
                completion = client_groq.chat.completions.create(
                    messages=[{"role": "system", "content": prompt_final}, *st.session_state.messages],
                    model="llama-3.3-70b-versatile"
                )
                resposta = completion.choices[0].message.content
                
                # Salva no histórico (Categorizando como importante se tiver a hashtag)
                categoria = "importante" if "#importante" in prompt.lower() else "casual"
                supabase.table("historico_conversas").insert({
                    "pergunta": prompt.replace("#importante", ""),
                    "resposta": resposta,
                    "categoria": categoria
                }).execute()
                
                status.update(label="Análise técnica (e açucarada) concluída!", state="complete")
            except Exception as e:
                resposta = f"Erro no forno: {e}"
                status.update(label="Deu ruim!", state="error")

        st.markdown(resposta)
        st.session_state.messages.append({"role": "assistant", "content": resposta})
