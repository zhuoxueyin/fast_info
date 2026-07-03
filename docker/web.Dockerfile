ARG DOCKER_REGISTRY_PREFIX=
FROM ${DOCKER_REGISTRY_PREFIX}node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM ${DOCKER_REGISTRY_PREFIX}node:20-alpine AS docs-build
WORKDIR /app/docs-site
COPY docs-site/package*.json ./
RUN npm ci
COPY docs-site ./
RUN npm run build

FROM ${DOCKER_REGISTRY_PREFIX}nginx:1.27-alpine
COPY docker/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /app/frontend/dist /usr/share/nginx/html
COPY --from=docs-build /app/docs-site/.vitepress/dist /usr/share/nginx/docs

EXPOSE 80
