from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
import os

def get_cyrillic_font():
    """Attempts to register a font that supports Cyrillic."""
    possible_fonts = [
        ('DejaVu', 'DejaVuSans.ttf'),
        ('Arial', 'C:/Windows/Fonts/arial.ttf'),
        ('Arial', '/usr/share/fonts/truetype/msttcorefonts/Arial.ttf'),
        ('LiberationSans', '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'),
    ]

    for name, path in possible_fonts:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                return name
            except Exception:
                continue
    
    # Fallback if no font found (likely will cause squares for Cyrillic)
    return 'Helvetica'

FONT_NAME = get_cyrillic_font()

def generate_child_report(file_path, child_data, parents_data, health_data, vaccine_data):
    """
    Generates a PDF report for a specific child.
    """
    doc = SimpleDocTemplate(file_path, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()

    # Custom styles
    styles.add(ParagraphStyle(name='MainTitle', fontName=FONT_NAME, fontSize=18, alignment=TA_CENTER, spaceAfter=20))
    styles.add(ParagraphStyle(name='SubTitle', fontName=FONT_NAME, fontSize=14, spaceAfter=10))
    styles.add(ParagraphStyle(name='Body', fontName=FONT_NAME, fontSize=10, spaceAfter=5))

    # --- Header ---
    story.append(Paragraph("Медицинская карта воспитанника", styles['MainTitle']))
    story.append(Spacer(1, 20))

    # --- Child Info ---
    # child_data is a sqlite3.Row object, so we can access by key or index
    c_name = child_data['full_name']
    c_dob = child_data['birth_date']
    c_group = child_data['group_name']
    c_allergy = child_data['allergies']

    story.append(Paragraph(f"ФИО: {c_name}", styles['Body']))
    story.append(Paragraph(f"Дата рождения: {c_dob}", styles['Body']))
    story.append(Paragraph(f"Группа: {c_group}", styles['Body']))
    if c_allergy:
        story.append(Paragraph(f"Аллергии: {c_allergy}", styles['Body']))
    story.append(Spacer(1, 20))

    # --- Parents Info ---
    story.append(Paragraph("Родители", styles['SubTitle']))
    if parents_data:
        p_data = [["ФИО", "Телефон"]]
        for p in parents_data:
            p_data.append([p['full_name'], p['phone']])
        
        t = Table(p_data, colWidths=[300, 150])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('FONTNAME', (0,0), (-1,-1), FONT_NAME),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("Нет данных", styles['Body']))
    
    story.append(Spacer(1, 20))

    # --- Health Records ---
    story.append(Paragraph("История здоровья", styles['SubTitle']))
    if health_data:
        h_data = [["Дата", "Тип", "Описание", "Диагноз"]]
        for h in health_data:
            # Map type if needed, or use raw
            h_data.append([
                h['record_date'], 
                h['record_type'], 
                h['description'][:50] if h['description'] else '', 
                h['diagnosis'] or ''
            ])
        
        t = Table(h_data, colWidths=[70, 80, 200, 100])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('FONTNAME', (0,0), (-1,-1), FONT_NAME),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("Нет записей", styles['Body']))
        
    story.append(Spacer(1, 20))

    # --- Vaccinations ---
    story.append(Paragraph("Карта прививок", styles['SubTitle']))
    if vaccine_data:
        v_data = [["Вакцина", "Дата", "Статус"]]
        for v in vaccine_data:
            v_data.append([v['vaccine_name'], v['date_administered'], v['status']])
            
        t = Table(v_data, colWidths=[200, 100, 100])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('FONTNAME', (0,0), (-1,-1), FONT_NAME),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("Нет данных", styles['Body']))

    try:
        doc.build(story)
    except PermissionError:
        raise PermissionError("Невозможно записать файл. Закройте PDF, если он открыт.")
