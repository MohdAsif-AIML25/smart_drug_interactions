# ============================================
# Smart Drug Interaction Platform — Frontend
# React + Vite + Nginx Multi-stage Dockerfile
# ============================================

FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json ./
COPY package-lock.json* ./

RUN npm install

COPY . .

RUN npm run build


# ── Production Stage ────────────────────────
FROM nginx:alpine AS production

# Install curl for healthcheck
RUN apk add --no-cache curl

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]