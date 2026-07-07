ARG DOCKER_REGISTRY_PREFIX=
FROM ${DOCKER_REGISTRY_PREFIX}node:20-alpine AS frontend-build
WORKDIR /app/frontend
# 限制 Node 堆内存，避免前端构建在内存较小的机器上 OOM
ENV NODE_OPTIONS="--max-old-space-size=900"
COPY frontend/package*.json ./
# --maxsockets=1 降低 npm 安装并发，进一步减少内存峰值
RUN npm ci --maxsockets=1
COPY frontend ./
# 低内存机器上 vue-tsc 类型检查容易 OOM，跳过类型检查只执行 vite build。
# 类型检查请在本地或 CI 中通过 `npm run check` 单独执行。
RUN npx vite build

FROM ${DOCKER_REGISTRY_PREFIX}node:20-alpine AS docs-build
WORKDIR /app/docs-site
ENV NODE_OPTIONS="--max-old-space-size=900"
COPY docs-site/package*.json ./
RUN npm ci --maxsockets=1
COPY docs-site ./
RUN npm run build

FROM ${DOCKER_REGISTRY_PREFIX}nginx:1.27-alpine
COPY docker/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /app/frontend/dist /usr/share/nginx/html
COPY --from=docs-build /app/docs-site/.vitepress/dist /usr/share/nginx/docs

EXPOSE 80
