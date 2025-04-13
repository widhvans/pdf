# bot.py
import os
import re
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
    Table,
    TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from config import BOT_TOKEN, WATERMARK_TEXT

# Register a Unicode font for multilingual support (e.g., Hindi)
pdfmetrics.registerFont(TTFont('NotoSans', 'NotoSans-Regular.ttf'))
pdfmetrics.registerFont(TTFont('NotoSans-Bold', 'NotoSans-Bold.ttf'))

# Conversation state
INPUT_TEXT = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['text_list'] = []  # Store all messages
    context.user_data['pdf_filename'] = f"study_notes_{update.message.from_user.id}.pdf"
    await update.message.reply_text(
        "Welcome to StudyBuddy PDF Bot! 📚✨\n"
        "Send your study notes (in any language, like Hindi or English).\n"
        "Use *text* for highlights, # for headings, or - for lists.\n"
        "Each message builds one beautiful PDF. Use /finish to get it, or /cancel to stop."
    )
    return INPUT_TEXT

async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_text = update.message.text
    context.user_data['text_list'].append(user_text)  # Append in sequence
    
    # Generate or update PDF
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
    
    # Send the final PDF
    try:
        with open(pdf_filename, 'rb') as pdf_file:
            await update.message.reply_document(
                document=pdf_file,
                filename="YourStudyNotes.pdf",
                caption="Your stunning study notes are ready! 📝✨ Start again with /start."
            )
        os.remove(pdf_filename)  # Clean up
        context.user_data['text_list'] = []  # Clear data
    except Exception as e:
        await update.message.reply_text(f"Error sending PDF: {str(e)}")
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pdf_filename = context.user_data.get('pdf_filename')
    if os.path.exists(pdf_filename):
        os.remove(pdf_filename)  # Clean up
    context.user_data['text_list'] = []  # Clear data
    await update.message.reply_text("Cancelled. Start fresh with /start! 🚀")
    return ConversationHandler.END

def generate_pdf(text_list, filename):
    # Create PDF
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=0.75*inch,
        rightMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    styles = getSampleStyleSheet()
    
    # Custom styles for study notes
    normal_style = ParagraphStyle(
        name='NormalCustom',
        fontName='NotoSans',
        fontSize=12,
        leading=16,
        textColor=colors.black,
        spaceAfter=10,
        alignment=0,  # Left-aligned
    )
    bold_style = ParagraphStyle(
        name='BoldCustom',
        fontName='NotoSans-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.black,
        spaceAfter=10,
    )
    heading_style = ParagraphStyle(
        name='HeadingCustom',
        fontName='NotoSans-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.darkblue,
        spaceAfter=12,
        spaceBefore=12,
    )
    highlight_style = ParagraphStyle(
        name='HighlightCustom',
        fontName='NotoSans-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.darkred,
        backColor=colors.lightyellow,
        spaceAfter=10,
    )
    
    # Build content
    story = []
    
    for text in text_list:
        lines = text.split('\n')
        in_list = False
        list_items = []
        
        for line in lines:
            line = line.strip()
            if not line:
                if list_items:
                    story.append(ListFlowable(
                        [ListItem(Paragraph(item, normal_style), leftIndent=10) for item in list_items],
                        bulletType='bullet',
                        start='square',
                        leftIndent=20,
                    ))
                    list_items = []
                    in_list = False
                story.append(Spacer(1, 8))
                continue
            
            # Detect headings (starting with #)
            if line.startswith('#'):
                clean_line = line[1:].strip()
                story.append(Paragraph(format_text(clean_line, normal_style, bold_style, highlight_style), heading_style))
                continue
            
            # Detect list items (-, *, or numbers)
            if re.match(r'^[-*]|\d+\.', line):
                if not in_list:
                    in_list = True
                clean_line = re.sub(r'^[-*]\s|\d+\.\s', '', line)
                list_items.append(format_text(clean_line, normal_style, bold_style, highlight_style))
            else:
                if list_items:
                    story.append(ListFlowable(
                        [ListItem(Paragraph(item, normal_style), leftIndent=10) for item in list_items],
                        bulletType='bullet',
                        start='square',
                        leftIndent=20,
                    ))
                    list_items = []
                    in_list = False
                # Highlight entire line if it’s an “answer” (e.g., *text* or standalone)
                formatted_line = format_text(line, normal_style, bold_style, highlight_style)
                story.append(Paragraph(formatted_line, highlight_style if '*' in line else normal_style))
        
        if list_items:
            story.append(ListFlowable(
                [ListItem(Paragraph(item, normal_style), leftIndent=10) for item in list_items],
                bulletType='bullet',
                start='square',
                leftIndent=20,
            ))
    
    # Custom canvas for watermarks
    def add_watermarks(canvas, doc):
        canvas.saveState()
        # White background
        canvas.setFillColor(colors.white)
        canvas.rect(0, 0, letter[0], letter[1], fill=1)
        
        # Border watermark (small, repeating)
        canvas.setFont("NotoSans", 8)
        canvas.setFillColor(colors.grey, alpha=0.5)
        text_width = pdfmetrics.stringWidth(WATERMARK_TEXT, "NotoSans", 8)
        spacing = 10
        # Top and bottom borders
        for x in range(-50, int(letter[0]), int(text_width + spacing)):
            canvas.drawString(x, letter[1] - 15, WATERMARK_TEXT)
            canvas.drawString(x, 5, WATERMARK_TEXT)
        # Left and right borders (vertical)
        canvas.rotate(90)
        for y in range(-50, int(letter[1]), int(text_width + spacing)):
            canvas.drawString(y, -letter[0] + 15, WATERMARK_TEXT)
            canvas.drawString(y, -5, WATERMARK_TEXT)
        canvas.rotate(-90)
        
        # Centered watermark
        canvas.setFont("NotoSans", 40)
        canvas.setFillColor(colors.grey, alpha=0.1)
        canvas.rotate(45)
        canvas.drawCentredString(letter[0]/2, -letter[1]/2, WATERMARK_TEXT)
        
        canvas.restoreState()
    
    # Add header/footer
    def add_header_footer(canvas, doc):
        add_watermarks(canvas, doc)
        canvas.saveState()
        canvas.setFont("NotoSans", 10)
        canvas.setFillColor(colors.grey)
        canvas.drawString(0.75*inch, 0.5*inch, f"StudyBuddy Notes | Page {doc.page}")
        canvas.drawRightString(letter[0] - 0.75*inch, 0.5*inch, "Created with StudyBuddy Bot")
        canvas.restoreState()
    
    doc.build(story, onFirstPage=add_header_footer, onLaterPages=add_header_footer)

def format_text(text, normal_style, bold_style, highlight_style):
    # Highlight *text* in bold and red
    formatted = re.sub(r'\*(.*?)\*', r'<font name="NotoSans-Bold" color="darkred">\1</font>', text)
    # Escape special characters
    formatted = formatted.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
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
