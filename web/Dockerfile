FROM node:24.18.0-bookworm-slim AS builder

WORKDIR /workspace/web

COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

COPY . ./

ARG VITE_API_BASE_URL=/api/v1
ARG VITE_USE_MOCK_API=false
ARG VITE_ENABLE_DESIGN_MOCK_FALLBACK=false
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_USE_MOCK_API=${VITE_USE_MOCK_API} \
    VITE_ENABLE_DESIGN_MOCK_FALLBACK=${VITE_ENABLE_DESIGN_MOCK_FALLBACK}

RUN test "${VITE_API_BASE_URL}" = "/api/v1" \
    && test "${VITE_USE_MOCK_API}" = "false" \
    && test "${VITE_ENABLE_DESIGN_MOCK_FALLBACK}" = "false" \
    && npm run build

FROM nginx:1.29.5-alpine3.23

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /workspace/web/dist /usr/share/nginx/html
RUN sed -i 's#^pid[[:space:]].*#pid /tmp/nginx.pid;#' /etc/nginx/nginx.conf

USER nginx

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=6 \
  CMD wget --quiet --spider http://127.0.0.1:8080/ || exit 1
