#!/usr/bin/env python3
import http.server
import socketserver
import os

PORT = 8080
DIRECTORY = "/home/samuel-appiah-kubi-acl/Desktop/Projects/PRCS/static/tiles"

class RangeRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def end_headers(self):
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()
    
    def do_GET(self):
        # Handle range requests
        range_header = self.headers.get('Range')
        if range_header:
            try:
                # Parse range header
                range_value = range_header.strip().split('=')[1]
                start, end = range_value.split('-')
                start = int(start)
                end = int(end) if end else None
                
                file_path = self.translate_path(self.path)
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    if end is None or end >= file_size:
                        end = file_size - 1
                    
                    self.send_response(206)
                    self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                    self.send_header('Content-Length', str(end - start + 1))
                    self.send_header('Accept-Ranges', 'bytes')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    
                    with open(file_path, 'rb') as f:
                        f.seek(start)
                        self.wfile.write(f.read(end - start + 1))
                    return
            except:
                pass
        
        # Fall back to normal GET
        super().do_GET()

os.chdir(DIRECTORY)
handler = RangeRequestHandler
httpd = socketserver.TCPServer(("", PORT), handler)
print(f"Serving at port {PORT} with range request support")
print(f"Directory: {DIRECTORY}")
print(f"URL: http://127.0.0.1:{PORT}/")
httpd.serve_forever()
