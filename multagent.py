import streamlit as st
from groq import Groq
from supabase import create_client, Client

# --- 1. CONEXÃO COM OS MOTORES (RODA NO BOOT) ---
try:
    # Llama (Cérebro)
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    
    # Supabase (Memória de Longo Prazo)
    supabase: Client = create_client(
        st.secrets["SUPABASE_URL"], 
        st.secrets["SUPABASE_KEY"]
    )
except Exception as e:
    st.error(f"Erro na fiação técnica: {e}")
    st.stop()

# --- 2. FUNÇÃO DE RESGATE DE MEMÓRIA (O "PESSOAL") ---
def buscar_memoria_recente(usuario="André"):
    try:
        # Busca as últimas 3 interações no banco para dar contexto
        res = supabase.table("memoria_agente") \
            .select("pergunta, resposta") \
            .eq("usuario", usuario) \
            .order("created_at", desc=True) \
            .limit(3) \
            .execute()
        
        if res.data:
            memorias = "\n".join([f"Usuário: {d['pergunta']} | Você: {d['resposta']}" for d in res.data])
            return f"\n\nMEMÓRIA DAS ÚLTIMAS CONVERSAS:\n{memorias}"
        return "\n\n(Esta é a primeira conversa oficial. Comece a construir o perfil do André.)"
    except Exception as e:
        return ""

# --- 3. PERSONALIDADE BÁSICA (SYSTEM PROMPT) ---
BASE_SYSTEM_PROMPT = """
Você é o 'Sênior Ácido', um mentor de TI veterano, sarcástico e assertivo.
- Missão: Apoiar o André, recém-formado em TI, com foco em IA, Dados e LGPD.
- Regra: Use analogias de TI e não enrole. Seja irônico, mas muito útil.
- IMPORTANTE: Use a 'MEMÓRIA' fornecida para lembrar o que o André já te contou ou perguntou.
"""

# --- 4. INTERFACE ---
st.set_page_config(page_title="Agente Pessoal", page_icon="🤖")
st.title("Agente Pessoal")
st.caption("Memória de Longo Prazo via Supabase | Llama 3.3")

# Inicializa o histórico na sessão (Memória de Curto Prazo/Visual)
if "messages" not in st.session_state:
    st.session_state.messages = []

# Exibe o chat na tela
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 5. INPUT E PROCESSAMENTO ---
if prompt := st.chat_input("Digite sua pergunta"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Consultando arquivos secretos...", expanded=False) as status:
            try:
                # PASSO 1: Buscar o que ele já sabe do André no Supabase
                contexto_pessoal = buscar_memoria_recente("André")
                prompt_final_com_memoria = BASE_SYSTEM_PROMPT + contexto_pessoal
                
                # PASSO 2: Chamar o Llama com o Sistema + Memória + Chat Atual
                chat_completion = client_groq.chat.completions.create(
                    messages=[
                        {"role": "system", "content": prompt_final_com_memoria},
                        *st.session_state.messages 
                    ],
                    model="llama-3.3-70b-versatile",
                    temperature=0.7,
                )
                resposta = chat_completion.choices[0].message.content
                
                # PASSO 3: Gravar a nova interação no Supabase
                supabase.table("memoria_agente").insert({
                    "pergunta": prompt,
                    "resposta": resposta,
                    "usuario": "André"
                }).execute()
                
                status.update(label="Memória atualizada e resposta pronta!", state="complete")
                
            except Exception as e:
                resposta = f"Deu tela azul! Erro: {str(e)}"
                status.update(label="Erro no sistema", state="error")

        st.markdown(resposta)
        st.session_state.messages.append({"role": "assistant", "content": resposta})

# --- 6. SIDEBAR ---
with st.sidebar:
    st.header("Painel de Controle")
    if st.button("Limpar Cache Visual"):
        st.session_state.messages = []
        st.rerun()
    st.info("O Sênior Ácido agora lê seu histórico do Supabase antes de cada resposta.")
