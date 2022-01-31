from pathlib import Path
from importlib.abc import MetaPathFinder, Loader
from importlib.util import spec_from_loader
from textwrap import dedent
import sys


class DjangoViewFileFinder(MetaPathFinder):

    def find_spec(self, import_name, path=None, target=None):
        if path is None:
            path = sys.path
        for directory in path:
            module_name = import_name.split(".")[-1]
            djv_path = Path(directory, f"{module_name}.djv")
            if djv_path.is_file():
                return spec_from_loader(
                    module_name,
                    DjangoViewFileLoader(djv_path),
                )


class DjangoViewFileLoader(Loader):

    def __init__(self, djv_path):
        self.djv_path = djv_path

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        try:
            contents = self.djv_path.read_text()
            py_code, template = contents.split("\n---\n", maxsplit=1)
            py_code += dedent("""
                def auto_template(view_func):
                    from functools import wraps
                    from django.http import HttpResponse
                    from django.template import RequestContext, Template
                    @wraps(view_func)
                    def new_view(request, *args, **kwargs):
                        response = view_func(request, *args, **kwargs)
                        if isinstance(response, HttpResponse):
                            return response
                        context = RequestContext(request, response)
                        rendered = Template(TEMPLATE).render(context)
                        return HttpResponse(rendered)
                    return new_view

                view = auto_template(view)
            """)
            py_code += f'\nTEMPLATE = """{template}"""\n'
            exec(py_code, module.__dict__)
        except OSError:
            raise ImportError(f"Could not open {str(self.djv_path)!r}")
        except ValueError:
            raise ImportError(f"{str(self.djv_path)!r} file format invaled")
        return module


def import_json(name, paths):
    spec = DjangoViewFileFinder().find_spec(name, paths)
    if spec:
        return spec.loader.create_module(spec)


finder = DjangoViewFileFinder()
sys.meta_path.append(finder)
