# api/utils/response.py
import json

def send_json(handler, data, status=200):
    """Отправка JSON ответа"""
    response = json.dumps(data, ensure_ascii=False).encode('utf-8')
    
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(response)))
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    handler.end_headers()
    
    handler.wfile.write(response)

def send_error(handler, message, status=400):
    """Отправка ошибки"""
    send_json(handler, {'success': False, 'error': message}, status)

def get_json_body(handler):
    """Получение JSON из тела запроса"""
    content_length = int(handler.headers.get('Content-Length', 0))
    if content_length <= 0:
        return {}
    
    body = handler.rfile.read(content_length)
    try:
        return json.loads(body.decode('utf-8'))
    except json.JSONDecodeError:
        raise ValueError('Invalid JSON')
