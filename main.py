import requests
import json
import subprocess
import helper
from pyromod import listen
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardButton, InlineKeyboardMarkup,
    InlineQueryResultArticle, InputTextMessageContent
)
import asyncio
from pyrogram.errors import FloodWait
import time
import logging
import os
import sys
from config import Config
from KHABAR.p_bar import progress_bar
from KHABAR.get_video_info import get_video_attributes, get_video_thumb
from dotenv import load_dotenv

load_dotenv()
os.makedirs("./downloads", exist_ok=True)

bot = Client("bot", bot_token=Config.BOT_TOKEN, api_id=Config.API_ID, api_hash=Config.API_HASH)

# Utility Functions
async def exec(cmd):
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    print(stdout.decode())
    return proc.returncode, stderr.decode()

def sanitize_filename(name):
    return (name.replace("\t", "")
            .replace(":", "")
            .replace("/", "")
            .replace("+", "")
            .replace("#", "")
            .replace("|", "")
            .replace("@", "")
            .replace("*", "")
            .replace(".", "")
            .strip())

async def safe_send_media(chat_id, file_path, caption, thumb=None):
    try:
        if file_path.endswith('.pdf'):
            await bot.send_document(
                chat_id=chat_id,
                document=file_path,
                caption=caption,
                parse_mode="md"
            )
        else:
            duration, width, height = get_video_attributes(file_path)
            await bot.send_video(
                chat_id=chat_id,
                video=file_path,
                caption=caption,
                duration=duration,
                width=width,
                height=height,
                thumb=thumb or None,
                supports_streaming=True,
                parse_mode="md"
            )
        return True
    except Exception as e:
        print(f"Error sending file: {str(e)}")
        return False

# Start Command
@bot.on_message(filters.command("start"))
async def start_command(client, message):
    await message.reply_text(
        "🤖 Welcome to Media Downloader Bot! 🎥\n\n"
        "I can help you download media from various platforms. "
        "Simply send me the text file containing links of the media you want to download, and I'll take care of the rest.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("How to Use 📚", callback_data="how_to_use"),
                    InlineKeyboardButton("Supported Platforms 🌐", callback_data="supported_platforms"),
                ],
                [
                    InlineKeyboardButton("About ℹ️", callback_data="about"),
                    InlineKeyboardButton("Feedback 📝", callback_data="feedback"),
                ],
            ]
        ),
        parse_mode="md"
    )

# Callback Handler
@bot.on_callback_query()
async def callback_handler(client, query):
    if query.data == "how_to_use":
        await query.answer("📚 How to Use 📚")
        await query.message.reply_text(
            "Here's how to use the bot:\n\n"
            "1. Send me the text file containing links of the media you want to download.\n"
            "2. Wait for me to process the link and provide you with the download options.\n"
            "3. Select the desired download option and enjoy your media!",
            parse_mode="md"
        )
    elif query.data == "supported_platforms":
        await query.answer("🌐 Supported Platforms 🌐")
        await query.message.reply_text(
            "These are the supported platforms:\n\n"
            "- YouTube\n- Classplus\n- Pw\n- Visionias\n- Adda24x7\n- And more!",
            parse_mode="md"
        )
    elif query.data == "about":
        await query.answer("ℹ️ About ℹ️")
        await query.message.reply_text(
            "This bot was created to make downloading media from various platforms easier and more convenient. "
            "If you have any questions or suggestions, feel free to reach out!",
            parse_mode="md"
        )
    elif query.data == "feedback":
        await query.answer("📝 Feedback 📝")
        await query.message.reply_text(
            "Please leave your feedback by contacting @Mr_Luciferbot. Your input helps us improve the bot and provide a better experience for all users.",
            parse_mode="md"
        )

# Main Download Command
@bot.on_message(filters.command(["down"]))
async def download_handler(bot: Client, m: Message):
    global cancel
    cancel = False
    
    # Get TXT file with URLs
    editable = await m.reply_text("**Hello! Please send me the TXT file containing URLs**")
    input_msg = await bot.listen(editable.chat.id)
    txt_file = await input_msg.download()
    await input_msg.delete(True)

    # Process the TXT file
    try:
        with open(txt_file, "r") as f:
            content = f.read().split("\n")
        links = [line.split(":", 1) for line in content if line.strip()]
        os.remove(txt_file)
    except Exception as e:
        await m.reply_text(f"❌ Invalid file input: {str(e)}")
        if os.path.exists(txt_file):
            os.remove(txt_file)
        return

    # Get user inputs
    inputs = await get_user_inputs(bot, m, len(links))
    if not inputs:
        return

    count = inputs['start_num']
    mm = inputs['batch_name']
    raw_text0 = inputs['user_name']
    vid_format = inputs['resolution']
    thumb = inputs['thumbnail']

    # Process each link
    for i in range(inputs['start_index'], len(links)):
        if cancel:
            await m.reply_text("🚫 Download canceled!")
            break

        try:
            url = links[i][1]
            name = sanitize_filename(links[i][0])
            
            # Download the file
            file_path = await download_media(url, name, vid_format, m)
            if not file_path:
                continue

            # Prepare caption and thumbnail
            caption = prepare_caption(count, name, mm, raw_text0, vid_format)
            thumbnail = await prepare_thumbnail(thumb, name, file_path)

            # Send the file
            if await safe_send_media(m.chat.id, file_path, caption, thumbnail):
                count += 1
            
            # Cleanup
            cleanup_files(file_path, thumbnail, thumb)

        except Exception as e:
            await m.reply_text(f"❌ Error processing {name}: {str(e)}")
            continue

    await m.reply_text("✅ All downloads completed!")

# CPD Command
@bot.on_message(filters.command(["cpd"]))
async def cpd_handler(bot: Client, m: Message):
    editable = await m.reply_text("Please send the TXT file")
    input_msg = await bot.listen(editable.chat.id)
    txt_file = await input_msg.download()
    await input_msg.delete(True)

    # Process the TXT file
    try:
        with open(txt_file, "r") as f:
            content = f.read().split("\n")
        links = [line.split(":", 1) for line in content if line.strip()]
        os.remove(txt_file)
    except Exception as e:
        await m.reply_text(f"❌ Invalid file input: {str(e)}")
        if os.path.exists(txt_file):
            os.remove(txt_file)
        return

    # Get user inputs
    inputs = await get_user_inputs(bot, m, len(links), 
    if not inputs:
        return

    count = inputs['start_num']
    raw_text0 = inputs['batch_name']
    raw_text2 = inputs['resolution']
    thumb = inputs['thumbnail']

    # Process each link
    for i in range(inputs['start_index'], len(links)):
        try:
            url = links[i][1]
            name1 = sanitize_filename(links[i][0])
            
            # Handle PDF files
            if ".pdf" in url or "pdf" in name1:
                name = f"{str(count).zfill(3)}) {name1.replace('pdf', '')}.pdf"
                if not await download_pdf(url, name, m, count, raw_text0):
                    continue
                count += 1
                continue

            # Handle video files
            file_path, caption = await process_video_url(
                url, name1, raw_text2, count, raw_text0, m
            )
            if not file_path:
                continue

            # Send the file
            thumbnail = await prepare_thumbnail(thumb, name1, file_path)
            if await safe_send_media(m.chat.id, file_path, caption, thumbnail):
                count += 1
            
            # Cleanup
            cleanup_files(file_path, thumbnail, thumb)

        except Exception as e:
            await m.reply_text(f"❌ Error processing {name1}: {str(e)}")
            continue

    await m.reply_text("✅ All downloads completed!")

# Helper Functions
async def get_user_inputs(bot, m, total_links):
    try:
        # Get starting index
        editable = await m.reply_text(
            f"Total links found: {total_links}\n\nEnter starting number (default 1):"
        )
        input1 = await bot.listen(editable.chat.id)
        start_num = int(input1.text) if input1.text.isdigit() else 1
        start_index = start_num - 1

        # Get batch name
        editable = await editable.edit("**Enter Batch Name:**")
        input01 = await bot.listen(editable.chat.id)
        batch_name = input01.text

        # Get user name
        editable = await editable.edit("**Enter Your Name:**")
        input0 = await bot.listen(editable.chat.id)
        user_name = input0.text

        # Get resolution
        editable = await editable.edit("**Enter resolution (e.g., 360, 480, 720):**")
        input2 = await bot.listen(editable.chat.id)
        resolution = input2.text

        # Get thumbnail
        editable = await editable.edit(
            "**Send thumbnail URL**\n(or send 'no' to skip):"
        )
        input6 = await bot.listen(editable.chat.id)
        thumb = input6.text
        if thumb.lower() != "no" and (thumb.startswith("http://") or thumb.startswith("https://")):
            getstatusoutput(f"wget '{thumb}' -O 'thumb.jpg'")
            thumb = "thumb.jpg"
        else:
            thumb = "no"

        return {
            'start_num': start_num,
            'start_index': start_index,
            'batch_name': batch_name,
            'user_name': user_name,
            'resolution': resolution,
            'thumbnail': thumb
        }

    except Exception as e:
        await m.reply_text(f"❌ Error getting inputs: {str(e)}")
        return None

async def download_media(url, name, resolution, message):
    try:
        cmd = [
            "yt-dlp",
            "--no-warnings",
            "--socket-timeout", "30",
            "-R", "25",
            "--fragment-retries", "25",
            "--external-downloader", "aria2c",
            "--downloader-args", "aria2c: -x 16 -j 32",
            url
        ]

        if "youtu" in url:
            cmd.extend(["-f", f"b[height<={resolution}][ext=mp4]/bv[height<={resolution}][ext=mp4]+ba[ext=m4a]/b[ext=mp4]"])
        elif ".m3u8" in url or ".mp4" in url:
            cmd.extend(["-f", f"b[height<={resolution}]/bv[height<={resolution}]+ba"])
        elif ".pdf" in url:
            cmd = ['yt-dlp', '-o', f'{name}.pdf', url]
        else:
            cmd.extend(["-f", f"b[height<={resolution}]/bv[height<={resolution}]+ba/b/bv+ba"])

        cmd.extend(["-o", f"{name}.%(ext)s"])

        returncode, stderr = await exec(cmd)
        if returncode != 0:
            await message.reply_text(f"❌ Download failed for {name}: {stderr}")
            return None

        # Find the downloaded file
        for ext in ['.mp4', '.mkv', '.pdf']:
            if os.path.exists(f"{name}{ext}"):
                return f"{name}{ext}"

        await message.reply_text(f"❌ Downloaded file not found for {name}")
        return None

    except Exception as e:
        await message.reply_text(f"❌ Error downloading {name}: {str(e)}")
        return None

def prepare_caption(count, name, batch_name, user_name, resolution):
    if name.endswith('.pdf'):
        return f"{str(count).zfill(2)}. {name}\n\n**Batch:** {batch_name}\n**Downloaded By:** {user_name}"
    else:
        return f"{str(count).zfill(2)}. {name} - {resolution}p\n\n**Batch:** {batch_name}\n**Downloaded By:** {user_name}"

async def prepare_thumbnail(thumb, name, file_path):
    if thumb != "no" and os.path.exists(thumb):
        return thumb
    
    if not file_path.endswith('.pdf'):
        try:
            thumbnail = f"{name}.jpg"
            subprocess.run(
                f'ffmpeg -i "{file_path}" -ss 00:00:01 -vframes 1 "{thumbnail}"',
                shell=True
            )
            return thumbnail if os.path.exists(thumbnail) else None
        except:
            return None
    return None

def cleanup_files(file_path, thumbnail, thumb):
    if file_path and os.path.exists(file_path):
        os.remove(file_path)
    if thumbnail and thumbnail != thumb and os.path.exists(thumbnail):
        os.remove(thumbnail)

async def download_pdf(url, name, message, count, batch_name):
    try:
        r = requests.get(url, allow_redirects=True, timeout=30)
        if r.status_code != 200:
            await message.reply_text(f"❌ Failed to download PDF: HTTP {r.status_code}")
            return False

        with open(name, "wb") as f:
            f.write(r.content)

        caption = f"{name}\n\nBatch: {batch_name}\nIndex: {count}"
        await safe_send_media(message.chat.id, name, caption)
        os.remove(name)
        return True

    except Exception as e:
        await message.reply_text(f"❌ Error downloading PDF: {str(e)}")
        return False

async def process_video_url(url, name1, resolution, count, batch_name, message):
    try:
        # Handle different platforms
        if "classplus" in url:
            headers = {
                'Host': 'api.classplusapp.com',
                'x-access-token': 'YOUR_TOKEN_HERE',
                'user-agent': 'Mobile-Android'
            }
            params = (('url', url),)
            response = requests.get(
                'https://api.classplusapp.com/cams/uploader/video/jw-signed-url',
                headers=headers,
                params=params
            )
            url = response.json().get('url', url)

        # Download the video
        name = f"{str(count).zfill(3)}) {name1}"
        cmd = [
            "yt-dlp",
            "-f", f"bestvideo[height<={resolution}]+bestaudio",
            "--no-keep-video",
            "--remux-video", "mkv",
            url,
            "-o", f"{name}.%(ext)s"
        ]

        returncode, stderr = await exec(cmd)
        if returncode != 0:
            await message.reply_text(f"❌ Download failed for {name1}: {stderr}")
            return None, None

        file_path = f"{name}.mkv"
        if not os.path.exists(file_path):
            await message.reply_text(f"❌ Downloaded file not found for {name1}")
            return None, None

        caption = f"**Title:** {name1}\n**Batch:** {batch_name}\n**Index:** {str(count).zfill(3)}"
        return file_path, caption

    except Exception as e:
        await message.reply_text(f"❌ Error processing {name1}: {str(e)}")
        return None, None

# Other Commands (dhurina, vision) would follow similar patterns...

@bot.on_message(filters.command(["cancel"]))
async def cancel_handler(_, m):
    global cancel
    cancel = True
    await m.reply_text("⏹ Canceling all downloads...")

@bot.on_message(filters.command("restart"))
async def restart_handler(_, m):
    await m.reply_text("🔄 Restarting bot...")
    os.execl(sys.executable, sys.executable, *sys.argv)

print("✅ Bot is running successfully!")
bot.run()
