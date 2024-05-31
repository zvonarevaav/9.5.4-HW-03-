import os

from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from .models import PostCategory, SubscriberToCategory, Subscribers
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


@receiver(m2m_changed, sender=PostCategory)
def notify_create_post(sender, instance, **kwargs):
    if kwargs['action'] == 'pre_add':
        subscribers_list_email = list()
        for i in kwargs['pk_set']:
            subscribers_list_email_i = SubscriberToCategory.objects.filter(category__id=i).values('subscriber__email')
            subscribers_list_email += subscribers_list_email_i
        # получаем уникальный список email пользователей
        subscribers_list_email_unique = list(set([email['subscriber__email'] for email in subscribers_list_email]))

        subscribers_list_user = list()
        for email in subscribers_list_email_unique:
            subscribers_list_user_i = Subscribers.objects.filter(email=email).values('name')
            subscribers_list_user += subscribers_list_user_i
        # получаем список имен пользователей по email
        subscribers_list_user_unique = [name['name'] for name in subscribers_list_user]

        # если есть подписчики на данную категорию поста отправляем email
        if len(subscribers_list_email_unique) != 0:
            print('Почта отправляется')
            for i in range(len(subscribers_list_email_unique)):
                html_content = render_to_string('send_message.html', {
                    'username': subscribers_list_user_unique[i],
                    'title': instance.title,
                    'text_post': instance.preview(),
                    # подгружено из .env
                    'link': f'{os.getenv("WORLD_NEWS_HOST")}{instance.get_absolute_url()}'
                })
                message_html = EmailMultiAlternatives(
                    subject=f'Вышел новый пост: {instance.title}',
                    # подгружено из .env
                    from_email=os.getenv("DEFAULT_FROM_EMAIL"),
                    to=[subscribers_list_email_unique[i]]
                )
                message_html.attach_alternative(html_content, 'text/html')
                message_html.send()
        else:
            print('Нет подписчиков')