# ── Stage 1: Build ────────────────────────────────────────────────
FROM node:20-slim AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --silent

COPY . .

# VITE_API_URL must be passed at build time via --build-arg
ARG VITE_API_URL=http://localhost:8000/api
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# ── Stage 2: Serve with nginx ─────────────────────────────────────
FROM nginx:1.25-alpine AS runtime

# Copy built app
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx config: SPA routing + gzip + port 8080 (Cloud Run)
RUN cat > /etc/nginx/conf.d/default.conf << 'NGINX'
server {
    listen 8080;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip static assets
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript;
    gzip_min_length 1000;

    # SPA: all routes → index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets 1 year
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2|woff|ttf)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        add_header Vary Accept-Encoding;
    }

    # Health check endpoint for Cloud Run
    location /health {
        access_log off;
        return 200 "ok\n";
        add_header Content-Type text/plain;
    }
}
NGINX

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
