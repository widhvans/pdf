# bot.py
import os
import re
import io
from PIL import Image, ImageDraw, ImageFont
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    ListFlowable,
    ListItem,
    PageBreak,
    Image as ReportlabImage,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from config import BOT_TOKEN, WATERMARK_TEXT

# Hindi detection
def is_hindi_text(text):
    return any(0x0900 <= ord(char) <= 0x097F for char in text)

# Render text as image for Hindi
def text_to_image(text, font_size, is_bold=False, is_highlight=False):
    try:
        # Use system font rendering via Pillow
        font_path = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
        if not os.path.exists(font_path):
            font_path = None  # Let Pillow find a default
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
        
        # Calculate text size
        dummy_draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
        bbox = dummy_draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Create image
        padding = 5
        img_width = text_width + 2 * padding
        img_height = text_height + 2 * padding
        img = Image.new('RGBA', (int(img_width), int(img_height)), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        
        # Background for highlights
        if is_highlight:
            draw.rectangle(
                [(0, 0), (img_width, img_height)],
                fill=(255, 255, 150, 128)  # Light yellow, semi-transparent
            )
        
        # Draw text
        text_color = (200, 0, 0) if is_highlight else (0, 0, 0)  # Red for highlights, black otherwise
        draw.text((padding, padding), text, font=font, fill=text_color)
        
        # Save to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        return img_bytes, img_width / 72, img_height / 72  # Convert pixels to points
    except Exception as e:
        print(f"Text-to-image failed: {e}")
        return None, 0, 0

# Hindi study keywords
HINDI_KEYWORDS = {
    'परिभाषा': 'definition',
    'उदाहरण': 'example',
    'महत्वपूर्ण': 'important',
    'प्रश्न': 'question',
    'उत्तर': 'answer',
    'नोट्स': 'notes',
    'अध्याय': 'chapter',
    'विषय': 'topic',
    'सारांश': 'summary',
    'प्रमुख': 'key',
    'सूत्र': 'formula',
    'विशेष': 'special',
    'अभ्यास': 'exercise',
}

# Conversation state
INPUT_TEXT = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['text_list'] = []
    context.user_data['pdf_filename'] = f"study_notes_{update.message.from_user.id}.pdf"
    await update.message.reply_text(
        "Welcome to StudyBuddy PDF Bot! 📚✨\n"
        "Send your study notes in any language (e.g., Hindi, English).\n"
        "Use *text* for highlights, # for headings, - for lists, or Hindi keywords like 'परिभाषा'.\n"
        "Each message builds one PDF. Use /finish to download, or /cancel to stop."
    )
    return INPUT_TEXT

async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_text = update.message.text
    context.user_data['text_list'].append(user_text)
    
    try:
        generate_pdf(context.user_data['text_list'], context.user_data['pdf_filename'])
        await update.message.reply_text("Added to your PDF! Keep sending notes or use /finish to download.")
    except Exception as e:
        await update.message.reply_text(f"Error updating PDF: {str(e)}")
    
    return INPUT_TEXT

async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pdf_filename = context.user_data.get('pdf_filename')
    if not context.user_data.get('text_list') or not os.path.exists(pdf_filename):
        await update.message.reply_text("No notes added yet! Send some text or use /cancel.")
        return INPUT_TEXT
    
    try:
        with open(pdf_filename, 'rb') as pdf_file:
            await update.message.reply_document(
                document=pdf_file,
                filename="YourStudyNotes.pdf",
                caption="Your stunning study notes are ready! 📝✨ Start again with /start."
            )
        os.remove(pdf_filename)
        context.user_data['text_list'] = []
    except Exception as e:
        await update.message.reply_text(f"Error sending PDF: {str(e)}")
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pdf_filename = context.user_data.get('pdf_filename')
    if os.path.exists(pdf_filename):
        os.remove(pdf_filename)
    context.user_data['text_list'] = []
    await update.message.reply_text("Cancelled. Start fresh with /start! 🚀")
    return ConversationHandler.END

def generate_pdf(text_list, filename):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=1*inch,
        rightMargin=1*inch,
        topMargin=1*inch,
        bottomMargin=1*inch,
        title="अध्ययन नोट्स",
        author="StudyBuddy Bot"
    )
    styles = getSampleStyleSheet()
    
    # Dynamic font size
    total_chars = sum(len(text) for text in text_list)
    base_font_size = 18 if total_chars < 300 else 16 if total_chars < 600 else 14
    if any(is_hindi_text(text) for text in text_list):
        base_font_size += 2  # Larger for Devanagari
    
    normal_style = ParagraphStyle(
        name='NormalCustom',
        fontName='Helvetica',
        fontSize=base_font_size,
        leading=base_font_size + 8,
        textColor=colors.black,
        spaceAfter=14,
        alignment=0,
    )
    bold_style = ParagraphStyle(
        name='BoldCustom',
        fontName='Helvetica-Bold',
        fontSize=base_font_size,
        leading=base_font_size + 8,
        textColor=colors.black,
        spaceAfter=14,
    )
    heading_style = ParagraphStyle(
        name='HeadingCustom',
        fontName='Helvetica-Bold',
        fontSize=base_font_size + 6,
        leading=base_font_size + 12,
        textColor=colors.navy,
        spaceAfter=16,
        spaceBefore=16,
    )
    highlight_style = ParagraphStyle(
        name='HighlightCustom',
        fontName='Helvetica-Bold',
        fontSize=base_font_size,
        leading=base_font_size + 8,
        textColor=colors.darkred,
        backColor=colors.lightyellow,
        spaceAfter=14,
        borderPadding=5,
        borderWidth=1.2,
        borderColor=colors.grey,
    )
    cover_style = ParagraphStyle(
        name='CoverCustom',
        fontName='Helvetica-Bold',
        fontSize=34,
        leading=40,
        textColor=colors.darkblue,
        alignment=1,
        spaceAfter=28,
    )
    
    # Cover page
    cover_text = "अध्ययन नोट्स | Study Notes"
    if is_hindi_text(cover_text):
        img_bytes, img_width, img_height = text_to_image(cover_text, int(34 * 1.5), is_bold=True)
        if img_bytes:
            story = [Spacer(1, 2.5*inch), ReportlabImage(img_bytes, img_width, img_height)]
        else:
            story = [Spacer(1, 2.5*inch), Paragraph(cover_text, cover_style)]
    else:
        story = [Spacer(1, 2.5*inch), Paragraph(cover_text, cover_style)]
    
    story.append(Paragraph("Created with StudyBuddy Bot", normal_style))
    story.append(PageBreak())
    
    # Content
    section_number = 0
    for i, text in enumerate(text_list):
        section_number += 1
        lines = text.split('\n')
        in_list = False
        list_items = []
        
        for line in lines:
            line = line.strip()
            if not line:
                if list_items:
                    story.append(ListFlowable(
                        [ListItem(Paragraph(item, normal_style), leftIndent=12) for item in list_items],
                        bulletType='bullet',
                        start='circle',
                        leftIndent=22,
                    ))
                    list_items = []
                    in_list = False
                story.append(Spacer(1, 12))
                continue
            
            # Detect headings and keywords
            is_heading = line.startswith('#')
            clean_line = line[1:].strip() if is_heading else line
            for keyword in HINDI_KEYWORDS:
                if clean_line.lower().startswith(keyword.lower()):
                    is_heading = True
                    clean_line = f"{keyword} ({HINDI_KEYWORDS[keyword]})"
                    break
            
            if is_heading:
                if is_hindi_text(clean_line):
                    img_bytes, img_width, img_height = text_to_image(clean_line, int((base_font_size + 6) * 1.5), is_bold=True)
                    if img_bytes:
                        story.append(ReportlabImage(img_bytes, img_width, img_height))
                    else:
                        story.append(Paragraph(format_text(clean_line, normal_style, bold_style, highlight_style), heading_style))
                else:
                    story.append(Paragraph(format_text(clean_line, normal_style, bold_style, highlight_style), heading_style))
                continue
            
            # Detect lists
            if re.match(r'^[-*]|\d+\.|१\.|[क-ह]\.', line):
                if not in_list:
                    in_list = True
                clean_line = re.sub(r'^[-*]\s|\d+\.\s|१\.\s|[क-ह]\.\s', '', line)
                list_items.append(clean_line)
            else:
                if list_items:
                    rendered_items = []
                    for item in list_items:
                        if is_hindi_text(item):
                            img_bytes, img_width, img_height = text_to_image(
                                item, int(base_font_size * 1.5), is_highlight='*' in item
                            )
                            if img_bytes:
                                rendered_items.append(ReportlabImage(img_bytes, img_width, img_height))
                            else:
                                rendered_items.append(Paragraph(format_text(item, normal_style, bold_style, highlight_style), normal_style))
                        else:
                            rendered_items.append(Paragraph(format_text(item, normal_style, bold_style, highlight_style), normal_style))
                    story.append(ListFlowable(
                        [ListItem(item, leftIndent=12) for item in rendered_items],
                        bulletType='bullet',
                        start='circle',
                        leftIndent=22,
                    ))
                    list_items = []
                    in_list = False
                
                # Render line
                is_highlight = any(keyword.lower() in line.lower() for keyword in HINDI_KEYWORDS) or '*' in line
                if is_hindi_text(line):
                    img_bytes, img_width, img_height = text_to_image(line, int(base_font_size * 1.5), is_highlight=is_highlight)
                    if img_bytes:
                        story.append(ReportlabImage(img_bytes, img_width, img_height))
                    else:
                        story.append(Paragraph(format_text(line, normal_style, bold_style, highlight_style), highlight_style if is_highlight else normal_style))
                else:
                    story.append(Paragraph(format_text(line, normal_style, bold_style, highlight_style), highlight_style if is_highlight else normal_style))
        
        if list_items:
            rendered_items = []
            for item in list_items:
                if is_hindi_text(item):
                    img_bytes, img_width, img_height = text_to_image(
                        item, int(base_font_size * 1.5), is_highlight='*' in item
                    )
                    if img_bytes:
                        rendered_items.append(ReportlabImage(img_bytes, img_width, img_height))
                    else:
                        rendered_items.append(Paragraph(format_text(item, normal_style, bold_style, highlight_style), normal_style))
                else:
                    rendered_items.append(Paragraph(format_text(item, normal_style, bold_style, highlight_style), normal_style))
            story.append(ListFlowable(
                [ListItem(item, leftIndent=12) for item in rendered_items],
                bulletType='bullet',
                start='circle',
                leftIndent=22,
            ))
        
        # Section divider with number
        if i < len(text_list) - 1:
            story.append(Spacer(1, 12))
            story.append(Paragraph(f"<hr width='80%' color='silver'/> Section {section_number}", normal_style))
    
    # Watermarks and header/footer
    def add_watermarks(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.white)
        canvas.rect(0, 0, letter[0], letter[1], fill=1)
        
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(colors.grey, alpha=0.3)
        text_width = canvas.stringWidth(WATERMARK_TEXT, 'Helvetica', 7)
        spacing = 15
        for x in range(-50, int(letter[0]), int(text_width + spacing)):
            canvas.drawString(x, letter[1] - 20, WATERMARK_TEXT)
            canvas.drawString(x, 10, WATERMARK_TEXT)
        canvas.rotate(90)
        for y in range(-50, int(letter[1]), int(text_width + spacing)):
            canvas.drawString(y, -letter[0] + 20, WATERMARK_TEXT)
            canvas.drawString(y, -10, WATERMARK_TEXT)
        canvas.rotate(-90)
        
        canvas.setFont('Helvetica', 34)
        canvas.setFillColor(colors.grey, alpha=0.07)
        canvas.rotate(45)
        canvas.drawCentredString(letter[0]/2, -letter[1]/2, WATERMARK_TEXT)
        
        canvas.restoreState()
    
    def add_header_footer(canvas, doc):
        add_watermarks(canvas, doc)
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.grey)
        canvas.drawString(1*inch, 0.5*inch, f"StudyBuddy Notes | Page {doc.page}")
        canvas.drawRightString(letter[0] - 1*inch, 0.5*inch, "Created with StudyBuddy Bot")
        canvas.restoreState()
    
    doc.build(story, onFirstPage=add_header_footer, onLaterPages=add_header_footer)

def format_text(text, normal_style, bold_style, highlight_style):
    formatted = re.sub(r'\*(.*?)\*', r'<b>\1</b>', text)
    formatted = formatted.replace('&', '&').replace('<', '<').replace('>', '>')
    return formatted

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Oops, something broke! Try again or use /start. 📚")
    print(f"Error: {context.error}")

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            INPUT_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text),
                CommandHandler("finish", finish),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)
    print("StudyBuddy Bot is running... 🚀")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
