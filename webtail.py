#!/usr/bin/env python

"""
HTTP server that provides a web interface to run "tail" on a file (like
the Unix command).
"""

__version__ = '0.0.1'
__author__ = 'Santiago Coffey'
__email__ = 'scoffey@playdom.com'

import BaseHTTPServer
import logging
import sys
import urlparse

_STATIC_HTML = """<html>
<head>
<title>Web Tail</title>
<script type="text/javascript">

function param(key, fallback) {
    var query = window.location.search.substring(1);
    var parameters = query.split('&');
    for (var i = 0; i < parameters.length; i++) {
        var pair = parameters[i].split('=');
        if (pair[0] == key) {
            return unescape(pair[1]);
        }
    }
    return fallback;
}

var offset = 0;
var limit = parseInt(param('limit', 1000));
var polling = null;

var append = function (text) {
    if (text) {
        offset += text.match(/\\n/g).length;
        var element = document.getElementById('tail');
        element.textContent += text;
        window.scrollTo(0, document.body.scrollHeight);
    }
}

var request = function (uri, callback) {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', uri, true);
    xhr.onreadystatechange = function () {
        var done = 4, ok = 200;
        if (xhr.readyState == done && xhr.status == ok) {
            callback(xhr.responseText);
        }
    };
    xhr.send(null);
}

var tail = function () {
    var uri = '/tail?offset=' + offset + '&limit=' + limit;
    request(uri, append);
}

var refresh = function () {
    tail();
    if (polling == null) {
        var interval = parseInt(param('offset', 5000));
        polling = window.setInterval(tail, interval);
    }
}

var sleep = function () {
    if (polling != null) {
        window.clearInterval(polling);
        polling = null;
    }
}

window.onload = function () {
    request('/linecount', function (text) {
        var linecount = parseInt(text);
        offset = Math.max(0, linecount - limit);
        window.onfocus = refresh;
        window.onblur = sleep;
        refresh();
    });
}

</script>
</head>

<body style="background: black; color: #ddd;">
<pre id="tail"></pre>
</body>

</html>
"""

class WebTailHTTPRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    """ Request handler for the web tail server """

    protocol_version = 'HTTP/1.1'

    filename = None # determines file to tail

    def do_GET(self):
        self.http_headers = {}
        routes = {
            '/': lambda request: _STATIC_HTML,
            '/linecount': self._get_linecount,
            '/tail': self._get_tail,
        }
        url = urlparse.urlsplit(self.path)
        request = dict(urlparse.parse_qsl(url.query))
        handler = routes.get(url.path, lambda request: None)
        body = handler(request)
        self._serve(body, 400 if body is None else 200)

    def _get_linecount(self, request):
        count = self.linecount(self.filename)
        logging.info('linecount(%r) returned %d', self.filename, count)
        return str(count)

    def _get_tail(self, request):
        offset = int(request.get('offset', 0))
        limit = int(request.get('limit', 1000))
        lines = self.tail(self.filename, offset, limit)
        logging.info('tail(%r, %r, %r) returned %d lines', \
                self.filename, offset, limit, len(lines))
        self.http_headers['Content-Type'] = 'text/plain'
        return ''.join(lines)

    def _serve(self, body, http_status=200):
        self.send_response(http_status)
        self.http_headers.setdefault('Content-Type', 'text/html')
        self.http_headers.setdefault('Content-Length', len(body))
        self.http_headers.setdefault('Connection', 'keep-alive')
        for k, v in self.http_headers.iteritems():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def linecount(self, filename):
        """ Returns the number of lines in a file """
        count = 0
        stream = open(filename)
        for line in stream:
            count += 1
        stream.close()
        return count

    def tail(self, filename, offset=0, limit=1000):
        """ Returns lines in a file (from given offset, up to limit lines) """
        lines = []
        maxlinenum = offset + limit
        stream = open(filename)
        for linenum, line in enumerate(stream):
            if linenum > maxlinenum or not line.endswith('\n'):
                break
            if linenum >= offset:
                lines.append(line)
        stream.close()
        return lines

    def log_request(self, code='-', size='-'):
        pass

class WebTailServer(BaseHTTPServer.HTTPServer):
    """ Web tail server.

        Only differs from BaseHTTPServer.HTTPServer in the handling of
        exceptions while processing requests. """

    def _handle_request_noblock(self):
        try:
            request, client_address = self.get_request()
        except socket.error:
            return
        if self.verify_request(request, client_address):
            try:
                self.process_request(request, client_address)
            except KeyboardInterrupt:
                self.close_request(request)
                raise
            except Exception:
                self.handle_error(request, client_address)
                self.close_request(request)

    def handle_error(self, request, client_address):
        logging.exception('Error while processing request from %s:%d', \
                *client_address)

def main(program, filename=None, port=4411, **kwargs):
    """ Main program: Runs the web tail HTTP server """
    if filename is None:
        logging.error('No input file to tail')
        return
    try:
        WebTailHTTPRequestHandler.filename = filename
        server_address = ('', int(port))
        httpd = WebTailServer(server_address, WebTailHTTPRequestHandler)
        logging.info('Starting HTTP server at port %d', server_address[1])
        httpd.serve_forever()
    except KeyboardInterrupt:
        logging.info('HTTP server stopped')

if __name__ == '__main__':
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, \
            format='[%(asctime)s] [%(levelname)s] %(message)s')
    main(*sys.argv)
