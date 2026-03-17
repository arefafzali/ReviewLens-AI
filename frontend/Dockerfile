# Use the latest LTS version (Node 24)
FROM node:24-alpine

WORKDIR /app

# Alpine is tiny; if you use bcrypt or sharp, you often need these:
# RUN apk add --no-cache python3 make g++

# Copy dependency files first
COPY package.json package-lock.json ./

# npm ci is faster and more reliable in Docker than npm install
RUN npm ci

# Copy the rest of the source code
COPY . .

EXPOSE 3000

# Ensure the host is set to 0.0.0.0 so it's reachable from outside the container
CMD ["npm", "run", "dev", "--", "-H", "0.0.0.0", "-p", "3000"]