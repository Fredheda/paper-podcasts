# Build context: frontend/  ->  docker build -t podcasts-web frontend
FROM node:24-alpine AS builder
WORKDIR /app
RUN npm install -g npm@12.2.2 && npm --version
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY . .
RUN npm run build

FROM node:24-alpine
WORKDIR /app
RUN npm install -g npm@12.2.2 && npm --version
ENV NODE_ENV=production
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts
COPY --from=builder /app/dist ./dist
COPY server.js ./server.js
EXPOSE 3000
CMD ["node", "server.js"]
