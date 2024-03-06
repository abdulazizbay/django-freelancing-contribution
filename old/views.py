import requests
from django.shortcuts import render
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from telegram import Bot
from telegram import ParseMode



def index(request):
    return render(request, 'index.html')


def send_telegram_message(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone_number = request.POST.get('phone_number')
        message = request.POST.get('message')
        bot_token = '6403381292:AAFZ5zRVi_l0XlYC06tNUO0EJCdnewLgOHk'
        chat_id = '6828431075'  
        bot = Bot(token=bot_token)
        telegram_message = f"New message from {name}\n\nPhone: {phone_number}\n\nMessage:\n{message}"
        try:
            bot.send_message(chat_id=chat_id, text=telegram_message, parse_mode=ParseMode.MARKDOWN)
            messages.success(request, 'Сообщение успешно отправлено!')
            return render(request, 'index.html') 
        except Exception as e:
            print(f"Error sending message to Telegram: {e}")
            return HttpResponseRedirect(reverse('index.html')) 
    return render(request, 'index.html')      


