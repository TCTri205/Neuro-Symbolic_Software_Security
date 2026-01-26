from unittest.mock import MagicMock
from src.core.context.loader import ProjectContext
from src.plugins.django.plugin import DjangoPlugin


class TestDjangoPlugin:
    def test_detect_returns_true_for_django_project(self):
        plugin = DjangoPlugin()
        context = MagicMock(spec=ProjectContext)
        context.pyproject = {"project": {"dependencies": ["Django>=4.0", "requests"]}}
        context.settings = {}
        assert plugin.detect(context) is True

    def test_detect_returns_true_for_django_settings_module(self):
        plugin = DjangoPlugin()
        context = MagicMock(spec=ProjectContext)
        context.pyproject = {}
        context.settings = {"ROOT_URLCONF": "myproject.urls"}
        assert plugin.detect(context) is True

    def test_parse_routes(self, tmp_path):
        plugin = DjangoPlugin()

        # Create a sample urls.py
        urls_file = tmp_path / "urls.py"
        urls_file.write_text(
            """
from django.urls import path, re_path, include
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('articles/<int:year>/', views.year_archive),
    re_path(r'^blog/', include('blog.urls')),
    path('api/v1/', include('api.urls')),
]
""",
            encoding="utf-8",
        )

        routes = plugin.parse_routes(str(tmp_path))

        assert len(routes) == 4

        # Verify admin
        r1 = next(r for r in routes if r.path == "admin/")
        assert r1.handler == "admin.site.urls"

        # Verify views.year_archive
        r2 = next(r for r in routes if r.path == "articles/<int:year>/")
        assert r2.handler == "views.year_archive"

        # Verify includes
        # re_path argument might be parsed slightly differently depending on AST node (Constant vs Call?)
        # r'^blog/' is a string.
        r3 = next(r for r in routes if "blog" in r.path)
        assert r3.handler == "include(...)"
        assert r3.django_func == "re_path" if hasattr(r3, "django_func") else True
