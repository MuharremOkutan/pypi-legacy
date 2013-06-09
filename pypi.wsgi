#!/usr/bin/python
import sys
import os

PREFIX = os.path.dirname(__file__)

try:
    with open(os.path.join(PREFIX, "pypi.pth"), "r") as fp:
        path = fp.read().strip()
except IOError:
    path = PREFIX

sys.path.insert(0, path)

import cStringIO
import webui
import store
import config
import re
from functools import partial

store.keep_conn = True

PREFIX = os.path.dirname(__file__)
CONFIG_FILE = os.environ.get("PYPI_CONFIG", os.path.join(PREFIX, "config.ini"))


class Request:

    def __init__(self, environ, start_response):
        self.start_response = start_response
        try:
            length = int(environ.get('CONTENT_LENGTH', 0))
        except ValueError:
            length = 0
        self.rfile = cStringIO.StringIO(environ['wsgi.input'].read(length))
        self.wfile = cStringIO.StringIO()
        self.config = config.Config(CONFIG_FILE)

    def send_response(self, code, message='no details available'):
        self.status = '%s %s' % (code, message)
        self.headers = []

    def send_header(self, keyword, value):
        self.headers.append((keyword, value))

    def set_content_type(self, content_type):
        self.send_header('Content-Type', content_type)

    def end_headers(self):
        self.start_response(self.status, self.headers)


def debug(environ, start_response):
    if environ['PATH_INFO'].startswith("/auth") and \
           "HTTP_AUTHORIZATION" not in environ:
        start_response("401 login",
                       [('WWW-Authenticate', 'Basic realm="foo"')])
        return
    start_response("200 ok", [('Content-type', 'text/plain')])
    environ = environ.items()
    environ.sort()
    for k, v in environ:
        yield "%s=%s\n" % (k, v)
    return


def application(environ, start_response):
    if "HTTP_AUTHORIZATION" in environ:
        environ["HTTP_CGI_AUTHORIZATION"] = environ["HTTP_AUTHORIZATION"]
    try:
        r = Request(environ, start_response)
        webui.WebUI(r, environ).run()
        return [r.wfile.getvalue()]
    except Exception, e:
        import traceback;traceback.print_exc()
        return ['Ooops, there was a problem (%s)' % e]
#application=debug


# pretend to be like the UWSGI configuration - set SCRIPT_NAME to the first
# part of the PATH_INFO if it's valid and remove that part from the PATH_INFO
def site_fake(app, environ, start_response):
    PATH_INFO = environ['PATH_INFO']
    m = re.match('^/(pypi|simple|daytime|serversig|mirrors|id|oauth|'
        'security)(.*)', PATH_INFO)
    if not m:
        start_response("404 not found", [('Content-type', 'text/plain')])
        return ['Not Found: %s' % PATH_INFO]

    environ['SCRIPT_NAME'] = '/' + m.group(1)
    environ['PATH_INFO'] = m.group(2)

    return app(environ, start_response)


if __name__ == '__main__':
    # very simple wsgi server so we can play locally
    from wsgiref.simple_server import make_server
    httpd = make_server('', 8000, partial(site_fake, application))
    print "Serving on port 8000..."
    httpd.serve_forever()
