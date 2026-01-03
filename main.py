from flask import Flask, request, send_file
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import base64
import binascii

app = Flask(__name__)

# --- Rota de Saúde (Health Check) ---
# Adicionada para o Render saber que a API está online e não dar erro nos logs
@app.route('/')
def home():
    return "API de Simulados Online! Envie um POST para /gerar-simulado", 200

def criar_word_prova(dados):
    doc = Document()
    
    # --- TÍTULO DO SIMULADO ---
    titulo = dados.get('titulo_simulado', 'Simulado SAEB')
    heading = doc.add_heading(titulo, 0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Cabeçalho de Identificação
    doc.add_paragraph('_' * 70)
    doc.add_paragraph('Nome: _________________________________________________ Data: ___/___/___')
    doc.add_paragraph('_' * 70)
    doc.add_paragraph()

    itens = dados.get('itens', [])

    # --- LOOP DAS QUESTÕES ---
    for i, item in enumerate(itens, 1):
        # Tenta pegar código ou nível para o título da questão
        codigo = item.get('descritor_codigo', '')
        nivel = item.get('nivel_dificuldade', '')
        info_extra = f" ({codigo} - {nivel})" if codigo or nivel else ""
        
        doc.add_heading(f"QUESTÃO {i} {info_extra}", level=2)
        
        # 1. Enunciado
        enunciado = item.get('enunciado', '')
        p = doc.add_paragraph(enunciado)
        p.paragraph_format.space_after = Pt(12)

        # 2. Imagem (Tratamento de Base64)
        img_b64 = item.get('imagem_base64')
        if img_b64:
            try:
                # Correção de padding se necessário (evita erros comuns de base64)
                img_b64 = img_b64.strip()
                missing_padding = len(img_b64) % 4
                if missing_padding:
                    img_b64 += '=' * (4 - missing_padding)

                # Decodifica a string Base64 para bytes
                image_data = base64.b64decode(img_b64)
                image_stream = io.BytesIO(image_data)
                
                # Adiciona ao Word (largura fixa de 3.5 polegadas)
                doc.add_picture(image_stream, width=Inches(3.5))
                
                # Centraliza a última imagem adicionada
                last_paragraph = doc.paragraphs[-1] 
                last_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                # Espaço extra após imagem
                doc.add_paragraph() 
            except Exception as e:
                print(f"Erro ao processar imagem da questão {i}: {e}")
                # Opcional: doc.add_paragraph("[Imagem não carregada]")

        # 3. Alternativas
        alts = item.get('alternativas', {})
        # Garante a ordem a, b, c, d, e
        for letra in ['a', 'b', 'c', 'd', 'e']:
            texto_alt = alts.get(letra)
            if texto_alt:
                doc.add_paragraph(f"({letra.upper()}) {texto_alt}")
        
        doc.add_paragraph('-' * 50) # Separador visual

    # --- GABARITO COMENTADO (NOVA PÁGINA) ---
    doc.add_page_break()
    heading_gab = doc.add_heading('GABARITO COMENTADO', level=1)
    heading_gab.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()

    for i, item in enumerate(itens, 1):
        # Pega a letra correta (ex: 'a') e transforma em maiúscula ('A')
        gabarito_letra = str(item.get('gabarito', '?')).lower()
        
        # Procura as justificativas em todos os lugares possíveis
        dic_justificativas = item.get('justificativa_pedagogica') or item.get('justificativa_alternativas') or {}
        
        # Pega o texto da alternativa correta
        texto_justificativa = dic_justificativas.get(gabarito_letra)
        
        # Monta o parágrafo: "Q1: A" em negrito
        p = doc.add_paragraph()
        run = p.add_run(f"Q{i}: {gabarito_letra.upper()}")
        run.bold = True
        run.font.size = Pt(12)
        
        # Se tiver explicação, adiciona na linha de baixo
        if texto_justificativa:
            # Estilo simples para o comentário
            p2 = doc.add_paragraph(f"Comentário: {texto_justificativa}")
            p2.paragraph_format.left_indent = Inches(0.3) # Recuo
            
        doc.add_paragraph() # Espaço entre itens do gabarito

    # --- FINALIZAÇÃO ---
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream

@app.route('/gerar-simulado', methods=['POST'])
def gerar_simulado():
    try:
        dados = request.json
        if not dados:
            return {"erro": "Nenhum dado JSON recebido"}, 400
            
        arquivo_word = criar_word_prova(dados)
        
        # Nome do arquivo dinâmico
        nome_arquivo = f"Simulado_{dados.get('materia', 'Geral')}.docx"
        
        return send_file(
            arquivo_word,
            as_attachment=True,
            download_name=nome_arquivo,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    except Exception as e:
        return {"erro": f"Erro interno: {str(e)}"}, 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
