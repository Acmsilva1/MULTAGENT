import streamlit as st
from groq import Groq

# --- 1. CONFIGURAÇÃO DE SEGURANÇA ---
try:
    # Como o Gemini está bugado, vamos focar apenas no Llama por enquanto
    LLAMA_KEY = st.secrets["LLAMA_API_KEY"]
    client = Groq(api_key=LLAMA_KEY)
except Exception as e:
    st.error("Erro nos Secrets! A chave LLAMA_API_KEY precisa estar configurada.")
    st.stop()

# --- 2. O SYSTEM PROMPT (A ALMA DO AGENTE) ---
# Aqui colocamos toda a expertise e o sarcasmo que você gosta
SYSTEM_PROMPT = """
Você é o 'Sênior Ácido', um mentor de TI expert em IA, Dados e LGPD.
1. Personalidade: Sarcástico, assertivo e direto ao ponto.
2. Método: Use analogias do dia a dia para explicar conceitos complexos.
3. Regra de Ouro: Se o usuário falar sobre dados sensíveis, dê um alerta de segurança imediato.
4. Tom de voz: Trate o usuário como um 'padawan' de TI que precisa de orientação real, sem enrolação.
"""

# --- 3. PERSISTÊNCIA DE MEMÓRIA (SESSION STATE) ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 4. INTERFACE STREAMLIT ---
st.set_page_config(page_title="Sênior Ácido (Llama Edition)", page_icon="🦙")
st.title("🦙 Sênior Ácido: O Agente Expert")
st.caption("Operando via Llama 3 (Groq) | Backup Gemini: Desativado por mau comportamento.")

# Exibir histórico de chat
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# --- 5. O LOOP DE INTERAÇÃO ---
if prompt := st.chat_input("Mande sua dúvida técnica..."):
    # Adiciona a pergunta do usuário ao histórico
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            # Chamada direta para o Llama 3 - Rápida e estável
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    # Passamos o histórico para ele ter contexto sequencial
                    *st.session_state.messages 
                ],
                model="llama3-70b-8192", # O modelo mais inteligente do Llama no Groq
                temperature=0.7, # Para manter a criatividade no sarcasmo
            )
            
            resposta = chat_completion.choices[0].message.content
            st.markdown(resposta)
            
            # Salva a resposta do agente no histórico
            st.session_state.messages.append({"role": "assistant", "content": resposta})
            
        except Exception as e:
            st.error(f"Até o Llama cansou! Erro: {str(e)}")

# --- 6. GOVERNANÇA (BOTÃO DE LIMPEZA) ---
if st.sidebar.button("Limpar Sessão (LGPD)"):
    st.session_state.messages = []
    st.rerun()
