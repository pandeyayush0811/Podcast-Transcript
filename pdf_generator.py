import os
from datetime import timedelta, datetime
from typing import List, Dict, Any, Optional
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def format_timestamp(milliseconds: int) -> str:
    seconds = max(0, milliseconds // 1000)
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def generate_podcast_pdf(
    source_name: str,
    utterances: List[Dict[str, Any]],
    speakers: List[str],
    speaker_names: Dict[str, str],
    output_pdf_path: str,
    detected_lang: str = "Auto"
) -> str:
    """
    Creates an executive-quality PDF with conversational dual-sided chat bubbles:
    - Speaker 1 (e.g. Host): Left-aligned speech bubble (Ice Blue)
    - Speaker 2 (e.g. Guest): Right-aligned speech bubble (Mint Green)
    """
    doc = SimpleDocTemplate(
        output_pdf_path,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=4
    )

    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#475569')
    )

    spk_header_left = ParagraphStyle(
        'SpkHeaderLeft',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#0369A1'),
        spaceAfter=3
    )

    spk_header_right = ParagraphStyle(
        'SpkHeaderRight',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#15803D'),
        spaceAfter=3
    )

    bubble_text_style = ParagraphStyle(
        'BubbleText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor('#1E293B')
    )

    th_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.white,
        alignment=1
    )

    tb_style = ParagraphStyle(
        'TableBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#0F172A'),
        alignment=1
    )

    elements = []

    # 1. Header Banner
    elements.append(Paragraph("🎙️ Podcast Transcript & Dialogue Report", title_style))
    today_str = datetime.now().strftime("%d %b %Y, %I:%M %p")
    meta_text = f"<b>Source:</b> {source_name}<br/><b>Generated:</b> {today_str} | <b>Detected Language:</b> {detected_lang.upper()} | <b>Total Speakers:</b> {len(speakers)}"
    elements.append(Paragraph(meta_text, meta_style))
    elements.append(Spacer(1, 14))

    # 2. Speaker Statistics Table
    stats_data = [
        [
            Paragraph("Speaker / Character", th_style),
            Paragraph("Dialogue Turns", th_style),
            Paragraph("Speaking Time", th_style),
            Paragraph("Words Spoken", th_style)
        ]
    ]

    for spk_id in speakers:
        display_name = speaker_names.get(spk_id, f"Speaker {spk_id}")
        spk_turns = [u for u in utterances if u["speaker"] == spk_id]
        total_time_ms = sum((u["end"] - u["start"]) for u in spk_turns)
        total_words = sum(len(u["text"].split()) for u in spk_turns)
        time_str = str(timedelta(seconds=int(total_time_ms / 1000)))

        stats_data.append([
            Paragraph(f"<b>{display_name}</b>", tb_style),
            Paragraph(str(len(spk_turns)), tb_style),
            Paragraph(time_str, tb_style),
            Paragraph(f"{total_words:,}", tb_style),
        ])

    stats_table = Table(stats_data, colWidths=[180, 100, 120, 120])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(stats_table)
    elements.append(Spacer(1, 18))

    # Divider
    divider = Table([['']], colWidths=[520], rowHeights=[2])
    divider.setStyle(TableStyle([('LINEBELOW', (0,0), (-1,-1), 1.5, colors.HexColor('#E2E8F0'))]))
    elements.append(divider)
    elements.append(Spacer(1, 14))

    # 3. Conversational Dual-Sided Chat Layout
    # Usable page width: A4 is 595 pt. Margins 36 each side => 595 - 72 = 523 pt.
    bubble_width = 410
    spacer_width = 113

    # Theme colors for up to 4 speakers
    theme_colors = [
        {"bg": '#EFF6FF', "border": '#BFDBFE', "header": spk_header_left, "side": "left"},     # Blue (Left)
        {"bg": '#F0FDF4', "border": '#BBF7D0', "header": spk_header_right, "side": "right"},   # Green (Right)
        {"bg": '#FFFBEB', "border": '#FDE68A', "header": spk_header_left, "side": "left"},     # Amber (Left)
        {"bg": '#FAF5FF', "border": '#E9D5FF', "header": spk_header_right, "side": "right"},   # Purple (Right)
    ]

    for u in utterances:
        spk_id = u["speaker"]
        spk_index = speakers.index(spk_id) if spk_id in speakers else 0
        cfg = theme_colors[spk_index % len(theme_colors)]

        display_name = speaker_names.get(spk_id, f"Speaker {spk_id}")
        time_str = f"[{format_timestamp(u['start'])} - {format_timestamp(u['end'])}]"

        header_para = Paragraph(f"<b>{display_name}</b> <font size=8 color='#64748B'>{time_str}</font>", cfg["header"])
        body_para = Paragraph(u["text"], bubble_text_style)

        card_content = [header_para, Spacer(1, 3), body_para]

        if cfg["side"] == "left":
            # Left aligned bubble
            row = [card_content, '']
            col_widths = [bubble_width, spacer_width]
            cell_coords = (0, 0)
        else:
            # Right aligned bubble
            row = ['', card_content]
            col_widths = [spacer_width, bubble_width]
            cell_coords = (1, 0)

        card_table = Table([row], colWidths=col_widths)
        card_table.setStyle(TableStyle([
            ('BACKGROUND', cell_coords, cell_coords, colors.HexColor(cfg["bg"])),
            ('BOX', cell_coords, cell_coords, 1, colors.HexColor(cfg["border"])),
            ('LEFTPADDING', cell_coords, cell_coords, 10),
            ('RIGHTPADDING', cell_coords, cell_coords, 10),
            ('TOPPADDING', cell_coords, cell_coords, 8),
            ('BOTTOMPADDING', cell_coords, cell_coords, 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))

        elements.append(card_table)
        elements.append(Spacer(1, 8))

    doc.build(elements)
    return output_pdf_path
