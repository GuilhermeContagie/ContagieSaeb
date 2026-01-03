import json
import base64
import matplotlib
matplotlib.use('Agg') # Backend para servidor
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from io import BytesIO
from fastapi.responses import StreamingResponse
import traceback # Importante para ver o erro real

app = FastAPI()

class ItemList(BaseModel):
    itens: List[Dict[str, Any]]
    titulo_simulado: Optional[str] = "SIMULADO SAEB"

# --- FUNÇÃO MATPLOTLIB (Mantenha a mesma lógica visual anterior) ---
def gerar_matplotlib(categoria, dados):
    fig, ax = plt.subplots(figsize=(6, 3.5), dpi=150)
    ax.set_axis_off()
    
    try:
        if categoria == "GRAFICO_BARRAS":
            ax.set_axis_on()
            colors = ['#5DADE2', '#F4D03F', '#AF7AC5', '#EC7063']
            valores = dados.get('valores', [])
            labels = dados.get('labels', [])
            if valores and labels:
                bars = ax.bar(labels, valores, color=colors[:len(labels)], edgecolor='black')
                ax.bar_label(bars, padding=3)
                ax.set_title(dados.get('titulo', ''), fontsize=10, fontweight='bold')
                ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
        
        # ... (Mantenha os outros gráficos: TABELA, RETA, RELOGIO, BLOCOS, GEOMETRIA aqui) ...
        # Se quiser economizar espaço aqui, copie os blocos 'elif' do código anterior
        # O erro não está aqui, está na montagem do Word ou Base64.
        
        else:
            ax.text(0.5, 0.5, "Visualização Gerada", ha='center')

    except Exception as e:
        ax.text(0.5, 0.5, f"Erro visual: {str(e)}", ha='center', color='red', fontsize=8)

    img_buffer = BytesIO()
    plt.tight_layout()
    plt.savefig(img_buffer, format='png', bbox_inches='tight')
    plt.close(fig)
    img_buffer.seek(0)
    return img_buffer

# --- FUNÇÃO DE WORD (Com Correção de Base64) ---
def criar_word_prova(data):
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Arial'; style.font.size = Pt(11)

    # Título
    p_head = doc.add_paragraph()
    p_head.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_h = p_head.add_run(str(data.titulo_simulado))
    run_h.bold = True; run_h.font.size = Pt(14)
    doc.add_paragraph("_" * 70)
    doc.add_paragraph("Nome: _________________________________________________ Data: ___/___/___")
    doc.add_paragraph("_" * 70)

    for i, item in enumerate(data.itens):
        # Enunciado
        p_q = doc.add_paragraph()
        run_q = p_q.add_run(f"QUESTÃO {i+1} ")
        run_q.bold = True
        desc = item.get('descritor_codigo', 'NA')
        niv = item.get('nivel_dificuldade', '')
        run_desc = p_q.add_run(f"({desc} - {niv})")
        run_desc.font.size = Pt(8); run_desc.font.color.rgb = RGBColor(100,100,100)
        
        doc.add_paragraph(item.get('enunciado', 'Questão sem enunciado'))

        # --- PROCESSAMENTO DE IMAGEM ---
        tipo_vis = item.get('tipo_visual_categoria', 'NENHUM')
        img_stream = None
        
        # 1. Matplotlib
        if tipo_vis == 'MATPLOTLIB' and item.get('dados_visual_python'):
            try:
                img_stream = gerar_matplotlib(tipo_vis, item['dados_visual_python'])
            except Exception as e:
                print(f"Erro Matplotlib Q{i}: {e}")
        
        # 2. IA Generativa (A CORREÇÃO ESTÁ AQUI)
        elif tipo_vis == 'IA_GENERATIVA' and item.get('imagem_base64'):
            try:
                b64_str = item['imagem_base64']
                # Limpeza: Se vier com cabeçalho "data:image/...", removemos.
                if "," in b64_str:
                    b64_str = b64_str.split(",")[1]
                
                image_data = base64.b64decode(b64_str)
                img_stream = BytesIO(image_data)
            except Exception as e:
                print(f"Erro Base64 Q{i}: {e}")
                # Não quebra o código, apenas segue sem imagem

        if img_stream:
            try:
                doc.add_picture(img_stream, width=Inches(3.5))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            except Exception as e:
                print(f"Erro ao inserir imagem no Word: {e}")
            doc.add_paragraph("")

        # Alternativas
        letras = ['a', 'b', 'c', 'd', 'e']
        alts = item.get('alternativas', {})
        if alts:
            for l in letras:
                if l in alts:
                    doc.add_paragraph(f"({l.upper()}) {alts[l]}")
        
        doc.add_paragraph("-" * 50)

    # Gabarito
    doc.add_page_break()
    doc.add_heading("GABARITO COMENTADO", 0)
    for i, item in enumerate(data.itens):
        doc.add_paragraph(f"Q{i+1}: {item.get('gabarito', '').upper()}", style='List Bullet')
        
    file_stream = BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream

@app.post("/gerar-simulado")
async def api_endpoint(data: ItemList):
    try:
        arquivo = criar_word_prova(data)
        return StreamingResponse(
            arquivo,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": "attachment; filename=simulado_saeb.docx"}
        )
    except Exception as e:
        # ISSO VAI MOSTRAR O ERRO REAL NO N8N
        error_msg = traceback.format_exc()
        print(error_msg) # Aparece no log do Render
        raise HTTPException(status_code=500, detail=error_msg)
