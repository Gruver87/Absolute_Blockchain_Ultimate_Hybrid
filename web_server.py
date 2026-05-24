#!/usr/bin/env python3
import http.server
import socketserver
import os

PORT = 8094
os.chdir(os.path.dirname(__file__))

Handler = http.server.SimpleHTTPRequestHandler
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"🌐 Web Server started on http://localhost:{PORT}")
    print(f"   Landing page: http://localhost:{PORT}/landing_page.html")
    print(f"   Whitepaper: http://localhost:{PORT}/whitepaper.html")
    httpd.serve_forever()
