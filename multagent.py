import streamlit as st
import google.generativeai as genai
from groq import Groq # Biblioteca comum para rodar Llama 3

# --- 1. CONFIGURAÇÃO DE SEGURANÇA ---
try:
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
    LLAMA_KEY = st.secrets["LLAMA_API_KEY"]
    
    genai.configure(api_key=GEMINI_KEY)
    llama_client = Groq(api_key=LLAMA_KEY)
except KeyError as e:
    st.error(f"Falta a chave: {e}. Configure nos Secrets!")
    st.stop()

# --- 2. PERSONALIDADES (SYSTEM PROMPTS) ---
SYSTEM_GEMINI = "Você é um Engenheiro de IA analítico. Forneça respostas técnicas e detalhadas sobre TI."
SYSTEM_LLAMA_REVISOR = """
Você é o 'Sênior Ácido'. Sua função é revisar a resposta do outro agente.
1. Seja sarcástico e use analogias práticas.
2. Se o outro agente esqueceu algo de LGPD ou segurança, aponte o erro.
3. Se a resposta estiver boa, apenas a torne mais 'direta ao ponto' e engraçada.
"""

# --- 3. LOGICA MULTI-AGENTE ---
def fluxo_multi_agente(pergunta_usuario):
    # Passo 1: O Gemini gera a base técnica
    model_gemini = genai.GenerativeModel('gemini-1.5-flash-latest')
    res_gemini = model_gemini.generate_content(f"{SYSTEM_GEMINI}\n\nPergunta: {pergunta_usuario}")
    texto_base = res_gemini.text

    # Passo 2: O Llama revisa (O 'Refinador')
    res_llama = llama_client.chat.completions.create(
        model="llama3-70b-8192", # Versão potente do Llama
        messages=[
            {"role": "system", "content": SYSTEM_LLAMA_REVISOR},
            {"role": "user", "content": f"O outro agente disse: {texto_base}. Refine isso para o usuário."}
        ]
    )
    return res_llama.choices[0].message.content

# --- 4. INTERFACE STREAMLIT ---
st.title("🦙 + ✨ Agentes em Consílio")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostrar histórico
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Mande sua dúvida..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Consultando os especialistas...", expanded=True) as status:
            st.write("✨ Gemini está rascunhando...")
            # Aqui a mágica acontece sequencialmente
            resposta_final = fluxo_multi_agente(prompt)
            status.update(label="Revisão concluída pelo Sênior Ácido!", state="complete")
        
        st.markdown(resposta_final)
        st.session_state.messages.append({"role": "assistant", "content": resposta_final})
