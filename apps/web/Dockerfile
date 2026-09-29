FROM node:24-alpine AS build
RUN npm install -g pnpm@11.25.0
WORKDIR /web
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml apps/web/.npmrc ./
RUN pnpm install --frozen-lockfile
COPY apps/web ./
RUN pnpm build
FROM nginxinc/nginx-unprivileged:1.28-alpine
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 8080
