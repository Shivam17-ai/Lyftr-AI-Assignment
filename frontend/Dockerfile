# Stage 1: Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Build-time argument for API URL
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2: Production nginx runtime
FROM nginx:alpine AS runtime

# Copy custom nginx configuration listening on port 3000
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy build artifacts to nginx public directory
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
