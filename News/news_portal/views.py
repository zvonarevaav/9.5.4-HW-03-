from django.shortcuts import redirect, reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from .models import Post, Category, Subscribers, SubscriberToCategory, Author, PostCategory
from .filters import PostFilter
from .forms import CreateNewsForm, UpdateNewsForm
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import Group
from django.contrib.auth.decorators import login_required


class PostList(ListView):
    model = Post
    ordering = 'time_post'
    template_name = 'news.html'
    context_object_name = 'posts'
    paginate_by = 3

    def get_queryset(self):  # создаем форму для поиска по модели Post
        queryset = super().get_queryset()
        self.filterset = PostFilter(self.request.GET, queryset)
        return self.filterset.qs

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filterset'] = self.filterset  # помещаем форму в переменную
        if not self.request.user.is_staff:
            context['is_not_author'] = not self.request.user.groups.filter(name='authors').exists()
        return context


class PostDetail(DetailView):
    model = Post
    template_name = 'post.html'
    context_object_name = 'post'

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.request.user.is_staff:
            context['is_not_author'] = not self.request.user.groups.filter(name='authors').exists()
        # выводим категории, на которые пользователь подписан, в контекст
        subscriber = Subscribers.objects.get(email=self.request.user.email)
        subscriber_category = SubscriberToCategory.objects.filter(subscriber=subscriber).values('category')
        context['subscriber_category'] = [i['category'] for i in subscriber_category]

        return context


class PostSearch(LoginRequiredMixin, PostList):  # представление формы поиска поста
    template_name = 'search.html'


class CreateNews(PermissionRequiredMixin, CreateView):  # представление формы для создания новости
    form_class = CreateNewsForm
    model = Post
    template_name = 'create.html'
    permission_required = 'news_portal.add_post'

    def form_valid(self, form):
        news = form.save(commit=False)
        news.type_post = 'nw'
        return super().form_valid(form)


class CreateArticle(PermissionRequiredMixin, CreateView):  # представление для создания статьи
    form_class = CreateNewsForm
    model = Post
    template_name = 'create.html'
    permission_required = 'news_portal.add_post'

    def form_valid(self, form):
        article = form.save(commit=False)
        article.type_post = 'ar'
        return super().form_valid(form)


class UpdateNews(PermissionRequiredMixin, UpdateView):  # представление для редактирования новости/статьи
    form_class = UpdateNewsForm
    model = Post
    template_name = 'update.html'
    permission_required = 'news_portal.change_post'


class DeleteNews(LoginRequiredMixin, DeleteView):  # представление для удаления новости/статьи
    model = Post
    template_name = 'delete.html'
    success_url = reverse_lazy('list')


@login_required
def upgrade_me(request):  # кнопка стать автором
    user = request.user
    author_group = Group.objects.get(name='authors')
    if not request.user.groups.filter(name='authors').exists():
        author_group.user_set.add(user)
    return redirect('/news')

@login_required   # представление для копки subscribe
def subscribe(request, id_post, id_category):

    # получаем категорию из БД поля Category модели Post (ManyToMany)
    category = Category.objects.get(id=id_category)
    subscriber_name = request.user.username
    subscriber_email = request.user.email

    # проверяем есть ли subscriber в таблице Subscribers (если нет - добавляем его)
    if not Subscribers.objects.filter(email=subscriber_email):
        subscriber = Subscribers.objects.create(name=subscriber_name, email=subscriber_email)
    else:
        subscriber = Subscribers.objects.get(email=subscriber_email)

    # проверяем есть ли subscriber в таблице SubscribersToCategory (подписывался ли?)
    if not SubscriberToCategory.objects.filter(subscriber=subscriber, category=category):
        SubscriberToCategory.objects.create(subscriber=subscriber, category=category)

    return redirect(f'/news/{id_post}/')  # возвращаемся на то же место сайта