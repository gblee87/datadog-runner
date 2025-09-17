# Use Ubuntu-based Node.js image for better cross-platform compatibility
FROM node:20-bullseye-slim AS build
WORKDIR /app

# Install necessary build tools
RUN apt-get update && apt-get install -y \
    python3 \
    make \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json* ./

# Install dependencies with clean slate
RUN npm ci --no-optional

COPY . .

# Set Node.js options for memory and stability
ENV NODE_OPTIONS="--max-old-space-size=4096 --max-semi-space-size=1024"

# Build with retry mechanism for stability
RUN npm run build || (echo "First build failed, retrying..." && npm run build)

# serve
FROM nginx:1.25-alpine
COPY --from=build /app/dist/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
