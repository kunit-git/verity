# Verity frontend (Vite + React) dev image.
FROM node:24-alpine

WORKDIR /app

# Install dependencies first so the layer is cached across source changes.
COPY package.json package-lock.json ./
RUN npm ci

# Application source (shadowed by a bind mount in development).
COPY . .

EXPOSE 5173

# Bind to 0.0.0.0 so the dev server is reachable from outside the container.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
