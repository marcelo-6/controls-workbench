# ---- build ----
FROM node:20-alpine AS build
WORKDIR /app

# Enable pnpm via Corepack
RUN corepack enable && corepack prepare pnpm@9.12.3 --activate

# Copy only manifests first (better Docker cache)
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Copy source and build
COPY . .
RUN pnpm build

# ---- runtime ----
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
