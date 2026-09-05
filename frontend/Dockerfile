# =============================================================================
# Global Infrastructure -- web image
#
# Vite inlines VITE_API_BASE_URL at build time, so it is a build argument rather
# than a runtime environment variable.
# =============================================================================

# --- Stage 1: build the SPA --------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

# Dependencies first: this layer is cached unless the lockfile changes.
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY . .

ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build


# --- Stage 2: serve ----------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

# Run unprivileged. /var/run is not writable by the nginx user, so the pid file
# is relocated into the cache directory, which is. The `user` directive is
# dropped because it is meaningless (and warns) for a non-root master process.
RUN mkdir -p /var/cache/nginx \
    && chown -R nginx:nginx /var/cache/nginx /usr/share/nginx/html \
    && sed -i 's|^pid .*|pid /var/cache/nginx/nginx.pid;|' /etc/nginx/nginx.conf \
    && sed -i '/^user  *nginx;/d' /etc/nginx/nginx.conf

USER nginx

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD wget --spider -q http://127.0.0.1:8080/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
