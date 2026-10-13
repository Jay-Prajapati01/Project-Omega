FROM node:20-alpine

WORKDIR /app

# Install dependencies first (cached layer)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source (in dev, we bind-mount over this anyway)
COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
