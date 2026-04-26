FROM node:24-bookworm-slim

WORKDIR /app

ENV NODE_ENV=production
ENV PROGRAM_ADMIN_HOST=0.0.0.0
ENV PROGRAM_ADMIN_PORT=8787
ENV PROGRAM_ADMIN_TRUST_PROXY=false

COPY package.json ./
RUN npm install --omit=dev

COPY src ./src
COPY ui ./ui
COPY tools ./tools
RUN mkdir -p /app/data

EXPOSE 8787

CMD ["node", "src/server.js"]
