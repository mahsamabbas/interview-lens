FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# The browser must call the host-mapped API port, not Docker service DNS.
ARG VITE_API_BASE=http://localhost:8004
ENV VITE_API_BASE=$VITE_API_BASE

RUN npm run build

FROM nginx:1.27-alpine AS runner

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
