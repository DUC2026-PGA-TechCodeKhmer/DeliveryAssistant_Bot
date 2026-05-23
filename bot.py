import logging
import re
import cv2
import easyocr
import numpy as np
import os
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler

# ហៅការរៀបចំពីឯកសារ keep_alive.py (សម្រាប់ hosting 24h)
from keep_alive import keep_alive

# អានទិន្នន័យពីឯកសារ .env (សម្រាប់ពេលសាកល្បងលើកុំព្យូទ័រ)
load_dotenv()

# --- ទាញយកព័ត៌មានពី Environment Variables ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
BOT_USERNAME = os.getenv('BOT_USERNAME') 
GROUP_CHAT_ID = os.getenv('GROUP_CHAT_ID')

# កំណត់ EasyOCR សម្រាប់អានអក្សរពីរូបភាព
reader = easyocr.Reader(['en'], gpu=False)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ១. នៅពេលអ្នកដឹកឥវ៉ាន់ថតរូបផ្ញើឱ្យ Bot
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    
    nparr = np.frombuffer(photo_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    await update.message.reply_text("🔎 កំពុងចាប់យកលេខទូរស័ព្ទ...")

    results = reader.readtext(image)
    raw_text = "".join([res[1] for res in results])
    cleaned_text = re.sub(r'\D', '', raw_text)
    phone_match = re.search(r'\d{9,10}', cleaned_text)

    if phone_match:
        detected_phone = phone_match.group()
        
        # បង្កើត Link សម្រាប់ផ្ញើទៅអតិថិជន ភ្ជាប់ជាមួយលេខទូរស័ព្ទពីក្នុងរូបភាព
        customer_bot_link = f"https://t.me/{BOT_USERNAME}?start={detected_phone}"
        
        formatted_phone = "855" + detected_phone[1:] if detected_phone.startswith('0') else detected_phone
        direct_chat_link = f"https://t.me/+{formatted_phone}"

        # ផ្ញើព័ត៌មានចូល Group សម្រាប់ Admin
        keyboard = [
            [InlineKeyboardButton("💬 បើក Chat ជាមួយគាត់", url=direct_chat_link)],
            [InlineKeyboardButton("🔗 ចម្លង Link ផ្ញើឱ្យគាត់", url=f"https://t.me/share/url?url={customer_bot_link}&text=សូមចុច Link នេះរួចផ្ញើទីតាំងឱ្យខ្ញុំផង")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_photo(
            chat_id=GROUP_CHAT_ID,
            photo=update.message.photo[-1].file_id,
            caption=f"📦 **មានឥវ៉ាន់ថ្មី!**\n📱 លេខទូរស័ព្ទលើប្រអប់៖ `{detected_phone}`\n\nសូមប្រើប៊ូតុងខាងក្រោមដើម្បីទាក់ទងទៅគាត់៖",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        await update.message.reply_text(f"✅ រកឃើញលេខ {detected_phone} និងបានបញ្ជូនទៅ Group។")
    else:
        await update.message.reply_text("❌ រកមិនឃើញលេខទូរស័ព្ទទេ។")

# ២. នៅពេលអតិថិជនចុច Link ចូលមកកាន់ Bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        # រក្សាទុកលេខទូរស័ព្ទដែលបានមកពីកូដថតរូប
        expected_phone = context.args[0]
        context.user_data['expected_phone'] = expected_phone
        
        # បង្កើតប៊ូតុងសុំផ្ទៀងផ្ទាត់លេខទូរស័ព្ទ Telegram របស់គាត់ជាមុនសិន
        keyboard = [[KeyboardButton("🔐 ចុចទីនេះដើម្បីផ្ទៀងផ្ទាត់លេខទូរស័ព្ទ", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            f"សូមស្វាគមន៍! ដើម្បីសុវត្ថិភាព និងធានាថាអ្នកជាម្ចាស់ឥវ៉ាន់ពិតប្រាកដ\n"
            f"សូមចុចប៊ូតុងខាងក្រោមដើម្បីផ្ទៀងផ្ទាត់លេខទូរស័ព្ទ Telegram របស់អ្នក៖",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("សូមស្វាគមន៍! Bot នេះប្រើសម្រាប់តែទទួលទីតាំងដឹកឥវ៉ាន់ប៉ុណ្ណោះ។")

# ៣. ពិនិត្យមើលលេខទូរស័ព្ទរបស់គាត់ (Contact Verification)
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    expected_phone = context.user_data.get('expected_phone')

    if contact and expected_phone:
        # សម្អាតលេខទូរស័ព្ទរបស់ Telegram ឱ្យនៅសល់តែលេខសុទ្ធ (ព្រោះពេលខ្លះវាមានសញ្ញា +)
        user_phone = re.sub(r'\D', '', contact.phone_number)
        
        # បម្លែងលេខទូរស័ព្ទដែលរំពឹងទុក (Expected) ឱ្យទៅជាទម្រង់ 855 ដូចគ្នាដើម្បីងាយស្រួលប្រៀបធៀប
        formatted_expected = "855" + expected_phone[1:] if expected_phone.startswith('0') else expected_phone
        formatted_expected = re.sub(r'\D', '', formatted_expected)

        # ⚡ ដំណាក់កាលផ្ទៀងផ្ទាត់ (Verification)
        if user_phone == formatted_expected:
            # បើលេខត្រូវគ្នា៖ បង្កើតប៊ូតុងឱ្យគាត់ផ្ញើ Location
            keyboard = [[KeyboardButton("📍 ចុចទីនេះដើម្បីផ្ញើទីតាំង", request_location=True)]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            
            await update.message.reply_text(
                "✅ ការផ្ទៀងផ្ទាត់ជោគជ័យ! អ្នកពិតជាម្ចាស់ឥវ៉ាន់ពិតប្រាកដមែន។\n"
                "សូមចុចប៊ូតុងខាងក្រោមដើម្បីផ្ញើទីតាំងបច្ចុប្បន្នរបស់អ្នក៖",
                reply_markup=reply_markup
            )
        else:
            # បើលេខមិនត្រូវគ្នា៖ បដិសេធចោលភ្លាម
            await update.message.reply_text(
                "❌ ការផ្ទៀងផ្ទាត់បរាជ័យ! លេខទូរស័ព្ទ Telegram របស់អ្នក មិនត្រូវគ្នានឹងលេខទូរស័ព្ទនៅលើកញ្ចប់ឥវ៉ាន់ឡើយ។\n"
                "អ្នកមិនអាចផ្ញើទីតាំងសម្រាប់សេវាកម្មនេះបានទេ។",
                reply_markup=ReplyKeyboardRemove()
            )

# ៤. នៅពេលអតិថិជនផ្ញើ Location (បន្ទាប់ពីផ្ទៀងផ្ទាត់ជាប់)
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location = update.message.location
    expected_phone = context.user_data.get('expected_phone', 'មិនស្គាល់លេខ')
    
    if location:
        maps_url = f"https://www.google.com/maps?q={location.latitude},{location.longitude}"
        
        # ផ្ញើទៅ Group វិញ
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=f"📍 **ទទួលបានទីតាំងពីអតិថិជនពិតប្រាកដ!**\n📱 លេខអតិថិជន៖ `{expected_phone}`\n🔗 ផែនទី៖ {maps_url}",
            parse_mode='Markdown'
        )
        await update.message.reply_text("🙏 អរគុណច្រើន! ទីតាំងរបស់អ្នកត្រូវបានបញ្ជូនទៅភ្នាក់ងារដឹកជញ្ជូនរួចរាល់ហើយ។", reply_markup=ReplyKeyboardRemove())

if __name__ == '__main__':
    # បើក Web Server ឱ្យដំណើរការ (កុំភ្លេចត្រូវមានឯកសារ keep_alive.py)
    keep_alive()
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    
    print("🚀 Bot កំពុងដំណើរការជាមួយប្រព័ន្ធផ្ទៀងផ្ទាត់លេខសម្ងាត់ និង Web Server...")
    app.run_polling()