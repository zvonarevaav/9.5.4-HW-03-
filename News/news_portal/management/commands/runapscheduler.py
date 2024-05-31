import logging

from django.conf import settings

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django.core.management.base import BaseCommand
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution
from django_apscheduler import util

from ...models import Subscribers, Post
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from datetime import datetime, timedelta
from dotenv import load_dotenv, find_dotenv
import os

load_dotenv(find_dotenv())
logger = logging.getLogger(__name__)


def my_job():
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    # создаем список имен и email всех подписчиков соответственно
    subscribers = Subscribers.objects.all().values('name', 'email')
    subscribers_name = [i['name'] for i in subscribers]
    subscribers_email = [i['email'] for i in subscribers]

    for i, name in enumerate(subscribers_name):
        # создаем список категорий каждого подписчика (у подписчика может быть несколько категорий)
        subscribers_category_id = [i['category'] for i in Subscribers.objects.filter(name=name).values('category')]
        # создаем список id постов на категорию которых подписан пользователь (несколько категорий)
        posts_list_id = list()
        for category_id in subscribers_category_id:
            post_gte = Post.objects.filter(category=category_id, time_post__gte=week_ago).values('id')
            post_list_id_i = [i['id'] for i in post_gte]
            posts_list_id += post_list_id_i

        # создаем уникальный список id постов и формируем QS модели Post отфильтрованных новостей
        posts_list_id_unique = list(set(posts_list_id))
        total_posts_list_qs = Post.objects.filter(id__in=posts_list_id_unique)

        # если у постов за неделю появились подписчики, то отсылаем им список постов
        if len(subscribers_name) != 0:
            print(f'Письмо отправлено {name} на email {subscribers_email[i]}')
            html_content = render_to_string('send_posts_week.html', {
                'username': name,
                'posts': total_posts_list_qs,
                # подгружено из .env
                'link': f'{os.getenv("WORLD_NEWS_HOST")}/news/'
            })
            message_html = EmailMultiAlternatives(
                subject='Список интересующих вас постов за неделю',
                # подгружено из .env
                from_email=os.getenv("DEFAULT_FROM_EMAIL"),
                to=[subscribers_email[i]]

            )
            message_html.attach_alternative(html_content, 'text/html')
            message_html.send()
        else:
            print('Нет подписчиков')


# The `close_old_connections` decorator ensures that database connections, that have become
# unusable or are obsolete, are closed before and after your job has run. You should use it
# to wrap any jobs that you schedule that access the Django database in any way.
@util.close_old_connections
def delete_old_job_executions(max_age=604_800):
    """
    This job deletes APScheduler job execution entries older than `max_age` from the database.
    It helps to prevent the database from filling up with old historical records that are no
    longer useful.

    :param max_age: The maximum length of time to retain historical job execution records.
                    Defaults to 7 days.
    """
    DjangoJobExecution.objects.delete_old_job_executions(max_age)


class Command(BaseCommand):
    help = "Runs APScheduler."

    def handle(self, *args, **options):
        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        scheduler.add_job(
            my_job,
            trigger=CronTrigger(day_of_week="sat", hour="19", minute="09"),  # Каждую субботу в 19:09
            id="my_job",  # The `id` assigned to each job MUST be unique
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'my_job'.")

        scheduler.add_job(
            delete_old_job_executions,
            trigger=CronTrigger(
                day_of_week="mon", hour="00", minute="00"
            ),  # Midnight on Monday, before start of the next work week.
            id="delete_old_job_executions",
            max_instances=1,
            replace_existing=True,
        )
        logger.info(
            "Added weekly job: 'delete_old_job_executions'."
        )

        try:
            logger.info("Starting scheduler...")
            scheduler.start()
        except KeyboardInterrupt:
            logger.info("Stopping scheduler...")
            scheduler.shutdown()
            logger.info("Scheduler shut down successfully!")