FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy application files
COPY monitor-uptimes-endpoint.js ./

# Run the script
CMD ["node", "monitor-uptimes-endpoint.js"]
