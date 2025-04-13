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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from config import BOT_TOKEN, WATERMARK_TEXT

# Conversation states
INPUT_TEXT, CONFIRM_DONE = 1, 2

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['text_list'] = []  # Initialize list to store texts
    await update.message.reply_text(
        "Welcome to Smart Text to PDF Bot! 📄\n"
        "Send me text to include in your PDF. Use *text* for bold highlighting.\n"
        "Send multiple messages to build one PDF.\n"
        "Use /done when finished, or /cancel to stop."
    )
    return INPUT_TEXT

async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_text = update.message.text
    context.user_data['text_list'].append(user_text)  # Store text in sequence
    await update.message.reply_text(
        "Text received! Send more text, or use /done to generate the PDF."
    )
    return INPUT_TEXT

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('text_list'):
        await update.message.reply_text(
            "No text provided yet! Send some text, or use /cancel."
        )
        return INPUT_TEXT
    await update.message.reply_text(
        "Ready to generate your PDF with all text? Reply 'yes' to confirm, or 'no' to add more text."
    )
    return CONFIRM_DONE

async def confirm_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    response = update.message.text.lower()
    if response == 'yes':
        user_id = update.message.from_user.id
        pdf_filename = f"output_{user_id}.pdf"
        try:
            # Generate PDF with all stored text
            generate_pdf(context.user_data['text_list'], pdf_filename)
            # Send PDF
            with open(pdf_filename, 'rb') as pdf_file:
                await update.message.reply_document(
                    document=pdf_file,
                    filename="YourSmartPDF.pdf",
                    caption="Here's your smart, colorful PDF with a watermark! 🎉"
                )
            # Clean up
            os.remove(pdf_filename)
            context.user_data['text_list'] = []  # Clear stored text
            await update.message.reply_text(
                "PDF sent! Use /start to create another."
            )
            return ConversationHandler.END
        except Exception as e:
            await update.message.reply_text(f"Error creating PDF: {str(e)}")
            return ConversationHandler.END
    elif response == 'no':
        await update.message.reply_text("Okay, send more text!")
        return INPUT_TEXT
    else:
        await update.message.reply_text("Please reply 'yes' or 'no'.")
        return CONFIRM_DONE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['text_list'] = []  # Clear stored text
    await update.message.reply_text("Operation cancelled. Use /start to begin again.")
    return ConversationHandler.END

def generate_pdf(text_list, filename):
    # Create a PDF document
    doc = SimpleDocTemplate(filename, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    
    # Custom styles
    normal_style = ParagraphStyle(
        name='NormalCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=14,
        textColor=colors.darkblue,
        spaceAfter=12,
    )
    bold_style = ParagraphStyle(
        name='BoldCustom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=14,
        textColor=colors.darkblue,
        spaceAfter=12,
    )
    
    # Content for PDF
    story = []
    
    for text in text_list:
        # Split text into lines to detect lists or paragraphs
        lines = text.split('\n')
        in_list = False
        list_items = []
        
        for line in lines:
            line = line.strip()
            if not line:
                if list_items:
                    story.append(ListFlowable(
                        [ListItem(Paragraph(item, normal_style)) for item in list_items],
                        bulletType='bullet',
                        start='circle'
                    ))
                    list_items = []
                    in_list = False
                story.append(Spacer(1, 12))
                continue
                
            # Detect list items (starting with -, *, or numbers like 1.)
            if re.match(r'^[-*]|\d+\.', line):
                if not in_list:
                    in_list = True
                # Remove list marker
                clean_line = re.sub(r'^[-*]\s|\d+\.\s', '', line)
                list_items.append(format_text(clean_line, normal_style, bold_style))
            else:
                if list_items:
                    story.append(ListFlowable(
                        [ListItem(Paragraph(item, normal_style)) for item in list_items],
                        bulletType='bullet',
                        start='circle'
                    ))
                    list_items = []
                    in_list = False
                # Format paragraph with bold for *text*
                story.append(Paragraph(format_text(line, normal_style, bold_style), normal_style))
        
        # Append any remaining list items
        if list_items:
            story.append(ListFlowable(
                [ListItem(Paragraph(item, normal_style)) for item in list_items],
                bulletType='bullet',
                start='circle'
            ))
    
    # Build PDF with watermark and background
    def add_watermark_and_background(canvas, doc):
        canvas.saveState()
        # Colorful background
        canvas.setFillColor(colors.lightblue)
        canvas.rect(0, 0, letter[0], letter[1], fill=1)
        # Watermark
        canvas.setFont("Helvetica-Bold", 40)
        canvas.setFillColor(colors.red, alpha=0.3)
        canvas.rotate(45)
        canvas.drawString(100, -100, WATERMARK_TEXT)
        canvas.restoreState()

    doc.build(story, onFirstPage=add_watermark_and_background, onLaterPages=add_watermark_and_background)

def format_text(text, normal_style, bold_style):
    # Replace *text* with <b>text</b> for bold formatting
    formatted = re.sub(r'\*(.*?)\*', r'<b>\1</b>', text)
    return formatted.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Something went wrong. Please try again or use /start.")
    print(f"Error: {context.error}")

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            INPUT_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text),
                CommandHandler("done", done),
            ],
            CONFIRM_DONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_done)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)
    print("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
