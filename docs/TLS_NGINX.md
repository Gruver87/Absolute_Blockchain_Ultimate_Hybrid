# TLS Termination with Nginx

> Reverse proxy перед REST `:8080` и RPC `:8545`. Учебный пример.

## nginx.conf (snippet)

```nginx
upstream abs_http {
    server 127.0.0.1:8080;
    keepalive 32;
}

upstream abs_rpc {
    server 127.0.0.1:8545;
    keepalive 16;
}

server {
    listen 443 ssl http2;
    server_name node.example.com;

    ssl_certificate     /etc/ssl/certs/node.crt;
    ssl_certificate_key /etc/ssl/private/node.key;
    ssl_protocols       TLSv1.2 TLSv1.3;

    # REST + Explorer
    location / {
        proxy_pass http://abs_http;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # JSON-RPC
    location /rpc/ {
        proxy_pass http://abs_rpc/;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
}

# Redirect HTTP → HTTPS
server {
    listen 80;
    server_name node.example.com;
    return 301 https://$host$request_uri;
}
```

## CORS в prod

После TLS обновите `CORS_ORIGINS`:

```bash
CORS_ORIGINS=https://node.example.com
```

## Rate limit (nginx layer, optional)

```nginx
limit_req_zone $binary_remote_addr zone=abs_api:10m rate=30r/s;

location / {
    limit_req zone=abs_api burst=60 nodelay;
    proxy_pass http://abs_http;
}
```

Комбинируется с Redis rate limit внутри приложения (`REDIS_RATE_LIMIT=true`).

## Let's Encrypt (certbot)

```bash
certbot certonly --nginx -d node.example.com
```

## API keys for RPC (roadmap)

Для публичного RPC рекомендуется отдельный `location` с `api_key` header check — пока вне scope; используйте JWT + firewall rules.
