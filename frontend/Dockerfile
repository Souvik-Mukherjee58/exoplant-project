# ---- Stage 1: Build ----
FROM node:20.18-alpine AS builder

WORKDIR /build

COPY package.json package-lock.json ./
RUN npm ci --production=false

COPY . .

# Build-time env: API requests proxied by nginx in production
ENV VITE_API_BASE_URL=/api/v1
RUN npm run build


# ---- Stage 2: Production (nginx non-root) ----
FROM nginx:1.27.3-alpine AS runtime

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/conf.d/exosignal.conf
COPY --from=builder /build/dist /usr/share/nginx/html

# Grant non-root nginx user permission to bind port 80 and write runtime pid/cache
RUN apk add --no-cache libcap && \
    setcap 'cap_net_bind_service=+ep' /usr/sbin/nginx && \
    apk del libcap && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid /var/cache/nginx /var/log/nginx /etc/nginx/conf.d /usr/share/nginx/html

USER nginx

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
