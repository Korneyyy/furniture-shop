# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Создаёт или обновляет суперпользователей'

    def handle(self, *args, **options):
        users_data = [
            {
                'username': 'admin',
                'email': 'admin@admin.com',
                'password': 'admin123',
            },
            {
                'username': 'ayratSupUz',
                'email': 'abdulhakkibnilias@gmail.com',
                'password': 'vostok26tiger',
            },
        ]

        for data in users_data:
            username = data['username']
            email = data['email']
            password = data['password']

            if User.objects.filter(username=username).exists():
                user = User.objects.get(username=username)
                user.set_password(password)
                user.is_superuser = True
                user.is_staff = True
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f'SUCCESS: Пользователь "{username}" обновлён')
                )
            else:
                User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password,
                )
                self.stdout.write(
                    self.style.SUCCESS(f'SUCCESS: Суперпользователь "{username}" создан')
                )