FROM oven/bun:1 AS builder

WORKDIR /app

# Install dependencies — cached layer, only re-runs when lockfile changes
COPY package.json bun.lock ./
RUN --mount=type=cache,target=/root/.bun/install/cache \
    bun install --frozen-lockfile

# Copy source and build
# PUBLIC_API_URL is baked in at build time — override via --build-arg
ARG PUBLIC_API_URL=http://localhost:8000
ENV PUBLIC_API_URL=$PUBLIC_API_URL

COPY . .
RUN bun run build

# Serve with nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

# Clean default config and use a minimal one
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
